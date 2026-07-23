"""Iteration-3 exit-model tests: opposite-liquidity TP, min-stop filter,
min-rr skip, variable-R engine accounting, and TP-level causality.

Where practical these exercise the real detection path (via the canonical
``bullish_5m`` fixture); the opposite-liquidity level selector is also unit-
tested directly with hand-built ``shl``/``setup`` frames so the nearest-level
and causality rules are checked without depending on smc's swing spacing.
"""

import numpy as np
import pandas as pd
import pytest

from tjr_4x.config import Config
from tjr_4x.strategy import Trade, _opposite_liquidity_tp
from tjr_4x import strategy, engine


# --------------------------------------------------------------------------- #
# Direct unit tests of the opposite-liquidity level selector
# --------------------------------------------------------------------------- #
def _shl(kinds_levels, n):
    """Build a minimal swing_highs_lows-shaped frame.

    ``kinds_levels`` maps positional bar -> (kind, level); other bars NaN.
    """
    hl = np.full(n, np.nan)
    lvl = np.full(n, np.nan)
    for bar, (k, v) in kinds_levels.items():
        hl[bar] = k
        lvl[bar] = v
    return pd.DataFrame({"HighLow": hl, "Level": lvl})


def _setup_frame(n):
    """A dummy daily-less 15m setup frame; previous_high_low degenerates to
    NaN on this single-day span so swing levels drive the selector."""
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    v = np.linspace(100.0, 100.0, n)
    return pd.DataFrame({"open": v, "high": v, "low": v, "close": v,
                         "volume": 1.0}, index=idx)


def test_oppliq_picks_nearest_opposing_high_above_entry():
    """(a) For a long, the TP is the NEAREST swing HIGH strictly above entry
    whose pivot is confirmed at/before bos_bar; rr computed correctly."""
    cfg = Config(exit_model="opposite_liquidity", swing_length=3)
    n = 30
    # two opposing highs above entry 100: 103 (bar 4) and 101.5 (bar 8).
    # both confirmed (bar+3) well before bos_bar=20. nearest above 100 = 101.5.
    shl = _shl({4: (1, 103.0), 8: (1, 101.5), 12: (-1, 95.0)}, n)
    tp = _opposite_liquidity_tp(shl, _setup_frame(n), bos_bar=20,
                                direction=1, entry=100.0, cfg=cfg)
    assert tp == pytest.approx(101.5)
    # rr for a stop at 99.5 (risk 0.5) -> (101.5-100)/0.5 = 3.0
    risk = 0.5
    rr = (tp - 100.0) / risk
    assert rr == pytest.approx(3.0)


def test_oppliq_returns_none_when_no_level_beyond_entry():
    """No swing HIGH strictly above entry -> None (no fallback)."""
    cfg = Config(exit_model="opposite_liquidity", swing_length=3)
    n = 30
    shl = _shl({4: (1, 99.0), 8: (-1, 95.0)}, n)  # only a high BELOW entry
    tp = _opposite_liquidity_tp(shl, _setup_frame(n), bos_bar=20,
                                direction=1, entry=100.0, cfg=cfg)
    assert tp is None


def test_oppliq_causality_excludes_unconfirmed_pivot():
    """(e) A swing HIGH whose pivot is NOT yet confirmed at bos_bar
    (pivot_bar + swing_length > bos_bar) must be ignored; the chosen level is
    the one confirmed at/before bos_bar."""
    cfg = Config(exit_model="opposite_liquidity", swing_length=3)
    n = 30
    # nearer high 100.5 at bar 9 is NOT confirmed by bos_bar=10 (9+3=12>10);
    # farther high 102 at bar 4 IS confirmed (4+3=7<=10). Selector must pick
    # 102, not 100.5.
    shl = _shl({4: (1, 102.0), 9: (1, 100.5)}, n)
    tp = _opposite_liquidity_tp(shl, _setup_frame(n), bos_bar=10,
                                direction=1, entry=100.0, cfg=cfg)
    assert tp == pytest.approx(102.0)
    # sanity: with a later bos_bar the nearer (now-confirmed) level wins.
    tp2 = _opposite_liquidity_tp(shl, _setup_frame(n), bos_bar=20,
                                 direction=1, entry=100.0, cfg=cfg)
    assert tp2 == pytest.approx(100.5)


def test_oppliq_short_mirrors_to_nearest_low_below_entry():
    """Mirror: for a short, nearest swing LOW strictly below entry."""
    cfg = Config(exit_model="opposite_liquidity", swing_length=3)
    n = 30
    shl = _shl({4: (-1, 97.0), 8: (-1, 98.5), 12: (1, 105.0)}, n)
    tp = _opposite_liquidity_tp(shl, _setup_frame(n), bos_bar=20,
                                direction=-1, entry=100.0, cfg=cfg)
    assert tp == pytest.approx(98.5)  # closest low below 100


