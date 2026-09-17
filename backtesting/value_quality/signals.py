"""Value composite (sector-relative), quality gate, and sharp-drop trigger.

Pure and look-ahead-safe: drop_trigger uses only bars strictly before `asof`;
value_composite ranks a cross-section supplied by the caller (which is itself
built only from `filed <= asof` fundamentals). No I/O.
"""
from __future__ import annotations
import pandas as pd

_VALUE_COLS = ["ep", "bp", "ebitda_ev", "fcf_yield"]


def value_composite(rows: pd.DataFrame) -> pd.Series:
    parts = []
    for sector, grp in rows.groupby("sector"):
        # rank each cheapness metric within the sector; higher metric = cheaper = higher rank
        ranks = grp[_VALUE_COLS].rank(pct=True)   # NaNs stay NaN, ignored by mean below
        parts.append(ranks.mean(axis=1))
    out = pd.concat(parts)
    return out.reindex(rows.index)


def drop_trigger(prices: pd.Series, asof: pd.Timestamp, threshold: float,
                 lookback: int = 63) -> bool:
    prior = prices[prices.index < asof]
    if len(prior) < 2:
        return False
    last = prior.iloc[-1]
    window_high = prior.iloc[-lookback:].max()
    return bool(last <= threshold * window_high)
