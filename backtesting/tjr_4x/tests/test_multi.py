"""Iteration-6 multi-instrument tests. Synthetic ClosedTrade lists only.

Builds ClosedTrade objects DIRECTLY (never reads caches / touches the
network) to exercise:
  (a) equal_trade_walk_forward -> k folds, counts differ by <=1, total preserved
  (b) fold ordering is by entry_time (ascending starts, monotone across folds)
  (c) pooled_closed concatenates across symbols + sorts by entry_time
  (d) net@realistic (r=0.5) > net@taker (r=1.0) on a fixture (more taker = worse)
"""

import pandas as pd
import pytest

from tjr_4x.engine import ClosedTrade
from tjr_4x import validation
from tjr_4x import multi_instrument as mi


_MAKER = 0.0002
_TAKER = 0.0005
_SLIP = 0.0005


def _ts(entry_time):
    t = pd.Timestamp(entry_time)
    return t.tz_localize("UTC") if t.tzinfo is None else t


def _win(entry_time, entry=100.0, sl=99.0, tp=102.0):
    """A TP winner: gross_R = |tp-entry|/|entry-sl| = 2.0 for these levels."""
    t = _ts(entry_time)
    risk = abs(entry - sl)
    g = abs(tp - entry) / risk
    # cost_R here is a placeholder; recost_trade recomputes it per cfg.
    return ClosedTrade(entry_time=t, fill_time=t, exit_time=t, direction=1,
                       entry=entry, sl=sl, tp=tp, exit_price=tp, outcome="tp",
                       gross_R=g, cost_R=0.0, net_R=g)


def _loss(entry_time, entry=100.0, sl=99.0, tp=102.0):
    t = _ts(entry_time)
    return ClosedTrade(entry_time=t, fill_time=t, exit_time=t, direction=1,
                       entry=entry, sl=sl, tp=tp, exit_price=sl, outcome="sl",
                       gross_R=-1.0, cost_R=0.0, net_R=-1.0)


def _series(n, start="2024-01-01", freq="1D"):
    """n winners at distinct ascending entry_times."""
    times = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    return [_win(t) for t in times]


# ------------------------------------------------------------------ #
# (a) k folds, equal-count (+/-1), total preserved
# ------------------------------------------------------------------ #
def test_equal_trade_walk_forward_equal_counts_and_total():
    closed = _series(17)          # not divisible by 8 -> counts must differ by 1
    folds = validation.equal_trade_walk_forward(closed, k=8)

    assert len(folds) == 8
    counts = [f["n"] for f in folds]
    assert sum(counts) == len(closed)             # total preserved
    assert max(counts) - min(counts) <= 1         # equal-count (+/-1)

    # exact-divisible case: all folds equal
    folds2 = validation.equal_trade_walk_forward(_series(16), k=8)
    assert [f["n"] for f in folds2] == [2] * 8

    # empty input -> empty result
    assert validation.equal_trade_walk_forward([], k=8) == []


# ------------------------------------------------------------------ #
# (b) fold ordering is by entry_time
# ------------------------------------------------------------------ #
def test_equal_trade_walk_forward_ordered_by_entry_time():
    # feed SHUFFLED closed trades; folds must still be time-ordered
    closed = _series(24)
    shuffled = closed[::-1]        # reversed input
    folds = validation.equal_trade_walk_forward(shuffled, k=8)

    starts = [f["start"] for f in folds]
    ends = [f["end"] for f in folds]
    assert starts == sorted(starts)               # ascending fold starts
    # each fold's end <= next fold's start (contiguous, disjoint by time)
    for i in range(len(folds) - 1):
        assert ends[i] <= starts[i + 1]


# ------------------------------------------------------------------ #
# (c) pooled_closed concatenates across symbols + sorts
# ------------------------------------------------------------------ #
def test_pooled_closed_concatenates_and_sorts():
    # two "symbols" with interleaving entry_times
    a = [_win("2024-01-02"), _win("2024-01-04"), _win("2024-01-06")]
    b = [_win("2024-01-01"), _win("2024-01-03"), _win("2024-01-05")]
    universe = {"AAA": (a, None), "BBB": (b, None)}

    pooled = mi.pooled_closed(universe)
    assert len(pooled) == len(a) + len(b)         # concatenated, none lost
    ets = [c.entry_time for c in pooled]
    assert ets == sorted(ets)                     # globally time-sorted


def test_symbol_of_parses_cache_filename():
    p = "/x/.cache/BTC_USDT_USDT_5m_1738118548341_1784774548341.csv"
    assert mi._symbol_of(p) == "BTC"
    assert mi._symbol_of("ETH_USDT_USDT_5m_1_2.csv") == "ETH"


# ------------------------------------------------------------------ #
# (d) net@realistic (r=0.5) > net@taker (r=1.0) ordering sanity
# ------------------------------------------------------------------ #
def test_net_realistic_beats_net_taker():
    """Per-fold: net@maker (r=0) >= net@realistic (r=0.5); and a direct
    r=0.5 vs r=1.0 pool comparison — more taker entries => lower net."""
    from dataclasses import replace
    from tjr_4x.engine import recost_trade, metrics_from_closed
    from tjr_4x.config import Config

    # mix of winners + losers so net is meaningful and cost differences show
    closed = _series(6) + [_loss("2024-01-10"), _loss("2024-01-11")]
    folds = validation.equal_trade_walk_forward(closed, k=4)
    for f in folds:
        if f["n"] > 0:
            assert f["net_maker"] >= f["net_realistic"]

    base = Config(**validation._BEST)

    def net_at(r):
        cfg = replace(base, cost_model="maker_taker", entry_taker_ratio=r)
        return metrics_from_closed([recost_trade(c, cfg) for c in closed]).avg_R

    assert net_at(0.0) > net_at(0.5) > net_at(1.0)   # more taker => lower net
