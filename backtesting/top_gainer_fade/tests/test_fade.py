"""Sanity tests for the top-gainer fade: look-ahead safety, funding count, short PnL."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.top_gainer_fade.strategy import (
    FadeConfig, find_fades, _funding_intervals, _day_features)


def _day(sym_open, path, day="2025-03-01"):
    """Build a one-day 5m frame from an open + a list of close prices (5m apart)."""
    idx = pd.date_range(f"{day} 00:00", periods=len(path), freq="5min", tz="UTC")
    close = np.array(path, dtype=float)
    high = np.maximum(close, np.roll(close, 1)); high[0] = max(sym_open, close[0])
    low = np.minimum(close, np.roll(close, 1)); low[0] = min(sym_open, close[0])
    op = np.concatenate([[sym_open], close[:-1]])
    return pd.DataFrame({"open": op, "high": high, "low": low,
                         "close": close, "volume": 1.0}, index=idx)


def test_funding_intervals_count():
    e = pd.Timestamp("2025-03-01 12:00", tz="UTC")
    x = pd.Timestamp("2025-03-01 23:55", tz="UTC")
    assert _funding_intervals(e, x) == 1              # only 16:00 crossed
    assert _funding_intervals(e, pd.Timestamp("2025-03-01 15:00", tz="UTC")) == 0
    assert _funding_intervals(pd.Timestamp("2025-03-01 07:00", tz="UTC"),
                              pd.Timestamp("2025-03-01 17:00", tz="UTC")) == 2  # 08 + 16


def test_lookahead_safe_ranking_uses_only_pre_tdec():
    # huge spike happens AFTER t_dec -> must NOT influence runup ranking
    n = 288  # full day of 5m bars
    path = [100.0] * n
    for i in range(145, n):   # after 12:00 (bar 144)
        path[i] = 200.0
    df = _day(100.0, path)
    t_dec = df.index[0] + pd.Timedelta(hours=12)
    feat = _day_features(df, t_dec)
    assert abs(feat["runup"]) < 1e-9                  # flat up to t_dec
    assert feat["high_pre"] <= 100.0 + 1e-9           # SL ref ignores later spike


def _gainer_then_pullback(peak_pct, entry_pct, n=288, day="2025-03-01"):
    """Rise to a peak (resistance) before 12:00, pull back to entry_pct at t_dec,
    then keep falling after — the canonical fade setup with a real stop distance."""
    peak, entry = 100.0 * (1 + peak_pct), 100.0 * (1 + entry_pct)
    up = list(np.linspace(100.0, peak, 120))            # rise to peak (bars 0..119)
    back = list(np.linspace(peak, entry, 25))           # pull back into t_dec (~bar 144)
    tail = list(np.linspace(entry, entry * 0.90, n - len(up) - len(back)))  # fall after
    return _day(100.0, (up + back + tail)[:n], day=day)


def test_short_profits_when_price_falls_after_entry():
    df = _gainer_then_pullback(peak_pct=0.08, entry_pct=0.05)  # peak +8%, entry +5%
    trades = find_fades({"AAA": df}, FadeConfig(min_gain=0.02))
    assert len(trades) == 1
    t = trades[0]
    assert t.ct.direction == -1
    assert t.ct.sl > t.ct.entry                          # stop above entry (resistance)
    assert t.ct.gross_R > 0                              # price fell -> short wins
    assert t.symbol == "AAA"


def test_picks_single_biggest_gainer():
    small = _gainer_then_pullback(peak_pct=0.03, entry_pct=0.025)
    big = _gainer_then_pullback(peak_pct=0.09, entry_pct=0.08)
    trades = find_fades({"SMALL": small, "BIG": big}, FadeConfig(min_gain=0.02))
    assert len(trades) == 1
    assert trades[0].symbol == "BIG"


def test_long_side_flips_direction_stop_and_funding():
    df = _gainer_then_pullback(peak_pct=0.08, entry_pct=0.05)  # rises, pulls back, falls
    # LONG the same setup: dir +1, stop BELOW entry (support), and it should LOSE
    # here because price falls after entry (opposite of the winning short).
    lt = find_fades({"AAA": df}, FadeConfig(side="long", min_gain=0.02))
    st = find_fades({"AAA": df}, FadeConfig(side="short", min_gain=0.02))
    assert len(lt) == 1 and len(st) == 1
    assert lt[0].ct.direction == 1
    assert lt[0].ct.sl < lt[0].ct.entry            # long stop = support, below entry
    assert lt[0].ct.gross_R < 0 < st[0].ct.gross_R  # falling day: long loses, short wins
    # funding sign: at +1bp market funding, short earns (net up), long pays (net down)
    from backtesting.top_gainer_fade.run import _recost
    from backtesting.tjr_4x.engine import metrics_from_closed
    from dataclasses import replace as _r
    s0 = metrics_from_closed(_recost(st, FadeConfig(side="short", funding_bps_per_interval=0.0))).avg_R
    s1 = metrics_from_closed(_recost(st, FadeConfig(side="short", funding_bps_per_interval=1.0))).avg_R
    l0 = metrics_from_closed(_recost(lt, FadeConfig(side="long", funding_bps_per_interval=0.0))).avg_R
    l1 = metrics_from_closed(_recost(lt, FadeConfig(side="long", funding_bps_per_interval=1.0))).avg_R
    assert s1 >= s0                                 # short earns positive funding
    assert l1 <= l0                                 # long pays positive funding
