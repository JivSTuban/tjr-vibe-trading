"""Bar-indexing tests for the exact-spec intraday path.

Yahoo labels a 5m bar by its START time. If "the 3:50 PM price" accidentally reads the
15:50 bar's CLOSE, the signal would contain 5 minutes of future information and the
whole anti-lookahead premise of spec §3 would be void. These tests pin the convention.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.eod_pressure_reversal import intraday


def _session(date="2026-09-08", n=78, start_price=100.0):
    """A full regular session of 5m bars, 09:30 .. 15:55 inclusive (78 bars)."""
    idx = pd.date_range(f"{date} 09:30", periods=n, freq="5min", tz="America/New_York")
    px = np.linspace(start_price, start_price, n)
    return pd.DataFrame(
        {"open": px, "high": px, "low": px, "close": px, "volume": np.ones(n) * 1000},
        index=idx,
    )


def test_bar_lookup_uses_bar_start_time():
    s = _session()
    s.loc[s.index.strftime("%H:%M") == "15:50", "open"] = 97.9
    s.loc[s.index.strftime("%H:%M") == "15:50", "close"] = 95.0   # must NOT be read
    assert intraday._at(s, "15:50") == pytest.approx(97.9)


def test_intraday_high_stops_before_the_signal_bar():
    """High "through 3:50" must exclude the 15:50 bar itself — that bar is the future."""
    s = _session()
    s.loc[s.index.strftime("%H:%M") == "11:00", "high"] = 101.0
    s.loc[s.index.strftime("%H:%M") == "15:50", "high"] = 999.0   # future spike
    f = intraday.exact_session_features(s, prev_close=100.0)
    assert f["dd_high_exact"] == pytest.approx(100.0 / 101.0 - 1.0, abs=1e-9)


def test_late_volume_window_is_1530_to_1550_exclusive():
    s = _session()
    key = s.index.strftime("%H:%M")
    s.loc[key == "15:25", "volume"] = 9e6      # just before the window
    s.loc[key == "15:30", "volume"] = 1e6
    s.loc[key == "15:35", "volume"] = 1e6
    s.loc[key == "15:40", "volume"] = 1e6
    s.loc[key == "15:45", "volume"] = 1e6
    s.loc[key == "15:50", "volume"] = 9e6      # the signal bar, not in the window
    f = intraday.exact_session_features(s, prev_close=100.0)
    assert f["late_vol"] == pytest.approx(4e6)


def test_spec_example_reproduces_on_intraday_bars():
    """Spec §15: prev close 100, high 101, 15:30 = 98.70, 15:50 = 97.90."""
    s = _session()
    key = s.index.strftime("%H:%M")
    s.loc[key == "10:00", "high"] = 101.0
    s.loc[key == "15:30", "open"] = 98.70
    s.loc[key == "15:50", "open"] = 97.90
    f = intraday.exact_session_features(s, prev_close=100.0)
    assert f["day_ret_exact"] == pytest.approx(-0.021, abs=1e-6)
    assert f["late_ret_exact"] == pytest.approx(97.90 / 98.70 - 1, abs=1e-6)
    assert f["dd_high_exact"] == pytest.approx(97.90 / 101.0 - 1, abs=1e-6)


def test_entry_is_the_1555_bar_not_the_close():
    s = _session()
    key = s.index.strftime("%H:%M")
    s.loc[key == "15:55", "open"] = 98.0
    s.loc[key == "15:55", "close"] = 97.0      # the official close
    f = intraday.exact_session_features(s, prev_close=100.0)
    assert f["entry_1555"] == pytest.approx(98.0)
    assert f["close"] == pytest.approx(97.0)
    # entering at the close is 1.03% cheaper here -> the daily run's optimism
    assert f["entry_1555"] > f["close"]


def test_next_morning_marks_are_the_three_spec_variants():
    s = _session()
    key = s.index.strftime("%H:%M")
    s.loc[key == "09:30", "open"] = 98.5
    s.loc[key == "09:35", "open"] = 98.9
    s.loc[key == "10:00", "open"] = 99.4
    m = intraday.next_morning_prices(s)
    assert (m["exit_open"], m["exit_0935"], m["exit_1000"]) == pytest.approx((98.5, 98.9, 99.4))


def test_extended_hours_bars_are_excluded_from_sessions():
    s = _session()
    pre = pd.date_range("2026-09-08 07:00", periods=6, freq="5min", tz="America/New_York")
    post = pd.date_range("2026-09-08 16:00", periods=6, freq="5min", tz="America/New_York")
    extra = pd.DataFrame(
        {"open": 50.0, "high": 50.0, "low": 50.0, "close": 50.0, "volume": 10.0},
        index=pre.union(post),
    )
    df = pd.concat([s, extra]).sort_index()
    sessions = intraday.session_frames(df)
    bars = list(sessions.values())[0]
    hhmm = bars.index.strftime("%H:%M")
    assert hhmm.min() >= "09:30" and hhmm.max() < "16:00"
    assert 50.0 not in bars["close"].to_numpy()
