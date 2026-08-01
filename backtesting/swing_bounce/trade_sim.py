"""Stop/target/time trade simulator over daily OHLC bars.

Pure. Conservative on ambiguity: a gap-through fills at the bar's open; a single bar touching BOTH
the stop and target resolves to the stop (no intrabar data to disambiguate).
"""
from __future__ import annotations

import pandas as pd


def simulate_trade(ohlc: pd.DataFrame, entry_idx: int, target_pct: float, stop_pct: float,
                   horizon_days: int, cost_bps: float = 15.0) -> dict | None:
    n = len(ohlc)
    if entry_idx + 1 >= n:
        return None
    entry = float(ohlc["close"].iloc[entry_idx])
    stop_p = entry * (1 - stop_pct)
    target_p = entry * (1 + target_pct)
    last = min(entry_idx + horizon_days, n - 1)
    outcome, exit_idx, exit_price = "time", last, float(ohlc["close"].iloc[last])
    for k in range(entry_idx + 1, last + 1):
        o = float(ohlc["open"].iloc[k])
        hi = float(ohlc["high"].iloc[k])
        lo = float(ohlc["low"].iloc[k])
        if o <= stop_p:                                   # gap down through stop
            outcome, exit_idx, exit_price = "stop", k, o
            break
        if o >= target_p:                                 # gap up through target
            outcome, exit_idx, exit_price = "target", k, o
            break
        if lo <= stop_p:                                  # same-bar both -> stop first (conservative)
            outcome, exit_idx, exit_price = "stop", k, stop_p
            break
        if hi >= target_p:
            outcome, exit_idx, exit_price = "target", k, target_p
            break
    cost = 2 * (cost_bps / 1e4)                            # entry + exit
    gross = exit_price / entry - 1.0
    net = gross - cost
    return {"outcome": outcome, "exit_idx": exit_idx, "exit_price": exit_price,
            "gross_ret": gross, "net_ret": net, "R": net / stop_pct}
