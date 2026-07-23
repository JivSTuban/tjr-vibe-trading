"""Iteration-5 validation CLI: walk-forward + cost-mix stress + ETH holdout.

The credibility test for the TJR-4X edge. Runs the best config
(C bias + 0.2% min-stop + fixed 2R) ONCE on BTC to get a single pool of
closed trades, then:

  (a) Walk-forward: 6 sequential equal-TIME folds by entry_time —
      per-fold n / win% / gross_expR / net_expR. Is the gross edge
      consistent across time or concentrated in 1-2 windows?
  (b) Cost-mix stress: recost the pool under optimistic (all-maker),
      realistic (50% taker entry) and pessimistic (all-taker entry)
      scenarios, for the FULL sample AND the last-20% OOS slice.
  (c) ETH instrument holdout: if a *ETH* cache exists, run the SAME cfg
      (no retuning) and print n / win% / gross + all 3 cost scenarios.
      If absent, skip WITHOUT touching the network.

Writes runs/validation.json. Run:
    python3 -m backtesting.tjr_4x.run_validation
"""

from __future__ import annotations

import glob
import json
import os

from .config import Config
from .validation import (load_5m, walk_forward, cost_scenarios, run_symbol,
                         _gross_expR, _BEST, _CACHE)
from .engine import recost_trade, metrics_from_closed
from dataclasses import replace


def _oos_slice(closed):
    """Last-20% slice by entry_time (cutoff = first + 0.8*(last-first))."""
    ets = [c.entry_time for c in closed]
    first_ts, last_ts = min(ets), max(ets)
    cutoff = first_ts + 0.8 * (last_ts - first_ts)
    return [c for c in closed if c.entry_time >= cutoff], cutoff


def _pf_str(pf):
    return "inf" if pf == float("inf") else f"{pf:.2f}"


def _print_walk_forward(folds):
    header = (f"{'fold':<5}{'start':<22}{'end':<22}{'n':>4}"
              f"{'win%':>7}{'gross':>9}{'net':>9}")
    print(header)
    print("-" * len(header))
    for f in folds:
        print(f"{f['fold']:<5}{f['start'][:19]:<22}{f['end'][:19]:<22}"
              f"{f['n']:>4}{f['win_rate']*100:>6.1f}%"
              f"{f['gross_expR']:>+9.3f}{f['net_expR']:>+9.3f}")


def _print_cost_table(label, rows):
    header = (f"{label:<14}{'r':>5}{'trades':>8}{'net_expR':>10}"
              f"{'PF':>7}{'net_R':>9}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['scenario']:<14}{r['entry_taker_ratio']:>5.1f}"
              f"{r['trades']:>8}{r['net_expR']:>+10.3f}"
              f"{_pf_str(r['profit_factor']):>7}{r['net_R']:>+9.1f}")


def main() -> None:
    base = Config(**_BEST)
    payload = {"best_config": _BEST}

    # ============================ BTC ================================= #
    print("=" * 64)
    print("BTC  (in-sample instrument — walk-forward + cost-mix stress)")
    print("=" * 64)
    btc = run_symbol("*BTC*_5m_*.csv", base)
    closed = btc["closed"]
    print(f"loaded {btc['bars']:,} bars -> {len(closed)} closed trades "
          f"(C bias + 0.2% min-stop + fixed 2R)\n")

    # ---- (a) walk-forward -------------------------------------------- #
    print("--- WALK-FORWARD (6 equal-time folds, maker r=0) ---")
    folds = walk_forward(closed, k=6)
    _print_walk_forward(folds)
    n_pos = sum(1 for f in folds if f["gross_expR"] > 0)
    print(f"\ngross-positive folds: {n_pos}/{len(folds)}\n")

    # ---- (b) cost scenarios: FULL + OOS ------------------------------ #
    full_cost = cost_scenarios(closed, base)
    oos, cutoff = _oos_slice(closed)
    oos_cost = cost_scenarios(oos, base)
    print("--- COST-MIX STRESS: FULL sample ---")
    _print_cost_table("scenario", full_cost)
    print(f"\n--- COST-MIX STRESS: OOS (last 20%, cutoff {str(cutoff)[:19]}, "
          f"n={len(oos)}) ---")
    _print_cost_table("scenario", oos_cost)

    payload["btc"] = {
        "bars": btc["bars"],
        "closed": len(closed),
        "walk_forward": folds,
        "gross_positive_folds": n_pos,
        "cost_full": full_cost,
        "cost_oos": oos_cost,
        "oos_cutoff": str(cutoff),
        "oos_n": len(oos),
    }

    # ============================ ETH ================================= #
    print("\n" + "=" * 64)
    print("ETH  (instrument holdout — SAME cfg, no retuning)")
    print("=" * 64)
    eth_matches = glob.glob(os.path.join(_CACHE, "*ETH*_5m_*.csv"))
    if not eth_matches:
        print("ETH cache not present — skipped")
        payload["eth"] = {"status": "skipped (no cache)"}
    else:
        eth = run_symbol("*ETH*_5m_*.csv", base)
        eclosed = eth["closed"]
        eres = eth["result"]
        egross = _gross_expR(eclosed, base)
        ecost = cost_scenarios(eclosed, base)
        print(f"loaded {eth['bars']:,} bars -> {len(eclosed)} closed trades")
        print(f"win% {eres.win_rate*100:.1f}   gross_expR {egross:+.3f}")
        print("--- ETH cost-mix stress ---")
        _print_cost_table("scenario", ecost)
        payload["eth"] = {
            "status": "run",
            "bars": eth["bars"],
            "closed": len(eclosed),
            "win_rate": eres.win_rate,
            "gross_expR": egross,
            "cost_scenarios": ecost,
        }

    # ============================ persist ============================= #
    out_dir = os.path.join(os.path.dirname(__file__), "runs")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "validation.json")
    with open(out, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
