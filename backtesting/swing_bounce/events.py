"""Beaten-down drop-event detection: sharp fall from trailing high + oversold.

Pure and look-ahead-safe (uses only bars up to and including t; the entry is made at t's close).
"""
from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0.0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0.0, float("nan"))
    return (100 - 100 / (1 + rs)).fillna(100.0)


def is_oversold(close: pd.Series, t_idx: int) -> bool:
    win = close.iloc[: t_idx + 1]
    if len(win) < 20:
        return False
    r = rsi(win).iloc[-1]
    ma = win.iloc[-20:].mean()
    sd = win.iloc[-20:].std(ddof=0)
    lower_band = ma - 2 * sd
    return bool(r < 35 or win.iloc[-1] < lower_band)


def is_drop_event(close: pd.Series, t_idx: int, threshold: float, lookback: int = 63) -> bool:
    win = close.iloc[max(0, t_idx - lookback): t_idx + 1]
    if len(win) < 20:
        return False
    trailing_high = win.max()
    below = close.iloc[t_idx] <= threshold * trailing_high
    return bool(below and is_oversold(close, t_idx))
