"""Spec §6 execution contract — the +1% target and its time stops. Pure.

The rules that decide whether this study is honest:

  GAP FIRST. If the next session OPENS at or above the target, the fill is the open,
  not a magical +1.00%. Spec §6.2 states this explicitly and it is where naive target
  backtests manufacture their edge.

  TOUCH != FILL ORDER. With daily bars a session that touches both a target and a
  deep low is ambiguous. There is no stop in this strategy (the exit is a TIME stop),
  so the ambiguity is one-sided and benign: the target either printed or it did not.
  The adverse path is still recorded as MAE so the pain is visible.

  NO 16:00 CLOSE FOR A 15:50 SIGNAL. The daily path proxies the entry with the close
  and says so; the intraday path enters at the 15:55 bar open. `run.py` measures the
  difference between them on the 60-day overlap.

  COSTS ARE SUBTRACTED, NEVER ASSUMED AWAY. 2/5/10 bps per side, both sides.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TARGET_PCT = 1.00
HORIZONS = (1, 3, 5)
COST_BPS = (2.0, 5.0, 10.0)


def simulate_one(adj: pd.DataFrame, entry_idx: int, entry_price: float,
                 horizon: int, target_pct: float = TARGET_PCT) -> dict | None:
    """Pure: one trade from the session at `entry_idx`, held up to `horizon` sessions.

    `adj` is SPLIT-ADJUSTED daily OHLC (features.adjusted output). `entry_price` is in
    that same adjusted space. Returns None when the horizon runs past the data, which
    keeps unfinished trades out of the sample instead of silently truncating them to
    the last close — a subtle way to bias the tail.
    """
    last = entry_idx + horizon
    if last >= len(adj):
        return None

    target = entry_price * (1.0 + target_pct / 100.0)
    fwd = adj.iloc[entry_idx + 1: last + 1]
    if fwd.empty:
        return None

    exit_price, exit_kind, hit_day = None, None, np.nan
    for day, (_, bar) in enumerate(fwd.iterrows(), start=1):
        if bar["open"] >= target:                 # gapped through — take the open
            exit_price, exit_kind, hit_day = float(bar["open"]), "gap_open", day
            break
        if bar["high"] >= target:                 # touched intraday — fill at target
            exit_price, exit_kind, hit_day = float(target), "target", day
            break
    if exit_price is None:                        # time stop at the horizon close
        exit_price, exit_kind = float(fwd.iloc[-1]["close"]), "time_stop"

    path = fwd if np.isnan(hit_day) else fwd.iloc[: int(hit_day)]
    gross = exit_price / entry_price - 1.0
    return {
        "entry_price": float(entry_price),
        "exit_price": exit_price,
        "exit_kind": exit_kind,
        "days_held": int(hit_day) if not np.isnan(hit_day) else horizon,
        "hit_target": exit_kind in ("target", "gap_open"),
        "gross_ret": gross,
        "mae": float(path["low"].min() / entry_price - 1.0),
        "mfe": float(path["high"].max() / entry_price - 1.0),
    }


def close_to_open(adj: pd.DataFrame, entry_idx: int, entry_price: float) -> dict | None:
    """Pure: spec §6.2 control leg — hold to the next regular open, no target.

    Separates the overnight gap effect from any intraday rebound. If this earns most
    of the strategy's return, the '+1% reversal' is really just the overnight drift
    the sibling study already measured at +3.02 bps on SPY.
    """
    if entry_idx + 1 >= len(adj):
        return None
    nxt = adj.iloc[entry_idx + 1]
    return {
        "entry_price": float(entry_price),
        "exit_price": float(nxt["open"]),
        "exit_kind": "next_open",
        "days_held": 1,
        "hit_target": bool(nxt["open"] / entry_price - 1.0 >= TARGET_PCT / 100.0),
        "gross_ret": float(nxt["open"] / entry_price - 1.0),
        "mae": float(min(nxt["open"], nxt["low"]) / entry_price - 1.0),
        "mfe": float(max(nxt["open"], nxt["high"]) / entry_price - 1.0),
    }


def apply_costs(gross: pd.Series, bps_per_side: float) -> pd.Series:
    """Pure: round-trip cost. Two sides, so 5 bps/side is 10 bps of round trip."""
    return gross - 2.0 * bps_per_side / 10000.0
