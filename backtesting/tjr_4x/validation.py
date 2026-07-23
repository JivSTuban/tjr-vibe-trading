"""Iteration-5 validation helpers: walk-forward, cost-mix stress, holdout.

The credibility test for the TJR-4X edge. Everything here re-scores an
already-resolved pool of ClosedTrade objects via the outcome-aware
``recost_trade`` (no re-walk of price data), except ``run_symbol`` which
runs the full detect -> backtest path for one instrument.

Three lenses:
  * ``walk_forward`` — split closed trades into k sequential equal-TIME
    folds by entry_time; per fold report n / win% / gross_expR / net_expR
    (maker, r=0). Answers "is the gross edge consistent across time, or
    concentrated in 1-2 windows?".
  * ``cost_scenarios`` — recost the SAME pool under an entry cost-mix
    stress: optimistic (all-maker, r=0), realistic (50% taker, r=0.5),
    pessimistic (all-taker entry, r=1.0). Answers "does net survive a
    worse fill assumption?".
  * ``run_symbol`` — load a cached 5m CSV, detect + backtest, return the
    closed pool + base metrics. Used for the ETH instrument holdout (SAME
    cfg, no retuning).

No network: ``load_5m`` reads the newest matching cached CSV only.
"""

from __future__ import annotations

import glob
import math
import os
from dataclasses import replace
from typing import List

import pandas as pd

from .config import Config
from .strategy import find_trades
from .engine import (ClosedTrade, backtest, recost_trade, metrics_from_closed)

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")

# The best config: C bias, fixed 2R, min-stop 0.2% (iteration-3/4 winner).
_BEST = dict(bias_mode="C", exit_model="fixed_rr", min_stop_pct=0.002)


def load_5m(cache_glob: str) -> pd.DataFrame:
    """Read the NEWEST cached CSV matching ``cache_glob`` (no network).

    Columns lowercased, datetime index, sorted. ``cache_glob`` is matched
    inside ``.cache/`` (e.g. ``"*BTC*_5m_*.csv"``).
    """
    matches = sorted(glob.glob(os.path.join(_CACHE, cache_glob)),
                     key=os.path.getmtime)
    if not matches:
        raise FileNotFoundError(
            f"no cached CSV matching {cache_glob!r} in {_CACHE}")
    df = pd.read_csv(matches[-1], index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    return df.sort_index()


def _gross_expR(closed: List[ClosedTrade], base_cfg: Config) -> float:
    """Mean gross_R (zero-cost), outcome-aware, window-scoped."""
    g = metrics_from_closed(
        [recost_trade(ct, replace(base_cfg, cost_model="gross")) for ct in closed])
    return g.avg_R


def _net_expR(closed: List[ClosedTrade], cfg: Config) -> float:
    """Mean net_R under ``cfg`` (maker_taker + entry_taker_ratio applied)."""
    res = metrics_from_closed([recost_trade(ct, cfg) for ct in closed])
    return res.avg_R


def walk_forward(closed: List[ClosedTrade], k: int = 6) -> List[dict]:
    """Split closed trades into k sequential equal-TIME folds by entry_time.

    Fold boundaries are evenly spaced across [first_ts, last_ts]; each fold
    owns entry_times in [lo, hi) (the last fold includes the final ts). Per
    fold returns {fold, start, end, n, win%, gross_expR, net_expR(maker,r=0)}.
    Folds are time-equal, so counts vary with trade density.
    """
    closed = sorted(closed, key=lambda c: c.entry_time)
    if not closed:
        return []
    base = Config(**_BEST)
    maker = replace(base, cost_model="maker_taker", entry_taker_ratio=0.0)

    first_ts = closed[0].entry_time
    last_ts = closed[-1].entry_time
    span = last_ts - first_ts
    out = []
    for i in range(k):
        lo = first_ts + span * (i / k)
        hi = first_ts + span * ((i + 1) / k)
        if i == k - 1:
            fold = [c for c in closed if lo <= c.entry_time <= hi]
        else:
            fold = [c for c in closed if lo <= c.entry_time < hi]
        res = metrics_from_closed([recost_trade(c, maker) for c in fold])
        out.append({
            "fold": i + 1,
            "start": str(lo),
            "end": str(hi),
            "n": res.trade_count,
            "win_rate": res.win_rate,
            "gross_expR": _gross_expR(fold, base) if fold else 0.0,
            "net_expR": res.avg_R,
        })
    return out


def cost_scenarios(closed: List[ClosedTrade], cfg: Config) -> List[dict]:
    """Recost the pool under three entry cost-mix scenarios.

    optimistic r=0 (all-maker) >= realistic r=0.5 >= pessimistic r=1.0.
    Each row returns net_expR + PF (all maker_taker; only entry_taker_ratio
    varies). Returned in optimistic -> pessimistic order.
    """
    scenarios = [
        ("optimistic", 0.0),
        ("realistic", 0.5),
        ("pessimistic", 1.0),
    ]
    out = []
    for name, r in scenarios:
        scfg = replace(cfg, cost_model="maker_taker", entry_taker_ratio=r)
        res = metrics_from_closed([recost_trade(c, scfg) for c in closed])
        out.append({
            "scenario": name,
            "entry_taker_ratio": r,
            "trades": res.trade_count,
            "net_expR": res.avg_R,
            "profit_factor": res.profit_factor,
            "net_R": res.net_return_R,
        })
    return out


def run_symbol(cache_glob: str, cfg: Config):
    """Load a cached 5m CSV, detect + backtest, return (closed, base_metrics).

    Uses ``cfg`` verbatim (no retuning — this is what makes the ETH run a
    true holdout). Returns a dict with the closed pool and base Result.
    """
    df5m = load_5m(cache_glob)
    trades = find_trades(df5m, cfg)
    res = backtest(df5m, trades, cfg)
    return {
        "bars": len(df5m),
        "closed": res.closed_trades,
        "result": res,
    }
