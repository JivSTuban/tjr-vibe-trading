"""Alpaca minute bars — the data source that makes the late-pressure gate testable.

The first run of this study could only measure the spec's `late_return` gate (the
15:30 -> 15:50 move) on 57 days, because Yahoo serves 5-minute bars for the trailing
60 days and nothing else free goes deeper. Alpaca's Basic plan is free and serves
**minute bars back to 2016**; its only restriction is the most recent 15 minutes,
which is irrelevant to a historical study. That converts the one open question in
FINDINGS.md from unanswerable to answerable.

FETCH STRATEGY. The naive shape — loop tickers, pull 10 years each — is ~500M bars.
Instead we exploit two facts:

  1. The strategy only fires on ~30 candidates a day, and those candidates are
     identified from DAILY bars we already have cached. So we only need minute data
     for (date, ticker) pairs that actually reached the gate.
  2. Alpaca's bars endpoint is multi-symbol. One request covers every candidate on a
     given date.

That turns the pull into roughly one request per session instead of one per ticker,
and we discard everything outside 15:25-16:00 ET on receipt.

RATE LIMIT: 200 requests/min on Basic. The client self-throttles below that.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Iterable

import pandas as pd
import requests

BARS_URL = "https://data.alpaca.markets/v2/stocks/bars"
_CACHE = os.path.join(os.path.dirname(__file__), ".cache", "alpaca_min")

# Only the tail of the session matters: 15:25 gives a little room before the 15:30
# late-window mark, and 16:00 closes it.
KEEP_FROM = "15:25"
KEEP_TO = "16:00"


def _keychain(account: str) -> str | None:
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-s", "claude-alpaca", "-a", account, "-w"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return None


def credentials() -> tuple[str, str]:
    """Env first, then Keychain. Never hard-code a key in this repo."""
    k = os.environ.get("ALPACA_API_KEY") or _keychain("ALPACA_API_KEY")
    s = os.environ.get("ALPACA_SECRET_KEY") or _keychain("ALPACA_SECRET_KEY")
    if not k or not s:
        raise SystemExit("No Alpaca credentials in env or Keychain (service claude-alpaca)")
    return k, s


def headers() -> dict:
    k, s = credentials()
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}


def normalize_bars(payload: dict) -> pd.DataFrame:
    """Pure: Alpaca multi-symbol bars JSON -> tidy frame in ET.

    Alpaca stamps a minute bar with the LEFT edge of its interval, same convention as
    the Yahoo 5m loader this study already uses. So the "15:50 price" is the OPEN of
    the 15:50 bar — a price that exists at 15:50:00 and involves no look-ahead.
    """
    rows = []
    for sym, bars in (payload.get("bars") or {}).items():
        for b in bars:
            rows.append({
                "ticker": sym, "ts": b["t"], "open": b["o"], "high": b["h"],
                "low": b["l"], "close": b["c"], "volume": b["v"], "trades": b.get("n"),
            })
    if not rows:
        return pd.DataFrame(columns=["ticker", "ts", "open", "high", "low", "close", "volume", "trades"])
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601").dt.tz_convert("America/New_York")
    return df


def fetch_day(symbols: Iterable[str], day: str, session: requests.Session | None = None,
              feed: str = "sip", pause: float = 0.31) -> pd.DataFrame:
    """Minute bars for many symbols on one session date, trimmed to the closing window.

    `feed="sip"` is the consolidated tape. Basic-plan accounts may query it for
    anything older than 15 minutes, which is every bar in a historical study; falling
    back to `iex` would silently swap in a single exchange carrying ~2.5% of volume
    and quietly change what "the price at 15:50" means.
    """
    get = (session or requests).get
    out, token = [], None
    syms = ",".join(sorted(set(symbols)))
    while True:
        params = {
            "symbols": syms, "timeframe": "1Min",
            # 19:15-21:10Z brackets 15:25-16:00 ET under BOTH offsets: EDT (UTC-4)
            # maps it to 15:15-17:10 and EST (UTC-5) to 14:15-16:10. Hard-coding a
            # single offset would silently drop the whole window for half the year.
            "start": f"{day}T19:15:00Z", "end": f"{day}T21:10:00Z",
            "limit": 10000, "adjustment": "split", "feed": feed,
        }
        if token:
            params["page_token"] = token
        r = get(BARS_URL, params=params, headers=headers(), timeout=60)
        if r.status_code == 429:
            time.sleep(5)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"{day}: HTTP {r.status_code} {r.text[:200]}")
        payload = r.json()
        out.append(normalize_bars(payload))
        token = payload.get("next_page_token")
        time.sleep(pause)
        if not token:
            break

    df = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    if df.empty:
        return df
    hm = df["ts"].dt.strftime("%H:%M")
    return df[(hm >= KEEP_FROM) & (hm <= KEEP_TO)].reset_index(drop=True)


def cache_path(day: str) -> str:
    os.makedirs(_CACHE, exist_ok=True)
    return os.path.join(_CACHE, f"{day}.csv")


def load_or_fetch(symbols: Iterable[str], day: str,
                  session: requests.Session | None = None) -> pd.DataFrame:
    """Cached per-session pull. A day with no bars caches empty so it is not refetched."""
    p = cache_path(day)
    if os.path.exists(p):
        try:
            df = pd.read_csv(p, parse_dates=["ts"])
            if not df.empty:
                df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("America/New_York")
            return df
        except Exception:
            pass
    df = fetch_day(symbols, day, session=session)
    df.to_csv(p, index=False)
    return df
