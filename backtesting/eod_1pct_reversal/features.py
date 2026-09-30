"""Spec §3.2 price features — pure functions, two data regimes.

The spec measures everything at 15:50 ET. Free intraday history is 60 days (Yahoo),
so there are two implementations of ONE feature contract:

  `daily_features`     2014-2026, 2,311 tickers. 15:50 is PROXIED by the close.
  `intraday_features`  60 days, 515 tickers. The literal spec, 15:50 bar open.

Naming them separately (rather than silently degrading) is the point: `run.py`
measures the proxy error on the overlap, so the long-history numbers carry a
quantified bias instead of an assumed one.

WHICH FEATURES SURVIVE THE PROXY
  prev_low_distance_pct   close vs prev low        PROXY (close != 15:50 price)
  day_return_pct          close vs prev close      PROXY, same error
  close_location_value    (close-low)/(high-low)   PROXY, and BIASED LOW: the full
                          day's range includes 15:50-16:00, so a stock that bounced
                          into the close scores nearer its low than it truly was at
                          15:50. Loosens the gate.
  range_capacity_pct      20d median (H-L)/C       EXACT — no intraday needed.
  sector_relative_pct     stock - sector ETF       PROXY, both legs at the close.
  late_return_pct         15:30 -> 15:50           UNAVAILABLE. NaN on daily; the
                          gate is skipped and its absence is reported, never
                          silently treated as passing.
  spread_bps              (ask-bid)/mid            UNAVAILABLE on both paths (no
                          free historical quotes). Modelled as a cost, not a gate.

SPLITS. Every ratio feature is computed on SPLIT-ADJUSTED prices, because
`prev_low_distance` compares two different sessions: a 4:1 split between them prints
a -75% "distance" and manufactures a perfect-looking signal. The $10 price floor and
ADV both use RAW prices, since those screen the real tradable tape.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Spec §12 entry_filters. Defaults only — run.py sweeps the §3.2 neighbourhoods.
DEFAULTS = {
    "prev_low_distance_min_pct": -0.75,
    "prev_low_distance_max_pct": 1.00,
    "max_day_return_pct": -0.75,
    "max_late_return_pct": -0.25,
    "max_close_location": 0.35,
    "min_range_capacity_pct": 1.50,
    "max_sector_relative_pct": -0.50,
}

MIN_PRICE = 10.0
MIN_ADV20 = 50e6
RANGE_WINDOW = 20


def adjusted(df: pd.DataFrame) -> pd.DataFrame:
    """Pure: OHLC rescaled by adjclose/close so cross-session ratios survive splits."""
    f = (df["adjclose"] / df["close"]).replace([np.inf, -np.inf], np.nan).ffill().fillna(1.0)
    out = df.copy()
    for col in ("open", "high", "low", "close"):
        out[col] = df[col] * f
    return out


def daily_features(df: pd.DataFrame, sector_ret: pd.Series | None = None) -> pd.DataFrame:
    """Pure: per-session spec features for one ticker from DAILY bars.

    `df` is prices.normalize_chart shape. Every column uses the session itself or
    earlier; nothing is shifted backwards from t+1. The exit legs (`next_*`) are
    attached for convenience but are never read by a gate.
    """
    a = adjusted(df)
    out = pd.DataFrame(index=df.index)

    prev_close = a["close"].shift(1)
    prev_low = a["low"].shift(1)
    rng = (a["high"] - a["low"]).replace(0.0, np.nan)

    # entry_reference proxy = the session close (spec uses the 15:50 mid).
    out["entry_ref"] = a["close"]
    out["prev_low_distance_pct"] = (a["close"] / prev_low - 1.0) * 100.0
    out["day_return_pct"] = (a["close"] / prev_close - 1.0) * 100.0
    out["close_location_value"] = (a["close"] - a["low"]) / rng
    out["late_return_pct"] = np.nan  # needs a 15:30 mark; daily cannot see it

    # Range capacity: median of the PRIOR 20 sessions, today excluded (no look-ahead).
    daily_range = ((a["high"] - a["low"]) / a["close"]).replace([np.inf, -np.inf], np.nan)
    out["range_capacity_pct"] = daily_range.shift(1).rolling(RANGE_WINDOW).median() * 100.0

    if sector_ret is not None:
        out["sector_relative_pct"] = out["day_return_pct"] - sector_ret.reindex(df.index) * 100.0
    else:
        out["sector_relative_pct"] = np.nan

    # Tradability on the RAW tape.
    out["price"] = df["close"]
    out["adv20"] = (df["close"] * df["volume"]).shift(1).rolling(RANGE_WINDOW).mean()

    # Raw-vs-adjusted bridge so execution can price fills in adjusted space.
    out["adj_factor"] = (a["close"] / df["close"]).replace([np.inf, -np.inf], np.nan)
    return out


def intraday_features(bars: pd.DataFrame, daily: pd.DataFrame,
                      sector_bars: pd.DataFrame | None = None) -> pd.DataFrame:
    """Pure: the LITERAL spec features at 15:50 ET, one row per session.

    `bars` is 5-minute OHLCV indexed by tz-aware ET bar START (intraday.normalize_5m).
    Yahoo labels a bar by when it opens, so:

      * the 15:50 price is the OPEN of the 15:50 bar — known AT 15:50:00,
      * everything "through 15:50" uses bars 09:30..15:45 inclusive,
      * the entry is the OPEN of the 15:55 bar (spec §6.1 conservative entry).

    Off-by-one here smuggles five minutes of look-ahead into the signal, which is the
    single failure mode the spec's §6 exists to prevent.
    """
    if bars.empty:
        return pd.DataFrame()
    b = bars.copy()
    b["session"] = b.index.normalize().tz_localize(None)
    b["hm"] = b.index.strftime("%H:%M")

    def at(time_str: str, col: str) -> pd.Series:
        sel = b[b["hm"] == time_str]
        return sel.set_index("session")[col]

    signal_px = at("15:50", "open")
    late_px = at("15:30", "open")
    entry_px = at("15:55", "open")

    # High/low of the session THROUGH the signal: bars opening at or before 15:45,
    # plus the 15:50 open itself (a price observed at the signal instant).
    pre = b[b["hm"] <= "15:45"]
    hi = pre.groupby("session")["high"].max()
    lo = pre.groupby("session")["low"].min()
    hi = pd.concat([hi, signal_px], axis=1).max(axis=1)
    lo = pd.concat([lo, signal_px], axis=1).min(axis=1)

    idx = signal_px.index
    out = pd.DataFrame(index=idx)
    out["entry_ref"] = signal_px
    out["entry_px"] = entry_px.reindex(idx)

    a = adjusted(daily)
    prev_close = a["close"].shift(1).reindex(idx)
    prev_low = a["low"].shift(1).reindex(idx)
    factor = (a["close"] / daily["close"]).replace([np.inf, -np.inf], np.nan).reindex(idx)

    # Intraday bars are RAW; lift them into adjusted space to compare across sessions.
    sig_adj = signal_px * factor
    out["prev_low_distance_pct"] = (sig_adj / prev_low - 1.0) * 100.0
    out["day_return_pct"] = (sig_adj / prev_close - 1.0) * 100.0
    out["late_return_pct"] = (signal_px / late_px.reindex(idx) - 1.0) * 100.0

    rng = (hi - lo).replace(0.0, np.nan)
    out["close_location_value"] = (signal_px - lo) / rng

    daily_range = ((a["high"] - a["low"]) / a["close"]).replace([np.inf, -np.inf], np.nan)
    out["range_capacity_pct"] = (daily_range.shift(1).rolling(RANGE_WINDOW).median() * 100.0).reindex(idx)

    if sector_bars is not None and not sector_bars.empty:
        sb = sector_bars.copy()
        sb["session"] = sb.index.normalize().tz_localize(None)
        sb["hm"] = sb.index.strftime("%H:%M")
        s_sig = sb[sb["hm"] == "15:50"].set_index("session")["open"].reindex(idx)
        s_prev = s_sig.shift(1)
        sector_day = (s_sig / s_prev - 1.0) * 100.0
        out["sector_relative_pct"] = out["day_return_pct"] - sector_day
    else:
        out["sector_relative_pct"] = np.nan

    out["price"] = daily["close"].reindex(idx)
    out["adv20"] = (daily["close"] * daily["volume"]).shift(1).rolling(RANGE_WINDOW).mean().reindex(idx)
    out["adj_factor"] = factor
    return out


def tradable(feats: pd.DataFrame, min_price: float = MIN_PRICE,
             min_adv: float = MIN_ADV20) -> pd.Series:
    """Pure: spec §3.1 universe screen (price >= $10, 20d ADV >= $50M)."""
    return (feats["price"] >= min_price) & (feats["adv20"] >= min_adv)
