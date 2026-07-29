"""Paginated funding-rate history via ccxt binanceusdm, cached to CSV.

Uses ``fetch_funding_rate_history`` (SETTLED rates) — NOT ``fetch_funding_rate``
(which returns the estimated/upcoming rate, the trap flagged in the tooling
research). Public endpoint, no API keys — same access path as the OHLCV cache
in ``tjr_4x/data.py``. Network is only touched from ``fetch_funding`` under a
``__main__``/run path; ``load_funding`` reads the cache only.
"""

from __future__ import annotations

import glob
import os
from typing import Optional

import pandas as pd

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")


def _cache_path(symbol: str, since_ms: int, until_ms: int) -> str:
    os.makedirs(_CACHE, exist_ok=True)
    safe = symbol.replace("/", "_").replace(":", "_")
    return os.path.join(_CACHE, f"{safe}_funding_{since_ms}_{until_ms}.csv")


def _to_ms(ts) -> int:
    t = pd.Timestamp(ts)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return int(t.timestamp() * 1000)


def _fetch_page(exchange, symbol, cursor, attempts=4):
    """Unified fetch_funding_rate_history with retries (geo/451/transient)."""
    import time
    last = None
    for i in range(attempts):
        try:
            return exchange.fetch_funding_rate_history(symbol, since=cursor, limit=1000)
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def fetch_funding(symbol: str, since, until, exchange="gate",
                  use_cache: bool = True) -> pd.DataFrame:
    """Fetch settled funding-rate history [since, until) → DataFrame.

    Columns: funding_rate (float). DatetimeIndex (UTC), one row per funding
    settlement (8h on majors). Cached to CSV. Uses ccxt's UNIFIED
    fetch_funding_rate_history (Binance USDⓈ-M is geo-blocked here → default
    venue is 'gate', which allows a 180-day lookback). Funding rates are near-
    identical across venues (arbitrage-pinned), so venue choice is minor.
    """
    since_ms, until_ms = _to_ms(since), _to_ms(until)
    cpath = _cache_path(symbol, since_ms, until_ms)
    if use_cache and os.path.exists(cpath):
        return pd.read_csv(cpath, index_col=0, parse_dates=True)

    if isinstance(exchange, str):
        import ccxt
        exchange = getattr(ccxt, exchange)({"enableRateLimit": True})

    rows, cursor = [], since_ms
    while cursor < until_ms:
        batch = _fetch_page(exchange, symbol, cursor)
        if not batch:
            break
        rows.extend(batch)
        last = int(batch[-1]["timestamp"])
        if last + 1 <= cursor:
            break
        cursor = last + 1
        if len(batch) < 2:
            break

    if not rows:
        return pd.DataFrame(columns=["funding_rate"])
    df = pd.DataFrame([(int(r["timestamp"]), float(r["fundingRate"])) for r in rows],
                      columns=["ts", "funding_rate"]).drop_duplicates(subset="ts")
    df = df[df["ts"] < until_ms]
    df.index = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df[["funding_rate"]].astype(float).sort_index()
    df.index.name = "timestamp"
    if use_cache:
        df.to_csv(cpath)
    return df


def load_funding(symbol_glob: str) -> pd.DataFrame:
    """Read the NEWEST cached funding CSV matching ``symbol_glob`` (no network)."""
    matches = sorted(glob.glob(os.path.join(_CACHE, symbol_glob)),
                     key=os.path.getmtime)
    if not matches:
        raise FileNotFoundError(f"no cached funding CSV matching {symbol_glob!r}")
    return pd.read_csv(matches[-1], index_col=0, parse_dates=True).sort_index()
