"""Spec §4 entry conditions + §6 composite ranking score — all pure.

DATA SUBSTITUTIONS (read this before trusting any number downstream).

The spec measures four of its six filters against an intraday tape (3:30 PM and
3:50 PM marks). Free intraday history is capped at 60 days (Yahoo) or paywalled
(FMP/Finnhub/Polygon), so the full-history run measures what daily bars can measure
and proxies the rest. Each substitution is named here and its bias is stated:

  A. DayReturn      close/prev_close - 1              EXACT up to close-vs-15:50.
  B. LateReturn     -> CloseLocation in day range     PROXY. "Still selling late"
                       (close - low) / (high - low)   becomes "closed on the low".
                       Both isolate pressure INTO the bell; the proxy cannot see a
                       stock that fell at 2 PM and stabilised, so it is a LOOSER
                       filter and admits some non-late selloffs.
  C. DrawdownFromHigh close/high - 1                  EXACT.
  D. RelativeSector  stock_ret - sector_etf_ret       EXACT.
  E. RelativeLateVol -> volume / median(volume, 20)   PROXY. Whole-day relative
                       volume instead of the 15:30-15:50 window. Directionally the
                       same (heavy days are heavy late) but blind to a late burst on
                       an otherwise quiet day.
  F. No earnings     Nasdaq calendar, BMO/AMC aware   EXACT (see earnings.py).

`calibrate.py` measures the size of the B/E proxy error and the close-vs-15:55 entry
error on the 60-day intraday window, so the bias is quantified rather than assumed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = ["day_ret", "close_loc", "dd_from_high", "rel_sector", "rel_vol"]

# Spec §6 weights. close_loc carries filter B's 25%, rel_vol carries E's 10%.
WEIGHTS = {
    "day_ret": 0.20,
    "close_loc": 0.25,
    "dd_from_high": 0.20,
    "rel_sector": 0.25,
    "rel_vol": 0.10,
}

# Spec §4/§17 initial thresholds.
DEFAULT_THRESHOLDS = {
    "day_ret": -0.015,
    "close_loc": 0.25,
    "dd_from_high": -0.020,
    "rel_sector": -0.010,
    "rel_vol": 1.5,
}


def compute_features(df: pd.DataFrame, bench: pd.Series, adv_window: int = 20) -> pd.DataFrame:
    """Pure: per-session feature frame for one ticker.

    ``df`` is daily OHLCV (prices.normalize_chart shape); ``bench`` is the sector ETF's
    daily simple return aligned on the same index. Every feature uses only data from
    the session itself or earlier — no forward fill from t+1, which is the whole
    anti-lookahead point of spec §3.
    """
    out = pd.DataFrame(index=df.index)
    prev_close = df["close"].shift(1)

    out["day_ret"] = df["close"] / prev_close - 1.0
    rng = (df["high"] - df["low"]).replace(0.0, np.nan)
    out["close_loc"] = (df["close"] - df["low"]) / rng
    out["dd_from_high"] = df["close"] / df["high"] - 1.0
    out["rel_sector"] = out["day_ret"] - bench.reindex(df.index)

    # Median of the PRIOR 20 sessions, excluding today, mirroring the spec's
    # "median same-window volume over prior 20 sessions".
    med = df["volume"].shift(1).rolling(adv_window).median()
    out["rel_vol"] = df["volume"] / med.replace(0.0, np.nan)

    # Liquidity / price screens (spec §2), computed on prior sessions only.
    out["adv20"] = (df["close"] * df["volume"]).shift(1).rolling(adv_window).mean()
    out["price"] = df["close"]
    out["prev_close"] = prev_close
    out["next_open"] = df["open"].shift(-1)   # exit leg, used only after selection
    out["next_close"] = df["close"].shift(-1)

    # Adjustment factors for the overnight leg. Without these, a split or dividend
    # ex-date between the close and the next open prints a fake loss: a 4:1 split
    # reads as -75%. Carrying f(t) and f(t+1) lets `strategy.simulate` compute a
    # true total return across the hold, which also credits the dividend the holder
    # actually receives on an ex-date.
    factor = (df["adjclose"] / df["close"]).replace([np.inf, -np.inf], np.nan)
    out["adj_factor"] = factor
    out["next_adj_factor"] = factor.shift(-1)
    return out


def passes(feats: pd.DataFrame, thresholds: dict | None = None) -> pd.DataFrame:
    """Pure: boolean frame, one column per spec filter (A-E). Filter F is applied
    separately because it needs the earnings calendar."""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    return pd.DataFrame(
        {
            "A_day": feats["day_ret"] <= t["day_ret"],
            "B_late": feats["close_loc"] <= t["close_loc"],
            "C_high": feats["dd_from_high"] <= t["dd_from_high"],
            "D_sector": feats["rel_sector"] <= t["rel_sector"],
            "E_vol": feats["rel_vol"] >= t["rel_vol"],
        },
        index=feats.index,
    )


def liquid(feats: pd.DataFrame, min_price: float = 10.0, min_adv: float = 50e6) -> pd.Series:
    """Pure: spec §2 tradability screen (price >= $10, ADV20 >= $50M)."""
    return (feats["price"] >= min_price) & (feats["adv20"] >= min_adv)


def percentile_scores(cands: pd.DataFrame) -> pd.Series:
    """Pure: spec §6 composite score over one day's candidate cross-section.

    Each feature becomes a 0-1 percentile where 1 = *most extreme in the direction the
    spec calls severe*: the biggest daily selloff, the lowest close in range, the
    deepest drawdown, the worst sector-relative return, the highest relative volume.
    Ranking within the day (not against history) is what makes it a cross-sectional
    selector, per the spec's "rank candidates" wording.
    """
    if cands.empty:
        return pd.Series(dtype=float)
    if len(cands) == 1:
        return pd.Series([1.0], index=cands.index)

    ranked = pd.DataFrame(index=cands.index)
    # Lower is more severe for these four -> invert the percentile.
    for col in ["day_ret", "close_loc", "dd_from_high", "rel_sector"]:
        ranked[col] = 1.0 - cands[col].rank(pct=True)
    ranked["rel_vol"] = cands["rel_vol"].rank(pct=True)
    return sum(ranked[c] * w for c, w in WEIGHTS.items())
