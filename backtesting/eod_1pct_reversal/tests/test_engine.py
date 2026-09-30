"""Correctness pins for the EOD 1% engine.

These are the tests that decide whether a result means anything: fill ordering,
look-ahead, split distortion, and the rule that a missing feature must never pass a
gate. Everything else is arithmetic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.eod_1pct_reversal import execution as ex
from backtesting.eod_1pct_reversal import features as ft
from backtesting.eod_1pct_reversal import strategy as st
from backtesting.eod_1pct_reversal.run import control_table, forward_table


def frame(rows: list[dict]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-02", periods=len(rows), freq="B")
    df = pd.DataFrame(rows, index=idx)
    df["adjclose"] = df["close"]
    df["volume"] = 1e8
    return df


# ----------------------------------------------------------------- fill ordering

def test_gap_open_above_target_fills_at_the_open_not_the_target():
    """The trade that manufactures fake edge: a stock that opens +5% must be credited
    +5%, never a tidy +1%. Spec §6.2."""
    df = frame([
        {"open": 100, "high": 100, "low": 100, "close": 100},
        {"open": 105, "high": 106, "low": 104, "close": 105},
        {"open": 105, "high": 106, "low": 104, "close": 105},
    ])
    tab = forward_table(ft.adjusted(df), df["close"], horizon=1)
    row = tab.iloc[0]
    assert row["exit_kind"] == "gap_open"
    assert row["exit_price"] == pytest.approx(105.0)
    assert row["gross_ret"] == pytest.approx(0.05)


def test_intraday_touch_fills_at_the_target_exactly():
    df = frame([
        {"open": 100, "high": 100, "low": 100, "close": 100},
        {"open": 99, "high": 101.5, "low": 98, "close": 100.5},
        {"open": 100, "high": 101, "low": 99, "close": 100},
    ])
    tab = forward_table(ft.adjusted(df), df["close"], horizon=1)
    row = tab.iloc[0]
    assert row["exit_kind"] == "target"
    assert row["exit_price"] == pytest.approx(101.0)


def test_never_touched_exits_at_the_horizon_close_as_a_time_stop():
    df = frame([
        {"open": 100, "high": 100, "low": 100, "close": 100},
        {"open": 99, "high": 100.2, "low": 97, "close": 98},
        {"open": 98, "high": 99, "low": 96, "close": 97},
        {"open": 97, "high": 98, "low": 95, "close": 96},
    ])
    tab = forward_table(ft.adjusted(df), df["close"], horizon=3)
    row = tab.iloc[0]
    assert row["exit_kind"] == "time_stop"
    assert row["exit_price"] == pytest.approx(96.0)
    assert row["gross_ret"] == pytest.approx(-0.04)
    assert not row["hit_target"]


def test_earliest_day_wins_when_several_would_hit():
    """Day 1 touches the target and day 2 gaps far above it. The trade is already
    closed on day 1, so the day-2 gap must not be harvested."""
    df = frame([
        {"open": 100, "high": 100, "low": 100, "close": 100},
        {"open": 100, "high": 101.5, "low": 99, "close": 101},
        {"open": 110, "high": 112, "low": 109, "close": 111},
        {"open": 111, "high": 112, "low": 110, "close": 111},
    ])
    tab = forward_table(ft.adjusted(df), df["close"], horizon=3)
    assert tab.iloc[0]["days_held"] == 1
    assert tab.iloc[0]["exit_kind"] == "target"
    assert tab.iloc[0]["gross_ret"] == pytest.approx(0.01)


def test_trade_running_past_the_data_is_dropped_not_truncated():
    """Truncating an unfinished trade to the last available close silently biases the
    tail. It must leave the sample instead."""
    df = frame([
        {"open": 100, "high": 100, "low": 100, "close": 100},
        {"open": 100, "high": 100, "low": 100, "close": 100},
    ])
    tab = forward_table(ft.adjusted(df), df["close"], horizon=3)
    assert tab.empty


def test_mae_is_measured_only_up_to_the_exit():
    """A crash two days after the target already filled is not this trade's drawdown."""
    df = frame([
        {"open": 100, "high": 100, "low": 100, "close": 100},
        {"open": 100, "high": 101.5, "low": 99.5, "close": 101},
        {"open": 60, "high": 61, "low": 55, "close": 56},
        {"open": 56, "high": 57, "low": 50, "close": 51},
    ])
    tab = forward_table(ft.adjusted(df), df["close"], horizon=3)
    assert tab.iloc[0]["mae"] == pytest.approx(-0.005)


def test_control_leg_exits_at_the_next_open_with_no_target():
    df = frame([
        {"open": 100, "high": 100, "low": 100, "close": 100},
        {"open": 102, "high": 110, "low": 101, "close": 109},
    ])
    tab = control_table(ft.adjusted(df), df["close"])
    assert tab.iloc[0]["exit_kind"] == "next_open"
    assert tab.iloc[0]["gross_ret"] == pytest.approx(0.02)


# ----------------------------------------------------------------- splits

def test_split_does_not_manufacture_a_previous_low_signal():
    """A 2:1 split between two sessions prints a -50% 'distance to yesterday's low'
    on raw prices. Adjusted features must show the true ~0%."""
    idx = pd.date_range("2024-01-02", periods=2, freq="B")
    df = pd.DataFrame({
        "open": [200.0, 100.0], "high": [202.0, 101.0],
        "low": [198.0, 99.0], "close": [200.0, 100.0],
        "volume": [1e8, 1e8], "adjclose": [100.0, 100.0],
    }, index=idx)
    f = ft.daily_features(df)
    assert f["prev_low_distance_pct"].iloc[1] == pytest.approx(1.0101, abs=0.01)
    raw = (df["close"].iloc[1] / df["low"].iloc[0] - 1) * 100
    assert raw < -49


