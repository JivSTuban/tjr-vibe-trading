"""Daily OHLCV loader (Yahoo primary, FMP rescue) with a per-ticker CSV cache.

Split handling (spec §8): Yahoo's chart API returns *raw* quote OHLC plus an adjusted
close. On a split day the raw series steps discontinuously, which would manufacture a
fake -50% "day loser" signal. ``split_factor`` recovers the adjustment ratio from
adjclose/close and `flag_corporate_actions` marks days where it moves, so the strategy
can drop them instead of trading an artifact. (This is the APTV trap from the
2026-09-15 scan, in backtest form.)

Network is touched only by ``fetch_daily``. Everything else is pure.
"""
from __future__ import annotations

import os
import time
from typing import Iterable, Optional

import pandas as pd
import requests

_CACHE = os.path.join(os.path.dirname(__file__), ".cache", "prices")
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh) eod-pressure-reversal research"}
_COLS = ["open", "high", "low", "close", "volume", "adjclose"]

_YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
_FMP = "https://financialmodelingprep.com/stable/historical-price-eod/full"


def normalize_chart(payload: dict) -> pd.DataFrame:
    """Pure: Yahoo chart JSON -> OHLCV+adjclose frame indexed by tz-naive session date."""
    res = payload["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose")
    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert("America/New_York")
    df = pd.DataFrame(
        {
            "open": q.get("open"),
            "high": q.get("high"),
            "low": q.get("low"),
            "close": q.get("close"),
            "volume": q.get("volume"),
            "adjclose": adj if adj is not None else q.get("close"),
        },
        index=idx.normalize().tz_localize(None),
    )
    df = df[df["close"].notna()]
    df.index.name = "date"
    return df.astype(float)


def normalize_fmp(rows: list[dict]) -> pd.DataFrame:
    """Pure: FMP EOD rows -> the same frame shape. FMP has no adjclose on this
    endpoint, so adjclose mirrors close and split detection degrades to "off" for
    rescued tickers (they are logged in the run manifest)."""
    if not rows:
        return pd.DataFrame(columns=_COLS)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df["adjclose"] = df["close"]
    return df[_COLS].astype(float)


def split_factor(df: pd.DataFrame) -> pd.Series:
    """Pure: adjclose/close ratio. Constant through a clean stretch, steps on a
    split or dividend adjustment."""
    return (df["adjclose"] / df["close"]).replace([float("inf"), -float("inf")], pd.NA)


def flag_corporate_actions(df: pd.DataFrame, tol: float = 0.02) -> pd.Series:
    """Pure: True on sessions where the adjustment ratio jumps by more than ``tol``.

    Dividends move the ratio by a fraction of a percent; splits and spin-offs move it
    by tens of percent. The 2% default lets ordinary dividends through and catches the
    distortions the spec tells us to exclude.
    """
    f = split_factor(df)
    step = (f / f.shift(1) - 1.0).abs()
    return (step > tol).fillna(False)


def _cache_path(ticker: str) -> str:
    os.makedirs(_CACHE, exist_ok=True)
    return os.path.join(_CACHE, f"{ticker.replace('/', '_')}.csv")


def fetch_daily(
    ticker: str,
    start: str,
    end: str,
    use_cache: bool = True,
    fmp_key: Optional[str] = None,
    session: Optional[requests.Session] = None,
    pause: float = 0.12,
) -> Optional[pd.DataFrame]:
    """Fetch daily OHLCV for one ticker. Returns None when no source has it.

    Yahoo is primary (full history, has adjclose). FMP is a rescue for names Yahoo
    dropped — mostly ticker changes and acquisitions. A None return is a real data
    hole and the caller must record it, because silent holes are what turn a backtest
    survivorship-biased without anyone noticing.
    """
    path = _cache_path(ticker)
    if use_cache and os.path.exists(path):
        cached = pd.read_csv(path, index_col=0, parse_dates=True)
        return cached if len(cached) else None

    get = (session or requests).get
    p1 = int(pd.Timestamp(start).timestamp())
    p2 = int(pd.Timestamp(end).timestamp())
    df: Optional[pd.DataFrame] = None

    try:
        r = get(
            _YAHOO.format(sym=requests.utils.quote(ticker)),
            params={"interval": "1d", "period1": p1, "period2": p2},
            headers=_UA,
            timeout=30,
        )
        if r.status_code == 200:
            payload = r.json()
            if payload.get("chart", {}).get("result"):
                df = normalize_chart(payload)
    except Exception:
        df = None
    time.sleep(pause)

    if (df is None or len(df) < 50) and fmp_key:
        try:
            r = get(
                _FMP,
                params={"symbol": ticker, "from": start[:10], "to": end[:10], "apikey": fmp_key},
                headers=_UA,
                timeout=30,
            )
            rows = r.json() if r.status_code == 200 else []
            if isinstance(rows, list) and len(rows) >= 50:
                df = normalize_fmp(rows).sort_index()
        except Exception:
            pass
        time.sleep(pause)

    if df is None or df.empty:
        pd.DataFrame(columns=_COLS).to_csv(path)  # negative cache; don't refetch
        return None
    df.to_csv(path)
    return df


def load_panel(
    tickers: Iterable[str],
    start: str,
    end: str,
    fmp_key: Optional[str] = None,
    use_cache: bool = True,
    progress: Optional[callable] = None,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Fetch many tickers. Returns (frames, missing) — ``missing`` is the
    survivorship disclosure and belongs in the run manifest."""
    frames, missing = {}, []
    sess = requests.Session()
    for i, t in enumerate(tickers):
        df = fetch_daily(t, start, end, use_cache=use_cache, fmp_key=fmp_key, session=sess)
        if df is None or df.empty:
            missing.append(t)
        else:
            frames[t] = df
        if progress and i % 25 == 0:
            progress(i, len(frames), len(missing))
    return frames, missing
