"""Iteration-4 cost model + 80/20 split tests.

Synthetic paths only, no network. Covers:
  (a) maker_taker TP-win cost = two maker legs.
  (b) maker_taker SL-loss cost = maker entry + (taker+slip) exit, and is
      LARGER (per unit risk) than the winner's cost.
  (c) for a fixed winner, maker_taker net_R > taker_only net_R.
  (d) the 80/20 split assigns closed trades to IS / OOS by entry_time.
"""

from dataclasses import replace

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
    return Trade(entry_time=entry_time, direction=1, entry=entry, sl=sl, tp=tp,
                 sweep_level=99.0, bos_index=0, confirm_time=entry_time)


# entry=100, sl=99, tp=102 -> risk=1.0 -> cost_R == cost in price terms.
_MAKER = 0.0002
_TAKER = 0.0005
_SLIP = 0.0005


def _win_df():
    return _bars([
        (100.5, 100.6, 99.9, 100.1),   # fill
        (100.1, 102.5, 100.0, 102.4),  # TP 102
    ])


def _loss_df():
    return _bars([
        (100.5, 100.6, 99.9, 100.1),   # fill
        (100.1, 100.4, 98.5, 98.8),    # SL 99
    ])


def test_maker_taker_tp_cost_is_two_maker_legs():
    """(a) TP win under maker_taker: maker*entry + maker*tp, /risk."""
    cfg = replace(Config(), cost_model="maker_taker")
    res = engine.backtest(_win_df(), [_long_trade("2024-01-01")], cfg)
    ct = res.closed_trades[0]
    assert ct.outcome == "tp"
    risk = abs(ct.entry - ct.sl)  # 1.0
    expected = (_MAKER * ct.entry + _MAKER * ct.tp) / risk
    assert ct.cost_R == pytest.approx(expected)
    assert ct.net_R == pytest.approx(ct.gross_R - expected)


def test_maker_taker_sl_cost_is_maker_entry_plus_taker_slip_exit():
    """(b) SL loss cost = maker entry + (taker+slip) exit; larger per-unit
    than the winner's cost."""
    cfg = replace(Config(), cost_model="maker_taker")
    loss = engine.backtest(_loss_df(), [_long_trade("2024-01-01")], cfg)
    win = engine.backtest(_win_df(), [_long_trade("2024-01-01")], cfg)
    lct, wct = loss.closed_trades[0], win.closed_trades[0]
    assert lct.outcome == "sl"
    risk = abs(lct.entry - lct.sl)  # 1.0
    expected = (_MAKER * lct.entry + (_TAKER + _SLIP) * lct.sl) / risk
    assert lct.cost_R == pytest.approx(expected)
    # loser's taker+slip exit leg makes it strictly costlier than the maker
    # winner (same risk of 1.0 here, so compare cost_R directly).
    assert lct.cost_R > wct.cost_R


def test_maker_taker_net_better_than_taker_only_for_a_winner():
    """(c) same fixed winner: maker_taker net_R > taker_only net_R."""
    mk = engine.backtest(_win_df(), [_long_trade("2024-01-01")],
                         replace(Config(), cost_model="maker_taker"))
    tk = engine.backtest(_win_df(), [_long_trade("2024-01-01")],
                         replace(Config(), cost_model="taker_only"))
    mct, tct = mk.closed_trades[0], tk.closed_trades[0]
    assert mct.gross_R == pytest.approx(tct.gross_R)  # same trade
    assert mct.net_R > tct.net_R                       # cheaper maker fees


def test_taker_only_uses_actual_fill_prices_per_leg():
    """taker_only charges (taker+slip) on entry and on exit_price."""
    cfg = replace(Config(), cost_model="taker_only")
    res = engine.backtest(_win_df(), [_long_trade("2024-01-01")], cfg)
    ct = res.closed_trades[0]
    per = _TAKER + _SLIP
    risk = abs(ct.entry - ct.sl)
    expected = (per * ct.entry + per * ct.exit_price) / risk
    assert ct.cost_R == pytest.approx(expected)


def test_recost_gross_is_zero_cost():
    """recost_trade with cost_model='gross' zeroes cost, net==gross."""
    res = engine.backtest(_win_df(), [_long_trade("2024-01-01")],
                          replace(Config(), cost_model="maker_taker"))
    g = engine.recost_trade(res.closed_trades[0], replace(Config(), cost_model="gross"))
    assert g.cost_R == 0.0
    assert g.net_R == pytest.approx(g.gross_R)


def test_80_20_split_assigns_by_entry_time():
    """(d) cutoff = first + 0.8*(last-first); IS < cutoff, OOS >= cutoff,
    partition is complete and disjoint, ordered by entry_time."""
    # 10 closed trades at daily spacing.
    times = pd.date_range("2024-01-01", periods=10, freq="1D", tz="UTC")
    closed = []
    for t in times:
        df = _win_df().copy()
        df.index = pd.date_range(t, periods=len(df), freq="5min", tz="UTC")
        ct = engine.backtest(df, [_long_trade(df.index[0])],
                             replace(Config(), cost_model="maker_taker")).closed_trades[0]
        closed.append(ct)

    ets = [c.entry_time for c in closed]
    first_ts, last_ts = min(ets), max(ets)
    cutoff = first_ts + 0.8 * (last_ts - first_ts)
    is_t = [c for c in closed if c.entry_time < cutoff]
    oos_t = [c for c in closed if c.entry_time >= cutoff]

    # 9-day span * 0.8 = 7.2 days -> cutoff on day ~8.2; days 0..7 IS (8), 8..9 OOS (2)
    assert len(is_t) + len(oos_t) == len(closed)
    assert len(is_t) == 8 and len(oos_t) == 2
    assert all(c.entry_time < cutoff for c in is_t)
    assert all(c.entry_time >= cutoff for c in oos_t)
    # disjoint
    assert not (set(id(c) for c in is_t) & set(id(c) for c in oos_t))
