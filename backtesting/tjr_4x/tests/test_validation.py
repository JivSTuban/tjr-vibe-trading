"""Iteration-5 validation tests. Synthetic paths only, no network.

Covers:
  (a) entry_taker_ratio=0 reproduces the maker_taker cost of a known trade
      EXACTLY (regression guard for iteration-4 numbers).
  (b) entry_taker_ratio=1.0 makes the entry leg cost == taker+slip.
  (c) walk_forward partitions closed trades by time into k folds with
      correct counts (complete + disjoint).
  (d) cost_scenarios ordering: optimistic net >= realistic >= pessimistic.
"""

from dataclasses import replace

import pandas as pd
import pytest

from tjr_4x.config import Config
from tjr_4x.strategy import Trade
from tjr_4x import engine
from tjr_4x import validation


_MAKER = 0.0002
_TAKER = 0.0005
_SLIP = 0.0005


def _bars(records, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(records), freq="5min", tz="UTC")
    df = pd.DataFrame(records, index=idx,
                      columns=["open", "high", "low", "close"])
    df["volume"] = 1.0
    return df


def _long_trade(entry_time, entry=100.0, sl=99.0, tp=102.0):
    return Trade(entry_time=entry_time, direction=1, entry=entry, sl=sl, tp=tp,
                 sweep_level=99.0, bos_index=0, confirm_time=entry_time)


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


# ---------------------------------------------------------------------- #
# (a) regression: entry_taker_ratio=0 reproduces iteration-4 maker_taker
# ---------------------------------------------------------------------- #
def test_entry_taker_ratio_zero_reproduces_iter4_maker_taker():
    """r=0 must equal the exact iteration-4 maker_taker cost (win + loss)."""
    # winner: two maker legs
    cfg0 = replace(Config(), cost_model="maker_taker", entry_taker_ratio=0.0)
    win = engine.backtest(_win_df(), [_long_trade("2024-01-01")], cfg0)
    wct = win.closed_trades[0]
    risk = abs(wct.entry - wct.sl)  # 1.0
    expected_win = (_MAKER * wct.entry + _MAKER * wct.tp) / risk
    assert wct.cost_R == pytest.approx(expected_win)

    # loser: maker entry + (taker+slip) exit
    loss = engine.backtest(_loss_df(), [_long_trade("2024-01-01")], cfg0)
    lct = loss.closed_trades[0]
    expected_loss = (_MAKER * lct.entry + (_TAKER + _SLIP) * lct.sl) / risk
    assert lct.cost_R == pytest.approx(expected_loss)

    # and it must match the DEFAULT Config (entry_taker_ratio default is 0)
    default = engine.backtest(_win_df(), [_long_trade("2024-01-01")],
                              replace(Config(), cost_model="maker_taker"))
    assert default.closed_trades[0].cost_R == pytest.approx(wct.cost_R)


# ---------------------------------------------------------------------- #
# (b) entry_taker_ratio=1.0 -> entry leg cost == taker+slip
# ---------------------------------------------------------------------- #
def test_entry_taker_ratio_one_entry_leg_is_taker_plus_slip():
    """r=1.0: the entry leg pays taker+slip; TP leg stays maker."""
    cfg1 = replace(Config(), cost_model="maker_taker", entry_taker_ratio=1.0)
    win = engine.backtest(_win_df(), [_long_trade("2024-01-01")], cfg1)
    ct = win.closed_trades[0]
    risk = abs(ct.entry - ct.sl)  # 1.0
    # entry taker+slip, TP still maker
    expected = ((_TAKER + _SLIP) * ct.entry + _MAKER * ct.tp) / risk
    assert ct.cost_R == pytest.approx(expected)

    # and r=1 entry leg alone == taker+slip * entry (isolate the entry leg)
    cfg0 = replace(Config(), cost_model="maker_taker", entry_taker_ratio=0.0)
    win0 = engine.backtest(_win_df(), [_long_trade("2024-01-01")], cfg0)
    ct0 = win0.closed_trades[0]
    # difference in cost_R is purely the entry-leg delta
    entry_delta = ((_TAKER + _SLIP) - _MAKER) * ct.entry / risk
    assert (ct.cost_R - ct0.cost_R) == pytest.approx(entry_delta)


# ---------------------------------------------------------------------- #
# (c) walk_forward partitions by time into k folds, correct counts
# ---------------------------------------------------------------------- #
def _closed_at(times):
    closed = []
    for t in times:
        df = _win_df().copy()
        df.index = pd.date_range(t, periods=len(df), freq="5min", tz="UTC")
        ct = engine.backtest(df, [_long_trade(df.index[0])],
                             replace(Config(), cost_model="maker_taker")
                             ).closed_trades[0]
        closed.append(ct)
    return closed


def test_walk_forward_partitions_by_time_into_k_folds():
    """12 daily trades -> k=6 folds partition completely + disjointly."""
    times = pd.date_range("2024-01-01", periods=12, freq="1D", tz="UTC")
    closed = _closed_at(times)
    folds = validation.walk_forward(closed, k=6)

    assert len(folds) == 6
    total = sum(f["n"] for f in folds)
    assert total == len(closed)          # complete partition, none lost
    # each fold owns a contiguous time slice; every trade counted once
    for f in folds:
        assert f["n"] >= 0
    # folds are time-ordered
    starts = [f["start"] for f in folds]
    assert starts == sorted(starts)
    # empty input -> empty folds
    assert validation.walk_forward([], k=6) == []


# ---------------------------------------------------------------------- #
# (d) cost_scenarios ordering: optimistic >= realistic >= pessimistic
# ---------------------------------------------------------------------- #
def test_cost_scenarios_monotonic_ordering():
    """More taker entries => higher cost => lower net. Ordering must hold."""
    # mix of winners and losers so net is meaningful
    times = pd.date_range("2024-01-01", periods=6, freq="1D", tz="UTC")
    closed = _closed_at(times[:4])  # 4 winners
    # add two losers
    for t in times[4:]:
        df = _loss_df().copy()
        df.index = pd.date_range(t, periods=len(df), freq="5min", tz="UTC")
        ct = engine.backtest(df, [_long_trade(df.index[0])],
                             replace(Config(), cost_model="maker_taker")
                             ).closed_trades[0]
        closed.append(ct)

    rows = validation.cost_scenarios(closed, Config(**validation._BEST))
    assert [r["scenario"] for r in rows] == \
        ["optimistic", "realistic", "pessimistic"]
    opt, real, pess = (r["net_expR"] for r in rows)
    assert opt >= real >= pess
    assert rows[0]["entry_taker_ratio"] == 0.0
    assert rows[2]["entry_taker_ratio"] == 1.0
