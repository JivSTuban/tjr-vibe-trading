"""Causality + catalyst study on top of the base backtest.

    PYTHONPATH=. uv run python -m backtesting.eod_pressure_reversal.run_causality

Question: does separating PRESSURE (the whole demand chain fell, the stock was carried)
from INFORMATION (the chain held up and this name broke) recover the edge the base
strategy does not have?

Secondary question, and the one that keeps this honest: does a demand narrative show up
in the data WITHOUT being told? If AI demand really did lift semis, rare earths, copper,
uranium and power from 2023 on, those baskets must appear as tailwind themes in
2023-2026 purely from trailing relative strength. If they do not, the narrative is not
in the returns and no overlay built on it can work.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import causality, earnings, metrics, run as base_run, strategy

COMMON_CUT = 0.5
POOLS = {"V1 top-5 (stage 7)": 7, "wider pool (stage 4)": 4}


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def attach_causality(cands: pd.DataFrame, frames: dict[str, pd.DataFrame],
                     themes: pd.DataFrame, strength: pd.DataFrame) -> pd.DataFrame:
    """Join per-(ticker, date) causal features onto the candidate table."""
    parts = []
    for tkr, df in frames.items():
        r = df["close"].pct_change()
        label = causality.assign_theme(r, themes)
        if label.notna().sum() == 0:
            continue
        dec = causality.decompose(r, themes, label)
        dec["ticker"] = tkr
        # Theme strength is per (date, theme); pick the row's own theme.
        s = pd.Series(np.nan, index=dec.index)
        for etf in pd.unique(label.dropna()):
            if etf in strength:
                m = (label == etf).to_numpy()
                s[m] = strength[etf].reindex(dec.index)[m]
        dec["theme_strength"] = s
        parts.append(dec.reset_index().rename(columns={"index": "date"}))
    if not parts:
        return cands
    feat = pd.concat(parts, ignore_index=True)
    keep = ["date", "ticker", "theme", "beta", "theme_ret", "common", "residual",
            "common_share", "theme_strength"]
    return cands.merge(feat[keep], on=["date", "ticker"], how="left")


def cell_table(trades: pd.DataFrame, by: str, ret_col: str = "gross_ret") -> pd.DataFrame:
    """Per-bucket summary with a t-stat, so a pretty split can be checked for noise."""
    rows = []
    for label, grp in trades.dropna(subset=[by]).groupby(by):
        r = grp[ret_col].dropna()
        if r.empty:
            continue
        se = r.std(ddof=1) / np.sqrt(r.size) if r.size > 1 else np.nan
        rows.append({
            by: str(label),
            "n": int(r.size),
            "win_rate": float((r > 0).mean()),
            "mean_bps": float(r.mean() * 1e4),
            "median_bps": float(r.median() * 1e4),
            "t_stat": float(r.mean() / se) if se and se > 0 else np.nan,
            "worst": float(r.min()),
        })
    return pd.DataFrame(rows).sort_values("mean_bps", ascending=False).reset_index(drop=True)


def discovered_themes(strength: pd.DataFrame, per_year: bool = True) -> dict:
    """Which baskets were in demand each year, discovered from relative strength alone.

    This is the audit of the look-ahead question. Nothing here is told what the demand
    narrative is; it simply reports which chains were beating SPY when.
    """
    out = {}
    s = strength.copy()
    s["year"] = s.index.year
    for y, grp in s.groupby("year"):
        means = grp.drop(columns=["year"]).mean().dropna().sort_values(ascending=False)
        if means.empty:
            continue
        out[int(y)] = {
            "top": [(k, round(float(v) * 100, 2)) for k, v in means.head(3).items()],
            "bottom": [(k, round(float(v) * 100, 2)) for k, v in means.tail(2).items()],
        }
    return out


def run() -> dict:
    bundle = base_run.load_everything()
    log("building candidate table")
    cands = base_run.build_candidate_table(bundle)
    blocked = earnings.blocked_pairs(bundle["earn_idx"], pd.DatetimeIndex(bundle["sessions"]))

    log("fetching theme ETFs")
    theme_frames = causality.fetch_theme_prices(base_run.START, base_run.END,
                                                fmp_key=base_run._key("stock-scan-fmp"))
    log(f"  {len(theme_frames)}/{len(causality.THEME_ETFS)} theme ETFs")
    themes = causality.theme_returns(theme_frames)
    spy_ret = bundle["bench"]["SPY"]["close"].pct_change()
    strength = causality.theme_strength(themes, spy_ret)

    log("assigning themes + decomposing returns (PIT)")
    cands = attach_causality(cands, bundle["frames"], themes, strength)
    cov = float(cands["common_share"].notna().mean())
    log(f"  causal features on {cov*100:.1f}% of candidate rows")

    results = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "window": f"{base_run.START}..{base_run.END}",
        "common_cut": COMMON_CUT,
        "feature_coverage": cov,
        "discovered_themes_by_year": discovered_themes(strength),
        "pools": {},
    }

    for pool_name, stage in POOLS.items():
        trades = strategy.simulate(
            strategy.apply_stage(cands, stage, blocked, top_n=5), cost_bps=0.0)
        trades = causality.label_cells(trades, common_cut=COMMON_CUT)
        log(f"{pool_name}: {len(trades):,} trades")

        pool = {
            "n_trades": int(len(trades)),
            "all_mean_bps": float(trades["gross_ret"].mean() * 1e4),
            "by_cause": cell_table(trades, "cause").to_dict("records"),
            "by_demand": cell_table(trades, "demand").to_dict("records"),
            "by_cell": cell_table(trades, "cell").to_dict("records"),
            "by_theme": cell_table(trades, "theme").to_dict("records"),
        }
        # Continuous check: does the reversal rise monotonically with common_share?
        q = trades.dropna(subset=["common_share"]).copy()
        if len(q) > 100:
            q["bucket"] = pd.qcut(q["common_share"], 5, labels=[f"Q{i+1}" for i in range(5)],
                                  duplicates="drop")
            pool["by_common_share_quintile"] = cell_table(q, "bucket").to_dict("records")
        # The decisive robustness check. The base strategy's whole edge lived in
        # 2024-2025, so a causal cell that ALSO only works then is the same regime
        # finding wearing a new label, not a mechanism.
        best = trades[trades["cell"] == "PRESSURE / TAILWIND"]
        if len(best) > 50:
            pool["best_cell_by_year"] = metrics.by_year(best, "gross_ret").to_dict("records")
            pool["best_cell_oos"] = metrics.by_period(best, base_run.SPLITS, "gross_ret").to_dict("records")
            pool["best_cell_costs"] = [
                {"cost_bps_per_side": c,
                 **metrics.trade_metrics(strategy.simulate(best, cost_bps=c))}
                for c in base_run.COST_BPS
            ]
            pool["best_cell_left_tail"] = metrics.left_tail(best, "gross_ret")
            pool["best_cell_jackknife"] = metrics.jackknife_years(best, "gross_ret")
            # Corrected to the spec's real 3:55 entry and 9:35 exit, using the
            # intraday calibration constants (see calibrate.py / FINDINGS §4).
            pool["best_cell_spec_adjusted_bps"] = float(
                best["gross_ret"].mean() * 1e4 - 1.11 - 3.96)
        results["pools"][pool_name] = pool

        for row in pool["by_cell"]:
            log(f"  {row['cell']:<26} n={row['n']:>6,} mean={row['mean_bps']:>7.2f}bps "
                f"win={row['win_rate']*100:>5.1f}% t={row['t_stat']:>6.2f}")

    out_dir = os.path.join(os.path.dirname(__file__), "runs",
                           datetime.now().strftime("%Y%m%d-%H%M%S") + "-causality")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "causality.json"), "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    log(f"wrote {out_dir}")
    return results


if __name__ == "__main__":
    run()
