"""Paginated OHLCV fetch via ccxt binanceusdm with a local parquet cache.

Network is NEVER called at import time. ``fetch_ohlcv`` is only invoked
from ``run.py`` under ``if __name__ == '__main__'`` (or by the live
orchestrator). Tests must not touch this module's network path.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import pandas as pd

_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")

_TF_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000,
    "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
}


def _cache_path(symbol: str, timeframe: str, since: int, until: int) -> str:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    safe = symbol.replace("/", "_").replace(":", "_")
    return os.path.join(_CACHE_DIR, f"{safe}_{timeframe}_{since}_{until}.parquet")


def _to_ms(ts) -> int:
    t = pd.Timestamp(ts)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return int(t.timestamp() * 1000)


def fetch_ohlcv(symbol: str, timeframe: str, since, until,
                exchange=None, limit: int = 1000,
                use_cache: bool = True) -> pd.DataFrame:
    """Fetch paginated OHLCV [since, until) as a datetime-indexed DataFrame.

    Columns: open, high, low, close, volume. Cached to parquet (falls
    back to CSV if pyarrow/fastparquet is unavailable).
    """
    since_ms = _to_ms(since)
    until_ms = _to_ms(until)
    cpath = _cache_path(symbol, timeframe, since_ms, until_ms)

    if use_cache and os.path.exists(cpath):
        try:
            return pd.read_parquet(cpath)
        except Exception:
            csv = cpath.replace(".parquet", ".csv")
            if os.path.exists(csv):
                return pd.read_csv(csv, index_col=0, parse_dates=True)

    if exchange is None:
        import ccxt  # imported lazily so tests never need network/creds
        exchange = ccxt.binanceusdm({"enableRateLimit": True})

    tf_ms = _TF_MS.get(timeframe)
    if tf_ms is None:
        raise ValueError(f"unsupported timeframe {timeframe}")

    rows = []
    cursor = since_ms
    while cursor < until_ms:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe,
                                     since=cursor, limit=limit)
        if not batch:
            break
        rows.extend(batch)
        last = batch[-1][0]
        nxt = last + tf_ms
        if nxt <= cursor:
            break
        cursor = nxt
        if len(batch) < limit:
            break
        time.sleep(getattr(exchange, "rateLimit", 200) / 1000.0)

    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df[df["ts"] < until_ms].drop_duplicates(subset="ts")
    df.index = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df.index.name = "timestamp"

    if use_cache:
        try:
            df.to_parquet(cpath)
        except Exception:
            df.to_csv(cpath.replace(".parquet", ".csv"))
    return df
