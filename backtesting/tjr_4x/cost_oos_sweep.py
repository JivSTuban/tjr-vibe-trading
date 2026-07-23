"""Iteration-4 cost model + in-sample / out-of-sample split.

Runs the best config found so far ONCE to get a single pool of closed
trades, then:

  1. Partitions the CLOSED trades 80/20 by entry_time (a temporal split;
     cutoff = first_ts + 0.8 * (last_ts - first_ts)). IS = entry_time <
     cutoff, OOS = entry_time >= cutoff. The trades are NOT re-simulated;
     the same resolved outcomes are re-scored per window.
  2. For each window (FULL, IS, OOS) and each cost model
     (taker_only, maker_taker) recomputes metrics via an outcome-aware
     re-cost. A GROSS (zero-cost) row per window isolates edge stability.

The best config is **C bias + 0.2% min-stop, fixed 2R** (the iteration-3
winner). Only the entry limit (maker) vs the stop->market SL (taker+slip)
distinction is new here.

Uses the cached 5m CSV in .cache/ (no re-fetch). Run:
    python3 -m backtesting.tjr_4x.cost_oos_sweep
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pandas as pd

from .config import Config
from .strategy import find_trades
from .engine import backtest, recost_trade, metrics_from_closed

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")

# The iteration-3 winner: C bias, fixed 2R, min-stop 0.2%.
_BEST = dict(bias_mode="C", exit_model="fixed_rr", min_stop_pct=0.002)

_WINDOWS = ["FULL", "IS", "OOS"]
_COST_MODELS = ["taker_only", "maker_taker"]


def _load_5m(cfg: Config, months: int = 18) -> pd.DataFrame:
    csvs = sorted(glob.glob(os.path.join(_CACHE, "*_5m_*.csv")))
    if csvs:
        df = pd.read_csv(csvs[-1], index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        return df.sort_index()
    from .data import fetch_ohlcv  # network only if no cache
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=30 * months)
    return fetch_ohlcv(cfg.symbol, cfg.base_timeframe, since, until)


def _row(window: str, cost_model: str, closed, base_cfg: Config) -> dict:
    """Recompute one (window, cost_model) row from closed trades."""
    cfg = replace(base_cfg, cost_model=cost_model)
    recosted = [recost_trade(ct, cfg) for ct in closed]
    res = metrics_from_closed(recosted)
    # gross expectancy = mean gross_R (zero-cost), window-scoped
    gross_res = metrics_from_closed([recost_trade(ct, replace(base_cfg, cost_model="gross"))
                                     for ct in closed])
    return {
        "window": window, "cost_model": cost_model,
        "trades": res.trade_count,
        "win_rate": res.win_rate,
        "gross_expR": gross_res.avg_R,      # == mean gross_R
        "net_expR": res.avg_R,
        "profit_factor": res.profit_factor,
        "net_R": res.net_return_R,
    }


def main() -> None:
    base = Config(**_BEST)          # C, min_stop 0.002, fixed 2R
    df5m = _load_5m(base)
    print(f"loaded {len(df5m):,} bars")

    # ---- run the strategy ONCE -> single pool of closed trades ---------- #
    trades = find_trades(df5m, base)
    full_res = backtest(df5m, trades, base)
    closed = full_res.closed_trades
    print(f"best config: C bias + min_stop 0.2% + fixed 2R -> "
          f"{len(closed)} closed trades")

    # ---- 80/20 temporal split of the CLOSED trades --------------------- #
    entry_times = [ct.entry_time for ct in closed]
    first_ts, last_ts = min(entry_times), max(entry_times)
    cutoff = first_ts + 0.8 * (last_ts - first_ts)
    is_trades = [ct for ct in closed if ct.entry_time < cutoff]
    oos_trades = [ct for ct in closed if ct.entry_time >= cutoff]
    windows = {"FULL": closed, "IS": is_trades, "OOS": oos_trades}

    print(f"cutoff (80/20): {cutoff}")
    print(f"IS trades: {len(is_trades)}   OOS trades: {len(oos_trades)}")
    print("NOTE: min_stop 0.2% was picked from a FULL-sample diagnostic "
          "(mild in-sample leakage); OOS *gross* is the honest stability "
          "signal.\n")

    # ---- build the table ----------------------------------------------- #
    rows = []
    for w in _WINDOWS:
        for cm in _COST_MODELS:
            rows.append(_row(w, cm, windows[w], base))

    header = (f"{'window':<8}{'cost_model':<13}{'trades':>7}{'win%':>7}"
              f"{'gross_expR':>12}{'net_expR':>10}{'PF':>7}{'net_R':>9}")
    print(header)
    print("-" * len(header))
    for r in rows:
        pf = r["profit_factor"]
        pf_s = "inf" if pf == float("inf") else f"{pf:.2f}"
        print(f"{r['window']:<8}{r['cost_model']:<13}{r['trades']:>7}"
              f"{r['win_rate']*100:>6.1f}%{r['gross_expR']:>12.3f}"
              f"{r['net_expR']:>10.3f}{pf_s:>7}{r['net_R']:>9.1f}")

    # ---- IS -> OOS gross comparison (the overfit test) ----------------- #
    is_gross = metrics_from_closed(
        [recost_trade(ct, replace(base, cost_model="gross")) for ct in is_trades])
    oos_gross = metrics_from_closed(
        [recost_trade(ct, replace(base, cost_model="gross")) for ct in oos_trades])
    print("\n=== IS -> OOS GROSS (edge stability) ===")
    print(f"  IS  gross exp_R = {is_gross.avg_R:+.3f}  "
          f"(n={is_gross.trade_count}, win {is_gross.win_rate*100:.1f}%)")
    print(f"  OOS gross exp_R = {oos_gross.avg_R:+.3f}  "
          f"(n={oos_gross.trade_count}, win {oos_gross.win_rate*100:.1f}%)")
    delta = oos_gross.avg_R - is_gross.avg_R
    print(f"  OOS - IS delta  = {delta:+.3f} R/trade")

    # ---- persist ------------------------------------------------------- #
    out_dir = os.path.join(os.path.dirname(__file__), "runs")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "cost_oos.json")
    payload = {
        "best_config": _BEST,
        "cutoff": str(cutoff),
        "is_trades": len(is_trades),
        "oos_trades": len(oos_trades),
        "table": rows,
        "is_gross_expR": is_gross.avg_R,
        "oos_gross_expR": oos_gross.avg_R,
        "note": ("min_stop 0.2% picked from full-sample diagnostic (mild "
                 "in-sample leakage); OOS gross is the honest stability signal"),
    }
    with open(out, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