# ----------------------------------------------------------------- gates

def test_a_missing_feature_never_passes_a_gate():
    """NaN must be False. On the daily path late_return_pct is always NaN, and a NaN
    that evaluated True would silently disable the gate."""
    feats = pd.DataFrame({
        "prev_low_distance_pct": [np.nan], "day_return_pct": [np.nan],
        "late_return_pct": [np.nan], "close_location_value": [np.nan],
        "range_capacity_pct": [np.nan], "sector_relative_pct": [np.nan],
    })
    c = st.conditions(feats)
    assert not c.any().any()


def test_control_rung_selects_everything():
    feats = pd.DataFrame({
        "prev_low_distance_pct": [5.0], "day_return_pct": [3.0],
        "late_return_pct": [2.0], "close_location_value": [0.9],
        "range_capacity_pct": [0.1], "sector_relative_pct": [2.0],
    })
    c = st.conditions(feats)
    assert st.rung_mask(c, []).all()
    assert not st.rung_mask(c, ["prevlow"]).any()


def test_prevlow_band_is_two_sided():
    """Far BELOW the previous low is not 'better' — the spec bands it on both sides."""
    feats = pd.DataFrame({
        "prev_low_distance_pct": [-5.0, 0.5, 3.0],
        "day_return_pct": [-2.0] * 3, "late_return_pct": [-1.0] * 3,
        "close_location_value": [0.1] * 3, "range_capacity_pct": [2.0] * 3,
        "sector_relative_pct": [-1.0] * 3,
    })
    assert list(st.conditions(feats)["prevlow"]) == [False, True, False]


# ----------------------------------------------------------------- look-ahead

def test_intraday_features_ignore_bars_after_the_signal():
    """The whole anti-look-ahead contract: mutating the 15:55 and 16:00 bars must not
    move a single 15:50 feature."""
    def session(day: str, last_high: float) -> pd.DataFrame:
        times = pd.date_range(f"{day} 09:30", f"{day} 15:55", freq="5min", tz="America/New_York")
        n = len(times)
        return pd.DataFrame({
            "open": [100.0] * n, "high": [100.5] * (n - 1) + [last_high],
            "low": [99.5] * n, "close": [100.0] * n, "volume": [1e6] * n,
        }, index=times)

    daily = frame([
        {"open": 100, "high": 101, "low": 99, "close": 100},
        {"open": 100, "high": 101, "low": 99, "close": 100},
    ])
    daily.index = pd.DatetimeIndex(["2024-01-02", "2024-01-03"])

    a = ft.intraday_features(session("2024-01-03", 100.5), daily)
    b = ft.intraday_features(session("2024-01-03", 999.0), daily)
    cols = ["prev_low_distance_pct", "day_return_pct", "late_return_pct",
            "close_location_value", "entry_ref"]
    pd.testing.assert_frame_equal(a[cols], b[cols])


def test_range_capacity_excludes_today():
    """Today's own range would be look-ahead at 15:50 — the median is of prior sessions."""
    rows = [{"open": 100, "high": 100.5, "low": 99.5, "close": 100} for _ in range(25)]
    rows[-1] = {"open": 100, "high": 200.0, "low": 50.0, "close": 100}
    df = frame(rows)
    f = ft.daily_features(df)
    assert f["range_capacity_pct"].iloc[-1] == pytest.approx(1.0, abs=0.05)


# ----------------------------------------------------------------- costs

def test_costs_are_charged_on_both_sides():
    g = pd.Series([0.01])
    assert ex.apply_costs(g, 5.0).iloc[0] == pytest.approx(0.01 - 0.001)


# ----------------------------------------------------------------- cross-source integrity

def test_price_basis_mismatch_is_dropped_not_averaged_in():
    """A spin-off or reverse split that two providers adjust differently prices a trade
    at up to 9.6x its real entry, booking a fake -90%. Measured on the pilot: 48 bad
    rows of 3,357 dragged the CONTROL from about +5 bps to -103. Rows where the minute
    tape and the daily bar disagree must leave the sample."""
    from backtesting.eod_1pct_reversal.run_alpaca import drop_price_basis_mismatches

    m = pd.DataFrame({
        "price":      [100.0, 100.0, 100.0, 100.0],
        "fill_16:00": [100.02, 99.98, 960.0, 167.0],   # two healthy, two corporate-action
        "fill_15:55": [100.01, 99.99, 959.0, 166.0],
    })
    out = drop_price_basis_mismatches(m)
    assert len(out) == 2
    assert out["fill_16:00"].tolist() == [100.02, 99.98]


def test_integrity_guard_falls_back_to_1555_when_1600_is_missing():
    """Roughly a third of ticker-sessions have no 16:00 bar. Requiring one would throw
    away good rows, so the check falls back rather than dropping."""
    from backtesting.eod_1pct_reversal.run_alpaca import drop_price_basis_mismatches

    m = pd.DataFrame({
        "price":      [100.0, 100.0],
        "fill_16:00": [np.nan, np.nan],
        "fill_15:55": [100.5, 940.0],
    })
    out = drop_price_basis_mismatches(m)
    assert len(out) == 1
    assert out["fill_15:55"].iloc[0] == 100.5
