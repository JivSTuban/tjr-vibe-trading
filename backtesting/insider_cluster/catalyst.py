"""Earnings-surprise catalyst overlay (Finnhub) — the one small-cap catalyst labelable at scale.

The research question is whether an insider CLUSTER buy adds alpha ON TOP OF a catalyst, or whether
the catalyst does all the work. FDA/contract catalysts can't be labeled programmatically at scale, so
we use the tractable proxy: a recent positive EARNINGS SURPRISE (PEAD). Finnhub's ``stock/earnings``
returns quarterly actual/estimate/surprisePercent keyed by fiscal-period END date; the announcement is
~4-6 weeks later, so we treat a beat as "recent/near" an event if its period end is within a lookback
window and approximate the announcement date as period_end + ``announce_lag_days``.

Network only in ``fetch_earnings`` (run-path); ``had_beat_near`` / ``beat_events`` are offline.
"""
from __future__ import annotations

import json
import os
import subprocess
import time

import pandas as pd
import requests

_CACHE = os.path.join(os.path.dirname(__file__), ".cache", "earnings")
_ANNOUNCE_LAG = 35            # crude period-end -> announcement-date offset (days)


def _key() -> str:
    return subprocess.check_output(
        ["security", "find-generic-password", "-s", "stock-scan-finnhub", "-a", "api", "-w"]
    ).decode().strip()


def fetch_earnings(ticker: str, token: str, use_cache: bool = True) -> list[dict]:
    os.makedirs(_CACHE, exist_ok=True)
    p = os.path.join(_CACHE, f"{ticker.upper()}.json")
    if use_cache and os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    url = f"https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&token={token}"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            data = r.json() or []
            with open(p, "w") as f:
                json.dump(data, f)
            time.sleep(1.1)          # free tier ~60/min
            return data
        except Exception:            # noqa: BLE001
            time.sleep(1.5 * (attempt + 1))
    with open(p, "w") as f:          # cache the empty so we don't re-hit
        json.dump([], f)
    return []


def load_earnings(ticker: str) -> list[dict]:
    p = os.path.join(_CACHE, f"{ticker.upper()}.json")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return json.load(f)


def _announce_dates(ticker: str, min_surprise: float = 0.0) -> list[pd.Timestamp]:
    """Approx announcement dates of quarters that BEAT (surprisePercent > min_surprise)."""
    out = []
    for e in load_earnings(ticker):
        sp = e.get("surprisePercent")
        per = e.get("period")
        if sp is None or per is None or sp <= min_surprise:
            continue
        try:
            out.append(pd.Timestamp(per) + pd.Timedelta(days=_ANNOUNCE_LAG))
        except Exception:            # noqa: BLE001
            continue
    return sorted(out)


def had_beat_near(ticker: str, event_date, back_days: int = 90, fwd_days: int = 5,
                  min_surprise: float = 0.0) -> bool:
    """True if an earnings BEAT was announced shortly before (<= back_days) or just after
    (<= fwd_days) the insider event — i.e. the cluster buy coincides with a positive PEAD catalyst."""
    ed = pd.Timestamp(event_date)
    for a in _announce_dates(ticker, min_surprise):
        if -fwd_days <= (ed - a).days <= back_days:
            return True
    return False


def beat_events(ticker: str, min_surprise: float = 0.0) -> list[pd.Timestamp]:
    """Catalyst-ONLY event dates for the counterfactual arm: approx announcement date of each beat."""
    return _announce_dates(ticker, min_surprise)
