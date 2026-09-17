"""Price + universe data layer for the value+quality backtest.

Network is touched ONLY by fetch_prices (run-path). Pure functions
median_dollar_volume and passes_universe are the tested surface and contain
no I/O. fetch_prices tries Yahoo chart API first (adjclose preferred),
falls back to Stooq CSV, caches to .cache/prices/<ticker>.csv, and appends
to .cache/missing_prices.txt on total failure (survivorship log).
load_prices reads the cache CSV with no network.
"""
from __future__ import annotations

import os
import time
from io import StringIO
from typing import Optional

import pandas as pd
import requests

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")
_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Pure functions (no I/O — tested surface)
# ---------------------------------------------------------------------------

def median_dollar_volume(prices: pd.DataFrame, asof, window: int = 60) -> float:
    prior = prices[prices.index <= asof].iloc[-window:]
    return float((prior["close"] * prior["volume"]).median())


def passes_universe(price: float, mktcap: float, dollar_vol: float) -> bool:
    return bool(price >= 5.0 and mktcap >= 300e6 and dollar_vol >= 1e6)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _prices_cache_path(ticker: str) -> str:
    d = os.path.join(_CACHE, "prices")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{ticker}.csv")


def _missing_log_path() -> str:
    os.makedirs(_CACHE, exist_ok=True)
    return os.path.join(_CACHE, "missing_prices.txt")


def _log_missing(ticker: str) -> None:
    with open(_missing_log_path(), "a") as f:
        f.write(ticker + "\n")


def _to_epoch(ts) -> int:
    t = pd.Timestamp(ts)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return int(t.timestamp())


def _try_yahoo(ticker: str, start, end) -> Optional[pd.DataFrame]:
    """Fetch from Yahoo Finance chart API. Returns DataFrame or None."""
    p1 = _to_epoch(start)
    p2 = _to_epoch(end)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={p1}&period2={p2}&interval=1d"
    )
    for i in range(4):
        try:
            r = requests.get(url, headers=_UA, timeout=30)
            if r.status_code in (404, 400):
                return None
            r.raise_for_status()
            data = r.json()
            result = data.get("chart", {}).get("result")
            if not result:
                return None
            block = result[0]
            timestamps = block.get("timestamp", [])
            if not timestamps:
                return None
            indicators = block.get("indicators", {})
            adjclose_blocks = indicators.get("adjclose", [])
            quote_blocks = indicators.get("quote", [])
            # Delisted tickers return "quote": [] — guard before indexing so an
            # empty/delisted response falls straight through to Stooq/missing-log
            # instead of burning all 4 retries via IndexError -> except.
            quote = quote_blocks[0] if quote_blocks else {}
            adjclose = adjclose_blocks[0] if adjclose_blocks else {}
            if adjclose.get("adjclose"):
                closes = adjclose["adjclose"]
            else:
                closes = quote.get("close", [])
            if not closes:
                return None
            volumes = quote.get("volume", [None] * len(timestamps))
            idx = pd.to_datetime(timestamps, unit="s", utc=True)
            df = pd.DataFrame({"close": closes, "volume": volumes}, index=idx)
            df = df.dropna(subset=["close"])
            if df.empty:
                return None
            df["volume"] = df["volume"].fillna(0).astype(float)
            df.index.name = "date"
            return df
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def _try_stooq_v2(ticker: str) -> Optional[pd.DataFrame]:
    """Fetch from Stooq CSV (corrected). Returns DataFrame or None."""
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    for i in range(3):
        try:
            r = requests.get(url, headers=_UA, timeout=30)
            if r.status_code != 200:
                return None
            if b"No data" in r.content or len(r.content) < 50:
                return None
            raw = pd.read_csv(StringIO(r.text))
            # Stooq columns: Date, Open, High, Low, Close, Volume
            raw.columns = [c.strip().lower() for c in raw.columns]
            if "close" not in raw.columns or "date" not in raw.columns:
                return None
            raw["date"] = pd.to_datetime(raw["date"], utc=True)
            raw = raw.set_index("date").sort_index()
            vol_col = "volume" if "volume" in raw.columns else None
            df = pd.DataFrame({"close": raw["close"]})
            df["volume"] = raw[vol_col].fillna(0) if vol_col else 0.0
            df = df.dropna(subset=["close"])
            if df.empty:
                return None
            df.index.name = "date"
            return df
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


# ---------------------------------------------------------------------------
# Network I/O functions (run-path only — no network in tests)
# ---------------------------------------------------------------------------

def fetch_prices(
    ticker: str,
    start,
    end,
    use_cache: bool = True,
) -> Optional[pd.DataFrame]:
    """Fetch daily OHLCV for *ticker* over [start, end].

    Primary: Yahoo Finance chart API (adjclose preferred).
    Fallback: Stooq CSV.
    Cache: .cache/prices/<ticker>.csv
    On total failure: appends ticker to .cache/missing_prices.txt and returns None.

    Returns a DataFrame with UTC DatetimeIndex, columns: close, volume.
    Network-only function — do not call from tests.
    """
    cpath = _prices_cache_path(ticker)
    if use_cache and os.path.exists(cpath):
        df = pd.read_csv(cpath, index_col=0, parse_dates=True)
        if not df.index.tzinfo:
            df.index = df.index.tz_localize("UTC")
        return df

    # Primary: Yahoo
    df = _try_yahoo(ticker, start, end)

    # Fallback: Stooq
    if df is None:
        df = _try_stooq_v2(ticker)
        if df is not None:
            # Trim to requested range
            s = pd.Timestamp(start)
            e = pd.Timestamp(end)
            s = s.tz_localize("UTC") if s.tzinfo is None else s.tz_convert("UTC")
            e = e.tz_localize("UTC") if e.tzinfo is None else e.tz_convert("UTC")
            df = df[(df.index >= s) & (df.index <= e)]

    if df is None or df.empty:
        _log_missing(ticker)
        return None

    df.to_csv(cpath)
    return df


def load_prices(ticker: str) -> pd.Series:
    """Load cached close price series for *ticker* (no network).

    Returns a pd.Series with UTC DatetimeIndex named 'close'.
    Raises FileNotFoundError if the ticker has not been fetched yet.
    """
    cpath = _prices_cache_path(ticker)
    if not os.path.exists(cpath):
        raise FileNotFoundError(
            f"No cached prices for {ticker!r}. "
            f"Run fetch_prices({ticker!r}, ...) first."
        )
    df = pd.read_csv(cpath, index_col=0, parse_dates=True)
    if not df.index.tzinfo:
        df.index = df.index.tz_localize("UTC")
    return df["close"]
