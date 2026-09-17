"""Portfolio selection for the value+quality+drawdown strategy.

Pure: consumes a single rebalance date's candidate cross-section (already
built point-in-time by the backtest loop) and returns the equal-weight holding
list. Look-ahead safety lives upstream (only `filed<=asof` fundamentals and
`<asof` prices feed the candidate frame).
"""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


@dataclass
class ValueQualityCfg:
    f_min: int = 7
    value_top_frac: float = 0.33
    drop_threshold: float = 0.75
    drop_lookback: int = 63
    max_names: int = 50
    max_hold_months: int = 12


def select_holdings(candidates: pd.DataFrame, cfg: ValueQualityCfg) -> list[str]:
    if candidates.empty:
        return []
    cutoff = candidates["value_score"].quantile(1.0 - cfg.value_top_frac, interpolation='lower')
    mask = (
        (candidates["value_score"] >= cutoff)
        & (candidates["fscore"] >= cfg.f_min)
        & (candidates["drop_fired"])
    )
    picked = candidates[mask].sort_values("value_score", ascending=False)
    return list(picked.index[: cfg.max_names])
