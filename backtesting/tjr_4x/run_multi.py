"""Multi-instrument robustness CLI (iteration 6).

Runs the best config (C bias + 0.2% min-stop + fixed 2R) UNCHANGED across
every distinct cached symbol, then reports:

  * Per-instrument table: bars, trades, win%, gross_expR, net@maker(0.0),
    net@realistic(0.5), net@taker(1.0), PF@realistic.
  * Breadth: of N instruments, how many have gross_expR>0 and how many have
    net@realistic>0.
  * Pooled: total trades, pooled gross_expR, pooled net@realistic, pooled PF.
  * Equal-trade walk-forward (k=8) on the pooled trades: per-fold gross and
    net@realistic (equal-COUNT folds — no empty folds from dry spells).

Writes runs/multi_instrument.json. No network (cached CSVs only). Run:
    python3 -m backtesting.tjr_4x.run_multi
"""

from __future__ import annotations

import json
import os
from dataclasses import replace

from .config import Config
from .engine import metrics_from_closed, recost_trade
from .validation import (_BEST, _gross_expR, cost_scenarios,
                         equal_trade_walk_forward)
from .multi_instrument import run_universe, pooled_closed


def _pf_str(pf) -> str:
    return "inf" if pf == float("inf") else f"{pf:.2f}"


def _net_at(closed, base, r):
    """net_expR of ``closed`` under maker_taker at entry_taker_ratio ``r``."""
    cfg = replace(base, cost_model="maker_taker", entry_taker_ratio=r)
    return metrics_from_closed([recost_trade(c, cfg) for c in closed]).avg_R


def _instrument_rows(universe, base):
    rows = []
    for sym, (closed, res) in universe.items():
        realistic = replace(base, cost_model="maker_taker", entry_taker_ratio=0.5)
        res_real = metrics_from_closed([recost_trade(c, realistic) for c in closed])
        rows.append({
            "symbol": sym,
            "bars": getattr(res, "bars", 0),
            "trades": len(closed),
            "win_rate": res_real.win_rate,
            "gross_expR": _gross_expR(closed, base) if closed else 0.0,
            "net_maker": _net_at(closed, base, 0.0) if closed else 0.0,
            "net_realistic": res_real.avg_R,
            "net_taker": _net_at(closed, base, 1.0) if closed else 0.0,
            "pf_realistic": res_real.profit_factor,
        })
    rows.sort(key=lambda r: r["symbol"])
    return rows


def _print_instrument_table(rows):
    header = (f"{'sym':<6}{'bars':>9}{'trades':>7}{'win%':>7}{'gross':>9}"
              f"{'net@0.0':>9}{'net@0.5':>9}{'net@1.0':>9}{'PF@0.5':>8}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['symbol']:<6}{r['bars']:>9,}{r['trades']:>7}"
              f"{r['win_rate']*100:>6.1f}%{r['gross_expR']:>+9.3f}"
              f"{r['net_maker']:>+9.3f}{r['net_realistic']:>+9.3f}"
              f"{r['net_taker']:>+9.3f}{_pf_str(r['pf_realistic']):>8}")


def _print_walk_forward(folds):
    header = (f"{'fold':<5}{'n':>5}{'start':<22}{'end':<22}"
              f"{'gross':>9}{'net@0.5':>9}")
    print(header)
    print("-" * len(header))
    for f in folds:
        start = (f["start"] or "")[:19]
        end = (f["end"] or "")[:19]
        print(f"{f['fold']:<5}{f['n']:>5}{start:<22}{end:<22}"
              f"{f['gross_expR']:>+9.3f}{f['net_realistic']:>+9.3f}")


def main() -> None:
    base = Config(**_BEST)
    payload = {"best_config": _BEST}

    print("=" * 78)
    print("MULTI-INSTRUMENT ROBUSTNESS  (best config, no retuning)")
    print("=" * 78)

    universe = run_universe(base)
    if not universe:
        print("no cached instruments found — nothing to run (no network).")
        payload["instruments"] = []
        _write(payload)
        return

    # ---- per-instrument table --------------------------------------- #
    rows = _instrument_rows(universe, base)
    _print_instrument_table(rows)
    payload["instruments"] = rows

    # ---- breadth ----------------------------------------------------- #
    n = len(rows)
    n_gross_pos = sum(1 for r in rows if r["gross_expR"] > 0)
    n_net_pos = sum(1 for r in rows if r["net_realistic"] > 0)
    print(f"\nBREADTH: of {n} instruments, {n_gross_pos} have gross_expR>0 "
          f"and {n_net_pos} have net@realistic>0")
    payload["breadth"] = {
        "n_instruments": n,
        "gross_positive": n_gross_pos,
        "net_realistic_positive": n_net_pos,
    }

    # ---- pooled ------------------------------------------------------ #
    pooled = pooled_closed(universe)
    pooled_gross = _gross_expR(pooled, base) if pooled else 0.0
    realistic = replace(base, cost_model="maker_taker", entry_taker_ratio=0.5)
    pooled_real = metrics_from_closed([recost_trade(c, realistic) for c in pooled])
    print(f"\nPOOLED: {len(pooled)} trades  gross_expR {pooled_gross:+.3f}  "
          f"net@realistic {pooled_real.avg_R:+.3f}  PF {_pf_str(pooled_real.profit_factor)}")
    payload["pooled"] = {
        "trades": len(pooled),
        "gross_expR": pooled_gross,
        "net_realistic": pooled_real.avg_R,
        "profit_factor": (None if pooled_real.profit_factor == float("inf")
                          else pooled_real.profit_factor),
        "cost_scenarios": cost_scenarios(pooled, base) if pooled else [],
    }

    # ---- equal-trade walk-forward (k=8) on the pool ------------------ #
    print("\n--- EQUAL-TRADE WALK-FORWARD (k=8, pooled) ---")
    folds = equal_trade_walk_forward(pooled, k=8)
    _print_walk_forward(folds)
    wf_gross_pos = sum(1 for f in folds if f["gross_expR"] > 0)
    print(f"\ngross-positive folds: {wf_gross_pos}/{len(folds)}")
    payload["walk_forward_equal_trade"] = folds

    _write(payload)


def _write(payload) -> None:
    out_dir = os.path.join(os.path.dirname(__file__), "runs")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "multi_instrument.json")
    with open(out, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
