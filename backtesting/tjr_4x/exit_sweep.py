"""Iteration-3 exit-model + min-stop sweep.

Unlike ``bias_sweep`` (which reuses one candidate pool and post-filters by
bias), the exit model changes the TP price *at creation*, and the min-stop
filter changes which setups survive -- so ``find_trades`` is re-run per
config. Bias is fixed to the promoted default (mode C); one config adds 4H
confluence. Each config's trades are resolved by the same forward-only
engine (now variable-R aware).

Metrics printed: config, trades, win%, avg_planned_rr (mean planned
reward:risk of resolved trades), exp_R (net expectancy), PF, net_R, maxDD_R.

Uses the cached 5m CSV in .cache/ if present (no re-fetch). Run:
    python3 -m backtesting.tjr_4x.exit_sweep
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from .config import Config
from .strategy import find_trades
from .engine import backtest

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")


# name -> Config kwargs (bias fixed to C = the promoted default).
_CONFIGS = {
    "C_fixed2R":               dict(bias_mode="C", exit_model="fixed_rr",
                                    min_stop_pct=0.0),
    "C_fixed2R_minstop":       dict(bias_mode="C", exit_model="fixed_rr",
                                    min_stop_pct=0.002),
    "C_oppliq":                dict(bias_mode="C", exit_model="opposite_liquidity",
                                    min_rr=1.0, min_stop_pct=0.0),
    "C_oppliq_minstop":        dict(bias_mode="C", exit_model="opposite_liquidity",
                                    min_rr=1.0, min_stop_pct=0.002),
    "C_oppliq_minstop_rr1.5":  dict(bias_mode="C", exit_model="opposite_liquidity",
                                    min_rr=1.5, min_stop_pct=0.002),
    "C4h_oppliq_minstop":      dict(bias_mode="C", use_4h_confluence=True,
                                    exit_model="opposite_liquidity",
                                    min_rr=1.0, min_stop_pct=0.002),
}


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


def _planned_rr(ct) -> float:
    """Planned reward:risk of a closed trade from its stored prices."""
    risk = abs(ct.entry - ct.sl)
    return (abs(ct.tp - ct.entry) / risk) if risk > 0 else 0.0


def main() -> None:
    base = Config()
    df5m = _load_5m(base)
    print(f"loaded {len(df5m):,} bars\n")

    header = (f"{'config':<24}{'trades':>7}{'win%':>8}{'avg_rr':>8}"
              f"{'exp_R':>9}{'PF':>7}{'net_R':>9}{'maxDD_R':>9}")
    print(header)
    print("-" * len(header))
    rows = []
    for name, kw in _CONFIGS.items():
        cfg = Config(**kw)
        trades = find_trades(df5m, cfg)
        res = backtest(df5m, trades, cfg)
        rr_vals = [_planned_rr(ct) for ct in res.closed_trades]
        avg_rr = (sum(rr_vals) / len(rr_vals)) if rr_vals else 0.0
        pf = res.profit_factor if res.profit_factor != float("inf") else 999
        rows.append({
            "config": name, "trades": res.trade_count,
            "win_rate": res.win_rate, "avg_planned_rr": avg_rr,
            "avg_R": res.avg_R, "profit_factor": res.profit_factor,
            "net_return_R": res.net_return_R,
            "max_drawdown_R": res.max_drawdown_R,
        })
        print(f"{name:<24}{res.trade_count:>7}{res.win_rate*100:>7.1f}%"
              f"{avg_rr:>8.2f}{res.avg_R:>9.3f}{pf:>7.2f}"
              f"{res.net_return_R:>9.1f}{res.max_drawdown_R:>9.1f}")

    out_dir = os.path.join(os.path.dirname(__file__), "runs")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "exit_sweep.json")
    with open(out, "w") as f:
        json.dump(rows, f, indent=2, default=str)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
