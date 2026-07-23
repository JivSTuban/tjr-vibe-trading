"""Tests for session/kill-zone gating."""

import pandas as pd

from backtesting.tjr_4x.sessions import in_sessions, filter_by_session, PRESETS


class _T:
    """Minimal trade stub with an entry_time."""
    def __init__(self, hour):
        self.entry_time = pd.Timestamp(f"2025-03-04 {hour:02d}:30:00")


def test_empty_windows_keeps_everything():
    trades = [_T(h) for h in range(24)]
    assert filter_by_session(trades, []) == trades
    assert in_sessions(pd.Timestamp("2025-03-04 03:00"), []) is True


def test_half_open_window_boundaries():
    # [7, 10) keeps 7,8,9 — excludes 10
    assert in_sessions(pd.Timestamp("2025-03-04 07:00"), [(7, 10)]) is True
    assert in_sessions(pd.Timestamp("2025-03-04 09:59"), [(7, 10)]) is True
    assert in_sessions(pd.Timestamp("2025-03-04 10:00"), [(7, 10)]) is False
    assert in_sessions(pd.Timestamp("2025-03-04 06:59"), [(7, 10)]) is False


def test_filter_by_london_ny():
    trades = [_T(h) for h in range(24)]  # one per hour
    kept = filter_by_session(trades, PRESETS["london+ny_am"])  # (7,10)+(12,15)
    hours = sorted(t.entry_time.hour for t in kept)
    assert hours == [7, 8, 9, 12, 13, 14]


def test_presets_are_disjoint_or_ordered_within():
    for name, windows in PRESETS.items():
        for start, end in windows:
            assert 0 <= start < end <= 24, f"bad window in {name}: {(start, end)}"
