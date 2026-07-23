"""Session / kill-zone gating for the TJR 4X backtest.

TJR teaches trading specific sessions (London, New York) and their ICT
"kill zones". Crypto trades 24/7, so this is an imported concept — we test
whether restricting entries to session windows recovers an edge.

Windows are expressed in **UTC hours** as half-open ``[start, end)`` ranges.
A trade is kept if its ``entry_time`` (setup-confirmation time; binance data
is UTC) falls inside any window.

LIMITATION: windows are fixed UTC and do NOT track US/UK daylight-saving
shifts — a known approximation (routed to OPEN_QUESTIONS). Kept simple and
deterministic for a first pass.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

# Preset session sets. Each is a list of half-open [start_hour, end_hour) UTC windows.
PRESETS: Dict[str, List[Tuple[int, int]]] = {
    "none": [],                                  # baseline — no gating (24/7)
    "london": [(7, 10)],                         # London session open ~07:00-10:00 UTC
    "ny_am": [(12, 15)],                         # New York AM ~12:00-15:00 UTC
    "london+ny_am": [(7, 10), (12, 15)],         # the two classic windows
    "kill_zones": [(7, 9), (12, 14)],            # tighter ICT London + NY kill zones
    "ny_full": [(13, 20)],                       # full NY cash session
}


def in_sessions(ts, windows: Sequence[Tuple[int, int]]) -> bool:
    """True if timestamp's UTC hour is inside any [start, end) window.

    Empty ``windows`` means "no gating" -> always True.
    """
    if not windows:
        return True
    h = ts.hour
    return any(start <= h < end for start, end in windows)


def filter_by_session(trades: List, windows: Sequence[Tuple[int, int]]) -> List:
    """Keep only trades whose entry_time falls inside a session window."""
    if not windows:
        return list(trades)
    return [t for t in trades if in_sessions(t.entry_time, windows)]
