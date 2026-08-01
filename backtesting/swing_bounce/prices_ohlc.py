"""Daily OHLC price loader for the swing backtest (the trade sim needs high/low, not just close).

Mirrors ``value_quality/prices.py`` Yahoo access but KEEPS open/high/low/close/volume. Network is
touched only by ``fetch_ohlc`` (run-path); ``load_ohlc`` and ``normalize_ohlc`` are offline. No Stooq
fallback here (Stooq is non-functional from this env and doesn't cleanly give OHLC) — a Yahoo miss
goes to the missing-log.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import pandas as pd
import requests

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh) swing-bounce research"}
_COLS = ["open", "high", "low", "close", "volume"]


def normalize_ohlc(raw: dict) -> pd.DataFrame:
    """Build an OHLC DataFrame (UTC DatetimeIndex, columns open/high/low/close/volume) from a dict of
    parallel arrays ``{timestamp, open, high, low, close, volume}``. Rows with a null close drop."""
    idx = pd.to_datetime(raw["timestamp"], unit="s", utc=True)
    df = pd.DataFrame({c: raw.get(c) for c in _COLS}, index=idx)
    df = df[df["close"].notna()]
    return df.astype(float)


def _to_epoch(ts) -> int:
    t = pd.Timestamp(ts)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return int(t.timestamp())


def _cache_path(ticker: str) -> str:
    os.makedirs(os.path.join(_CACHE, "ohlc"), exist_ok=True)
    return os.path.join(_CACHE, "ohlc", f"{ticker.upper()}.csv")


def fetch_ohlc(ticker: str, start, end, use_cache: bool = True) -> Optional[pd.DataFrame]:
    p = _cache_path(ticker)
    if use_cache and os.path.exists(p):
        return pd.read_csv(p, index_col=0, parse_dates=True)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?period1={_to_epoch(start)}&period2={_to_epoch(end)}&interval=1d")
    for i in range(4):
        try:
            r = requests.get(url, headers=_UA, timeout=30)
            r.raise_for_status()
            res = r.json().get("chart", {}).get("result")
            if not res:
                break
            res0 = res[0]
            ts = res0.get("timestamp")
            quote_blocks = res0.get("indicators", {}).get("quote", [])
            quote = quote_blocks[0] if quote_blocks else {}
            if not ts or not quote.get("close"):
                break
            df = normalize_ohlc({"timestamp": ts, "open": quote.get("open"),
                                 "high": quote.get("high"), "low": quote.get("low"),
                                 "close": quote.get("close"), "volume": quote.get("volume")})
            if df.empty:
                break
            if use_cache:
                df.to_csv(p)
            time.sleep(1.5)
            return df
        except Exception:
            time.sleep(1.5 * (i + 1))
    os.makedirs(_CACHE, exist_ok=True)
    with open(os.path.join(_CACHE, "missing_ohlc.txt"), "a") as f:
        f.write(ticker.upper() + "\n")
    return None


def load_ohlc(ticker: str) -> pd.DataFrame:
    p = _cache_path(ticker)
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df