# --------------------------------------------------------------------------- #
# Full-path: min-rr skip and min-stop skip via find_trades
# --------------------------------------------------------------------------- #
def _force_bias(monkeypatch, sign):
    monkeypatch.setattr(
        strategy, "_select_bias",
        lambda df5m, cfg: pd.Series(
            sign, index=strategy._resample(strategy._prep(df5m),
                                           cfg.bias_timeframe).index),
    )


def test_oppliq_skips_setup_when_rr_below_min(bullish_5m, monkeypatch):
    """(b) The canonical setup has a wide stop (~6% below entry) so its nearest
    opposing high (101) is far closer than 1R away -> rr << 1 -> skipped when
    exit_model=opposite_liquidity with min_rr=1.0."""
    _force_bias(monkeypatch, +1)
    cfg = Config(exit_model="opposite_liquidity", min_rr=1.0)
    trades = strategy.find_trades(bullish_5m, cfg)
    assert trades == []
    # and with min_rr driven below the actual (~0.09) rr, it is NOT skipped.
    cfg_lo = Config(exit_model="opposite_liquidity", min_rr=0.05)
    trades_lo = strategy.find_trades(bullish_5m, cfg_lo)
    assert len(trades_lo) == 1
    t = trades_lo[0]
    assert t.tp == pytest.approx(101.0, abs=1e-6)  # nearest opposing high
    rr = (t.tp - t.entry) / (t.entry - t.sl)
    assert rr == pytest.approx((101.0 - t.entry) / (t.entry - t.sl))


def test_min_stop_filter_skips_tiny_stop(bullish_5m, monkeypatch):
    """(c) min_stop_pct skips a setup whose stop is a smaller fraction of price
    than the threshold. The canonical stop is ~6.5% of entry; a threshold of
    10% skips it, a threshold below it keeps it (fixed_rr)."""
    _force_bias(monkeypatch, +1)
    base = strategy.find_trades(bullish_5m, Config())
    assert len(base) == 1
    t = base[0]
    stop_frac = (t.entry - t.sl) / t.entry
    # threshold ABOVE the actual stop fraction -> skipped
    hi = strategy.find_trades(bullish_5m, Config(min_stop_pct=stop_frac + 0.01))
    assert hi == []
    # threshold BELOW the actual stop fraction -> kept
    lo = strategy.find_trades(bullish_5m, Config(min_stop_pct=stop_frac / 2))
    assert len(lo) == 1


# --------------------------------------------------------------------------- #
# Engine: variable-R gross accounting
# --------------------------------------------------------------------------- #
def _bars(records, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(records), freq="5min", tz="UTC")
    df = pd.DataFrame(records, index=idx,
                      columns=["open", "high", "low", "close"])
    df["volume"] = 1.0
    return df


def test_engine_variable_R_gross_on_tp_win():
    """(d) On a TP hit the engine's gross_R = actual |tp-entry|/|entry-sl|
    (not the fixed rr_target). Here entry 100, sl 99 (risk 1), tp 103.5 ->
    gross_R = 3.5. On an SL hit gross_R = -1."""
    # variable-R win: tp 103.5 (=3.5R)
    df = _bars([
        (100.5, 100.6, 99.9, 100.1),   # fill (low 99.9 <= 100)
        (100.1, 103.6, 100.0, 103.5),  # hits tp 103.5
    ])
    t = Trade(entry_time=df.index[0], direction=1, entry=100.0, sl=99.0,
              tp=103.5, sweep_level=99.0, bos_index=0, confirm_time=df.index[0])
    res = engine.backtest(df, [t], Config())
    ct = res.closed_trades[0]
    assert ct.outcome == "tp"
    assert ct.gross_R == pytest.approx(3.5)
    assert ct.net_R == pytest.approx(3.5 - ct.cost_R)

    # SL side still exactly -1R.
    df2 = _bars([
        (100.5, 100.6, 99.9, 100.1),   # fill
        (100.1, 100.4, 98.5, 98.8),    # hits sl 99
    ])
    res2 = engine.backtest(df2, [t], Config())
    ct2 = res2.closed_trades[0]
    assert ct2.outcome == "sl"
    assert ct2.gross_R == pytest.approx(-1.0)


def test_engine_fixed_2R_still_gross_two():
    """Regression: a fixed-2R trade (tp = entry + 2*risk) still gross_R = 2.0
    under the new actual-price accounting."""
    df = _bars([
        (100.5, 100.6, 99.9, 100.1),
        (100.1, 102.5, 100.0, 102.4),  # tp 102 = entry+2*risk
    ])
    t = Trade(entry_time=df.index[0], direction=1, entry=100.0, sl=99.0,
              tp=102.0, sweep_level=99.0, bos_index=0, confirm_time=df.index[0])
    res = engine.backtest(df, [t], Config())
    assert res.closed_trades[0].gross_R == pytest.approx(2.0)
