"""Engine tests: fabricated 5m paths resolving to TP / SL / same-bar."""

import numpy as np
import pandas as pd
import pytest

from tjr_4x.config import Config
from tjr_4x.strategy import Trade
from tjr_4x import engine


def _bars(records, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(records), freq="5min", tz="UTC")
    df = pd.DataFrame(records, index=idx,
                      columns=["open", "high", "low", "close"])
    df["volume"] = 1.0
    return df


def _long_trade(entry_time, entry=100.0, sl=99.0, tp=102.0):
    # risk = 1.0 -> tp at +2R (102). direction long.
    return Trade(entry_time=entry_time, direction=1, entry=entry, sl=sl, tp=tp,
                 sweep_level=99.0, bos_index=0, confirm_time=entry_time)


def test_tp_hit_is_plus_two_R_win():
    """(4a) A path that fills then hits TP -> +2R gross, positive net R."""
    df = _bars([
        (100.5, 100.6, 99.9, 100.1),  # fill: low 99.9 <= entry 100
        (100.1, 101.0, 100.0, 100.9),
        (100.9, 102.5, 100.8, 102.4),  # hits TP 102
    ])
    t = _long_trade(df.index[0])
    res = engine.backtest(df, [t], Config())
    assert res.trade_count == 1
    ct = res.closed_trades[0]
    assert ct.outcome == "tp"
    assert ct.gross_R == pytest.approx(2.0)
    assert ct.net_R > 0
    assert res.win_rate == 1.0
    assert res.avg_R == pytest.approx(ct.net_R)


def test_sl_hit_is_minus_one_R_loss():
    """(4b) A path that fills then hits SL -> -1R gross, negative net R."""
    df = _bars([
        (100.5, 100.6, 99.9, 100.1),  # fill
        (100.1, 100.4, 98.5, 98.8),   # hits SL 99
    ])
    t = _long_trade(df.index[0])
    res = engine.backtest(df, [t], Config())
    ct = res.closed_trades[0]
    assert ct.outcome == "sl"
    assert ct.gross_R == pytest.approx(-1.0)
    assert ct.net_R < 0
    assert res.win_rate == 0.0


def test_same_bar_sl_and_tp_counts_as_loss():
    """(4c) A bar containing BOTH SL and TP -> SL-first (conservative loss)."""
    df = _bars([
        (100.5, 100.6, 99.9, 100.1),   # fill
        (100.1, 103.0, 98.0, 100.0),   # spans BOTH tp(102) and sl(99)
    ])
    t = _long_trade(df.index[0])
    res = engine.backtest(df, [t], Config())
    ct = res.closed_trades[0]
    assert ct.outcome == "sl"
    assert ct.gross_R == pytest.approx(-1.0)


def test_short_tp_and_sl_resolution():
    """Symmetry: a short fills on high>=entry and resolves TP below."""
    df = _bars([
        (99.5, 100.1, 99.4, 99.6),   # fill: high 100.1 >= entry 100
        (99.6, 99.8, 97.9, 98.0),    # hits short TP 98
    ])
    t = Trade(entry_time=df.index[0], direction=-1, entry=100.0, sl=101.0,
              tp=98.0, sweep_level=101.0, bos_index=0, confirm_time=df.index[0])
    res = engine.backtest(df, [t], Config())
    ct = res.closed_trades[0]
    assert ct.outcome == "tp"
    assert ct.gross_R == pytest.approx(2.0)


def test_max_one_open_position_skips_overlap():
    """Concurrency cap: a second trade opened while the first is still open
    is skipped (max_open_positions=1)."""
    df = _bars([
        (100.5, 100.6, 99.9, 100.1),  # t0 fills here
        (100.1, 100.4, 100.0, 100.2),
        (100.2, 100.5, 100.1, 100.3),
        (100.3, 102.5, 100.2, 102.4),  # t0 hits TP at bar 3
        (102.4, 102.6, 101.0, 101.2),
    ])
    t0 = _long_trade(df.index[0])
    t1 = _long_trade(df.index[1])   # overlaps t0's open window -> skipped
    res = engine.backtest(df, [t0, t1], Config())
    assert res.trade_count == 1


def test_entry_never_fills_is_dropped():
    """A trade whose entry price is never traded into is not counted."""
    df = _bars([
        (105.0, 106.0, 104.0, 105.5),
        (105.5, 106.5, 105.0, 106.0),
    ])
    t = _long_trade(df.index[0])  # entry 100 never reached
    res = engine.backtest(df, [t], Config())
    assert res.trade_count == 0


def test_metrics_expectancy_and_profit_factor():
    """Aggregate metrics: one win (+2R) + one loss (-1R) net of costs."""
    # Two sequential, non-overlapping trades.
    df = _bars([
        (100.5, 100.6, 99.9, 100.1),  # 0 t_win fill
        (100.1, 102.5, 100.0, 102.4),  # 1 t_win TP
        (100.0, 100.2, 99.8, 100.0),  # 2
        (100.5, 100.6, 99.9, 100.1),  # 3 t_loss fill
        (100.1, 100.4, 98.5, 98.8),   # 4 t_loss SL
    ])
    t_win = _long_trade(df.index[0])
    t_loss = _long_trade(df.index[3])
    res = engine.backtest(df, [t_win, t_loss], Config())
    assert res.trade_count == 2
    assert res.win_rate == pytest.approx(0.5)
    assert res.max_consecutive_losses == 1
    assert res.avg_win_R > 0 and res.avg_loss_R < 0
    # profit factor = gross win / gross loss, both net of costs
    assert res.profit_factor > 1.0
    assert res.max_drawdown_R < 0  # the loss creates a drawdown
