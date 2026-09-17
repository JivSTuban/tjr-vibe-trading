"""Spec filter F — "no earnings after today's close or before the next-morning exit".

Source is Nasdaq's public calendar API (keyless, historical, and it carries the
release-time flag). Finnhub's calendar returns nothing before ~2 years back on the
free tier and FMP's is paywalled, so Nasdaq is the only free source that covers
2014-2026 *with* BMO/AMC timing.

The timing flag is load-bearing, not a nicety. The strategy holds from 3:55 PM to
9:35 AM the next morning. That window contains:
  - tonight's AFTER-MARKET (AMC) release for the signal day, and
  - tomorrow's BEFORE-MARKET (BMO) release.
It does NOT contain tomorrow's AMC release. Excluding an entire +/-1 day band would
throw away good signals; excluding the wrong side would leave earnings gaps in the
book, which §14 says is exactly how an overnight strategy dies.

Network is touched only by ``fetch_calendar``. ``in_exclusion_window`` is pure.
"""
from __future__ import annotations

import json
import os
import time
from typing import Iterable, Optional

import pandas as pd
import requests

_CACHE = os.path.join(os.path.dirname(__file__), ".cache", "earnings")
_URL = "https://api.nasdaq.com/api/calendar/earnings"
_UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

# Nasdaq's `time` field values, mapped to whether the release lands in our hold window.
_AMC = {"time-after-hours", "time-after-market", "amc"}
_BMO = {"time-pre-market", "time-before-open", "bmo"}


def _cache_path(day: str) -> str:
    os.makedirs(_CACHE, exist_ok=True)
    return os.path.join(_CACHE, f"{day}.json")


def fetch_calendar(day: str, use_cache: bool = True, pause: float = 0.25,
                   session: Optional[requests.Session] = None) -> list[dict]:
    """Fetch one session's earnings calendar. Returns [] when Nasdaq has no rows.

    Results are cached per day, including empty days, so a 3,000-session backtest
    hits the network once per calendar date ever.
    """
    path = _cache_path(day)
    if use_cache and os.path.exists(path):
        try:
            with open(path) as fh:
                return json.load(fh)
        except Exception:
            pass
    get = (session or requests).get
    rows: list[dict] = []
    try:
        r = get(_URL, params={"date": day}, headers=_UA, timeout=30)
        if r.status_code == 200:
            data = r.json().get("data") or {}
            rows = [
                {"symbol": str(x.get("symbol", "")).strip().upper(),
                 "time": str(x.get("time", "")).strip().lower()}
                for x in (data.get("rows") or [])
                if x.get("symbol")
            ]
    except Exception:
        rows = []
    with open(path, "w") as fh:
        json.dump(rows, fh)
    time.sleep(pause)
    return rows


def build_index(calendars: dict[str, list[dict]]) -> pd.DataFrame:
    """Pure: {date -> rows} into a tidy (date, symbol, time) frame."""
    recs = [
        {"date": pd.Timestamp(day), "symbol": r["symbol"], "time": r.get("time", "")}
        for day, rows in calendars.items()
        for r in rows
    ]
    if not recs:
        return pd.DataFrame(columns=["date", "symbol", "time"])
    return pd.DataFrame(recs).drop_duplicates(["date", "symbol"])


def blocked_pairs(index: pd.DataFrame, sessions: pd.DatetimeIndex) -> set[tuple[pd.Timestamp, str]]:
    """Pure: the set of (signal_date, symbol) pairs filter F must reject.

    A signal on session ``d`` (exit the morning of the next session ``d+1``) is blocked
    when the symbol reports:
      - on ``d`` after the close (AMC), or
      - on ``d+1`` before the open (BMO).
    A *known* BMO print on ``d`` itself is already in the signal-day close and is not a
    forward shock, so it does not block — that is the case a naive +/-1 day band gets
    wrong, and it is why we read the time flag at all.

    IMPORTANT (verified 2026-09-15): Nasdaq populates the time flag only for recent
    rows — every historical event comes back ``time-not-supplied``. When the time is
    unknown we therefore block BOTH sides, because an unknown-time report on ``d``
    could be AMC and land squarely inside the hold. Without this, an AMC reporter like
    AAPL would be held straight through its own release, which is precisely the §14
    left-tail disaster the filter exists to prevent. The cost is some over-exclusion on
    the signal day; that is the right direction to be wrong in.
    """
    if index.empty:
        return set()
    sessions = pd.DatetimeIndex(sorted(sessions))
    nxt = {d: sessions[i + 1] for i, d in enumerate(sessions[:-1])}
    prv = {v: k for k, v in nxt.items()}

    blocked: set[tuple[pd.Timestamp, str]] = set()
    for date, sym, when in index[["date", "symbol", "time"]].itertuples(index=False):
        w = (when or "").lower()
        known = (w in _AMC) or (w in _BMO)
        if (w in _AMC or not known) and date in nxt:
            blocked.add((date, sym))                      # tonight, after our entry
        if (w in _BMO or not known) and date in prv:
            blocked.add((prv[date], sym))                 # tomorrow morning, before our exit
    return blocked


def in_exclusion_window(blocked: set, date, symbol: str) -> bool:
    """Pure convenience wrapper used by the strategy layer."""
    return (pd.Timestamp(date), symbol.upper()) in blocked


def fetch_range(sessions: Iterable, use_cache: bool = True,
                progress: Optional[callable] = None, workers: int = 6) -> dict[str, list[dict]]:
    """Fetch the calendar for every session date. ~250 calls/year, cached forever.

    Fetched with a small thread pool because this is ~3,200 independent requests and
    serially it dominates the whole run. Concurrency is kept low deliberately: Nasdaq
    is a courtesy endpoint with no published rate limit, and hammering it would get the
    filter silently zeroed out rather than erroring loudly.
    """
    from concurrent.futures import ThreadPoolExecutor

    days = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in sessions]
    out: dict[str, list[dict]] = {}
    done = 0

    def one(day: str) -> tuple[str, list[dict]]:
        # Each worker gets its own Session: requests.Session is not thread-safe.
        return day, fetch_calendar(day, use_cache=use_cache, session=requests.Session())

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for day, rows in pool.map(one, days):
            out[day] = rows
            done += 1
            if progress and done % 200 == 0:
                progress(done, len(days))
    return out
