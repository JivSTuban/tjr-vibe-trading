"""5-minute bar loader + EXACT spec feature computation (the 60-day window).

Yahoo serves 5m bars for the trailing 60 days only, and every other free source is
either paywalled (FMP, Finnhub, Polygon beyond 2y) or needs an account we don't have
(Alpaca). So the full-history run uses daily proxies and THIS module runs the
unmodified spec on the recent window to measure how wrong those proxies are.

Bar convention: Yahoo labels a 5m bar by its START time in ET. So the "3:50 PM price"
is the OPEN of the 15:50 bar, the 3:55 PM entry is the OPEN of the 15:55 bar, and the
intraday high "through 3:50" is the max high of bars 09:30 through 15:45 inclusive.
Getting this off by one bar would smuggle in 5 minutes of look-ahead, which is exactly
what spec §3 exists to prevent.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import numpy as np
import pandas as pd
import requests

_CACHE = os.path.join(os.path.dirname(__file__), ".cache", "intraday")
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh) eod-pressure-reversal research"}
_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"

SIGNAL_T = "15:50"      # spec: compute signals here
LATE_T = "15:30"        # spec: late-window start
ENTRY_T = "15:55"       # spec: enter here, never at the 16:00 close
OPEN_T = "09:30"
EXIT_B_T = "09:35"      # spec variant B, the practical baseline
EXIT_C_T = "10:00"      # spec variant C


def _cache_path(ticker: str) -> str:
    os.makedirs(_CACHE, exist_ok=True)
    return os.path.join(_CACHE, f"{ticker.replace('/', '_')}.csv")


def normalize_5m(payload: dict) -> pd.DataFrame:
    """Pure: Yahoo 5m chart JSON -> OHLCV indexed by tz-aware ET bar-start."""
    res = payload["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert("America/New_York")
    df = pd.DataFrame(
        {"open": q.get("open"), "high": q.get("high"), "low": q.get("low"),
         "close": q.get("close"), "volume": q.get("volume")},
        index=idx,
    )
    df = df[df["close"].notna()]
    df.index.name = "ts"
    return df.astype(float)


def fetch_5m(ticker: str, use_cache: bool = True, pause: float = 0.15,
             session: Optional[requests.Session] = None) -> Optional[pd.DataFrame]:
    """Trailing-60-day 5m bars for one ticker. None when Yahoo has nothing."""
    path = _cache_path(ticker)
    if use_cache and os.path.exists(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if df.empty:
            return None
        if df.index.tz is None:
            df.index = df.index.tz_localize("America/New_York")
        return df
    get = (session or requests).get
    df = None
    try:
        r = get(_URL.format(sym=requests.utils.quote(ticker)),
                params={"interval": "5m", "range": "60d"}, headers=_UA, timeout=30)
        if r.status_code == 200 and r.json().get("chart", {}).get("result"):
            df = normalize_5m(r.json())
    except Exception:
        df = None
    time.sleep(pause)
    if df is None or df.empty:
        pd.DataFrame(columns=["open", "high", "low", "close", "volume"]).to_csv(path)
        return None
    df.to_csv(path)
    return df


def _at(day_bars: pd.DataFrame, hhmm: str, field: str = "open") -> float:
    """Pure: the value of one bar by its ET start time; NaN when that bar is absent."""
    key = day_bars.index.strftime("%H:%M")
    hit = day_bars.loc[key == hhmm]
    return float(hit[field].iloc[0]) if len(hit) else np.nan


def exact_session_features(bars: pd.DataFrame, prev_close: float) -> dict:
    """Pure: the spec's §4 conditions measured on real intraday bars for ONE session.

    Returns both the exact quantities and the daily-bar proxies for the same session,
    so `calibrate.py` can compare them head to head on identical data.
    """
    key = bars.index.strftime("%H:%M")
    p1550 = _at(bars, SIGNAL_T)
    p1530 = _at(bars, LATE_T)
    p1555 = _at(bars, ENTRY_T)
    close = float(bars["close"].iloc[-1])

    through_1550 = bars.loc[key < SIGNAL_T]          # bars 09:30..15:45
    high_1550 = float(through_1550["high"].max()) if len(through_1550) else np.nan
    low_1550 = float(through_1550["low"].min()) if len(through_1550) else np.nan

    late = bars.loc[(key >= LATE_T) & (key < SIGNAL_T)]
    late_vol = float(late["volume"].sum()) if len(late) else np.nan

    return {
        # --- exact, as specified ---
        "day_ret_exact": p1550 / prev_close - 1.0 if prev_close else np.nan,
        "late_ret_exact": p1550 / p1530 - 1.0 if p1530 else np.nan,
        "dd_high_exact": p1550 / high_1550 - 1.0 if high_1550 else np.nan,
        "late_vol": late_vol,
        "entry_1555": p1555,
        "p1550": p1550,
        # --- the daily-bar equivalents for the same session ---
        "close": close,
        "day_ret_close": close / prev_close - 1.0 if prev_close else np.nan,
        "close_loc_proxy": ((close - low_1550) / (high_1550 - low_1550)
                            if high_1550 and high_1550 > low_1550 else np.nan),
        "full_day_vol": float(bars["volume"].sum()),
    }


def next_morning_prices(bars: pd.DataFrame) -> dict:
    """Pure: the three spec §7 exit marks from the next session's bars."""
    return {
        "exit_open": _at(bars, OPEN_T),        # variant A
        "exit_0935": _at(bars, EXIT_B_T),      # variant B (the spec baseline)
        "exit_1000": _at(bars, EXIT_C_T),      # variant C
    }


def session_frames(df: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    """Pure: split a 5m series into regular-hours sessions keyed by date.

    Pre/post-market bars are dropped: the spec trades the regular session, and Yahoo's
    60-day 5m feed includes extended hours whose thin prints would distort both the
    intraday high and the late-volume measure.
    """
    key = df.index.strftime("%H:%M")
    rth = df.loc[(key >= "09:30") & (key < "16:00")]
    return {d: g for d, g in rth.groupby(rth.index.normalize().tz_localize(None))
            if len(g) >= 60}     # >= 5 hours of bars; drops half-days and gappy feeds
