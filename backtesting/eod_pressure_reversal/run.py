"""Driver: fetch -> stage sweep -> cost stress -> OOS split -> regimes -> left tail.

    PYTHONPATH=. uv run python -m backtesting.eod_pressure_reversal.run

Writes runs/<timestamp>/{results.json, trades.csv, dashboard.html, manifest.json}.
The manifest carries the data-coverage numbers (how many PIT tickers had no price
source) because that is the survivorship disclosure, and a result quoted without it
is not interpretable.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import earnings, metrics, prices, signals, strategy, universe, viz

START = "2014-01-01"
END = "2026-09-10"

# Spec §11 out-of-sample design.
SPLITS = {
    "development 2014-2021": ("2014-01-01", "2021-12-31"),
    "validation 2022-2024": ("2022-01-01", "2024-12-31"),
    "final untouched 2025-2026": ("2025-01-01", "2026-09-10"),
}
COST_BPS = [0.0, 2.0, 5.0, 10.0]          # spec §8, per side

# Spec §10 robustness grid.
ROBUSTNESS = {
    "day_ret": [-0.005, -0.010, -0.015, -0.020, -0.025, -0.030, -0.040],
    "close_loc": [0.10, 0.20, 0.25, 0.35],        # proxy for the late-decline threshold
    "dd_from_high": [-0.01, -0.02, -0.03, -0.04],
    "rel_sector": [-0.005, -0.010, -0.015, -0.020],
    "rel_vol": [1.0, 1.25, 1.5, 2.0],
}


def _key(service: str) -> str | None:
    try:
        return subprocess.check_output(
            ["security", "find-generic-password", "-s", service, "-a", "api", "-w"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return None


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_everything(use_cache: bool = True) -> dict:
    """Fetch membership, sectors, benchmarks, prices, earnings. Returns a bundle."""
    log("membership (point-in-time S&P 500)")
    membership = universe.fetch_membership(use_cache=use_cache)
    tickers = universe.universe_tickers(membership, START, END)
    log(f"  {len(tickers)} tickers were index members at some point in {START[:4]}-{END[:4]}")

    log("sector map (Wikipedia GICS)")
    sectors = universe.fetch_sectors(use_cache=use_cache)
    sector_map = dict(zip(sectors["ticker"], sectors["sector"]))

    fmp = _key("stock-scan-fmp")
    log("benchmarks (SPY, ^VIX, sector ETFs)")
    bench_frames, bench_missing = prices.load_panel(
        universe.BENCHMARKS, START, END, fmp_key=fmp, use_cache=use_cache
    )
    if bench_missing:
        log(f"  WARNING missing benchmarks: {bench_missing}")

    log(f"prices for {len(tickers)} tickers (cached after first run)")
    frames, missing = prices.load_panel(
        tickers, START, END, fmp_key=fmp, use_cache=use_cache,
        progress=lambda i, ok, miss: log(f"  {i}/{len(tickers)} ok={ok} missing={miss}"),
    )
    log(f"  price coverage {len(frames)}/{len(tickers)} ({100*len(frames)/max(len(tickers),1):.1f}%)")

    sessions = bench_frames["SPY"].index
    log(f"earnings calendar for {len(sessions)} sessions (cached after first run)")
    cal = earnings.fetch_range(
        sessions, use_cache=use_cache,
        progress=lambda i, n: log(f"  {i}/{n} sessions"),
    )
    earn_idx = earnings.build_index(cal)
    log(f"  {len(earn_idx)} earnings events")

    return {
        "membership": membership, "tickers": tickers, "sector_map": sector_map,
        "frames": frames, "missing": missing, "bench": bench_frames,
        "sessions": sessions, "earn_idx": earn_idx,
    }


def build_candidate_table(bundle: dict) -> pd.DataFrame:
    """Feature engineering across the panel -> one tidy candidate table."""
    bench_ret = {t: df["close"].pct_change() for t, df in bundle["bench"].items()}
    membership, frames = bundle["membership"], bundle["frames"]

    features, memb_mask, action_mask = {}, {}, {}
    starts = dict(zip(membership["ticker"], membership["start"]))
    ends = dict(zip(membership["ticker"], membership["end"]))

    for tkr, df in frames.items():
        etf = universe.resolve_sector_etf(bundle["sector_map"], tkr)
        b = bench_ret.get(etf, bench_ret["SPY"])
        features[tkr] = signals.compute_features(df, b)
        s, e = starts.get(tkr), ends.get(tkr)
        m = pd.Series(True, index=df.index)
        if s is not None and pd.notna(s):
            m &= df.index >= s
        if e is not None and pd.notna(e):
            m &= df.index <= e
        memb_mask[tkr] = m
        # Drop the signal day AND the day before a corporate action: the overnight
        # leg straddles t -> t+1, so an ex-date on t+1 contaminates a signal on t.
        act = prices.flag_corporate_actions(df)
        action_mask[tkr] = act | act.shift(-1).fillna(False)

    cands = strategy.build_candidates(
        features, membership_mask=memb_mask, action_mask=action_mask
    )
    return cands


def run() -> dict:
    t0 = time.time()
    bundle = load_everything()
    log("building candidate table")
    cands = build_candidate_table(bundle)
    log(f"  {len(cands):,} tradable (date, ticker) rows across {cands['date'].nunique():,} sessions")

    blocked = earnings.blocked_pairs(bundle["earn_idx"], pd.DatetimeIndex(bundle["sessions"]))
    log(f"  {len(blocked):,} (date, ticker) pairs blocked by the earnings window")

    spy = bundle["bench"]["SPY"]
    spy_ret = spy["close"].pct_change()
    vix = bundle["bench"]["^VIX"]["close"]
    n_sessions = len(spy.loc[START:END])

    results: dict = {
        "spec": "EOD Pressure Reversal V1",
        "window": f"{START}..{END}",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }

    # ---- Spec §9: staged build order, GROSS -----------------------------------
    # Gross, not net: §9 asks WHERE the edge comes from, and a flat cost charge of
    # 10 bps round trip swamps an effect this size and hides the filter-by-filter
    # structure. Costs get their own section immediately below.
    log("stage sweep (spec §9, gross)")
    stages = []
    for st in range(8):
        trades = strategy.simulate(strategy.apply_stage(cands, st, blocked), cost_bps=0.0)
        m = metrics.trade_metrics(trades)
        daily = strategy.equity_curve(trades)
        m.update({"stage": st, "label": strategy.STAGE_LABELS[st]})
        m.update({f"pf_{k}": v for k, v in metrics.portfolio_metrics(daily, n_sessions).items()})
        stages.append(m)
        log(f"  stage {st} {strategy.STAGE_LABELS[st]:<24} n={m.get('n_trades',0):>7,} "
            f"mean={m.get('mean_ret',0)*1e4:>7.2f}bps win={m.get('win_rate',0)*100:>5.1f}%")
    results["stages"] = stages

    # ---- The full V1 strategy (stage 7) ---------------------------------------
    final = strategy.apply_stage(cands, 7, blocked, top_n=5)
    log(f"final V1 strategy: {len(final):,} trades")

    cost_rows = []
    for bps in COST_BPS:
        t = strategy.simulate(final, cost_bps=bps)
        daily = strategy.equity_curve(t)
        m = metrics.trade_metrics(t)
        m.update({f"pf_{k}": v for k, v in metrics.portfolio_metrics(daily, n_sessions).items()})
        m["cost_bps_per_side"] = bps
        cost_rows.append(m)
        log(f"  cost {bps:>4.1f}bps/side  mean={m['mean_ret']*1e4:>7.2f}bps  "
            f"PF={m['profit_factor']:.3f}  sharpe={m['pf_sharpe']:.2f}  "
            f"total={m['pf_total_return']*100:.1f}%")
    results["cost_stress"] = cost_rows

    baseline = strategy.simulate(final, cost_bps=5.0)
    gross = strategy.simulate(final, cost_bps=0.0)
    tagged = metrics.tag_regimes(baseline, vix, spy_ret)
    daily = strategy.equity_curve(baseline)

    results["headline_gross"] = metrics.trade_metrics(gross)
    results["headline_gross"].update(
        {f"pf_{k}": v for k, v in metrics.portfolio_metrics(strategy.equity_curve(gross), n_sessions).items()}
    )
    results["breakeven_bps_per_side"] = float(results["headline_gross"]["mean_ret"] * 1e4 / 2.0)
    results["oos_gross"] = metrics.by_period(gross, SPLITS).to_dict("records")
    results["by_year_gross"] = metrics.by_year(gross).to_dict("records")
    results["headline"] = metrics.trade_metrics(baseline)
    results["headline"].update(
        {f"pf_{k}": v for k, v in metrics.portfolio_metrics(daily, n_sessions).items()}
    )
    results["oos"] = metrics.by_period(baseline, SPLITS).to_dict("records")
    results["by_year"] = metrics.by_year(baseline).to_dict("records")
    results["regime_vix"] = metrics.regime_table(tagged, "vix_bucket").to_dict("records")
    results["regime_spy"] = metrics.regime_table(tagged, "spy_bucket").to_dict("records")
    results["left_tail"] = metrics.left_tail(baseline)
    results["worst_trades"] = metrics.worst_trades(baseline, n=25).assign(
        date=lambda d: d["date"].astype(str)
    ).to_dict("records")

    # ---- Spec §10: one-at-a-time parameter robustness --------------------------
    log("robustness sweep (spec §10)")
    robust = {}
    for param, values in ROBUSTNESS.items():
        rows = []
        for v in values:
            variant = strategy.apply_stage(_reflag(cands, {param: v}), 7, blocked, top_n=5)
            t = strategy.simulate(variant, cost_bps=5.0)
            m = metrics.trade_metrics(t)
            m["value"] = v
            rows.append(m)
            log(f"  {param:<14} {v:>7} n={m.get('n_trades',0):>6,} mean={m.get('mean_ret',0)*1e4:>7.2f}bps")
        robust[param] = rows
    results["robustness"] = robust

    # ---- Benchmarks ------------------------------------------------------------
    results["benchmark"] = _benchmark_context(spy, gross, cands, blocked)

    results["coverage"] = {
        "pit_tickers": len(bundle["tickers"]),
        "priced": len(bundle["frames"]),
        "missing": len(bundle["missing"]),
        "missing_tickers": sorted(bundle["missing"])[:80],
        "sessions": int(n_sessions),
        "earnings_events": int(len(bundle["earn_idx"])),
        "earnings_blocked_pairs": len(blocked),
    }
    results["runtime_sec"] = round(time.time() - t0, 1)

    out_dir = os.path.join(os.path.dirname(__file__), "runs",
                           datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "results.json"), "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    baseline.assign(date=lambda d: d["date"].astype(str)).to_csv(
        os.path.join(out_dir, "trades.csv"), index=False)
    daily.assign(date=lambda d: d["date"].astype(str)).to_csv(
        os.path.join(out_dir, "daily.csv"), index=False)
    viz.write_dashboard(results, daily, os.path.join(out_dir, "dashboard.html"))
    log(f"wrote {out_dir}")
    return results


def _reflag(cands: pd.DataFrame, override: dict) -> pd.DataFrame:
    """Re-evaluate the filter flags with one threshold overridden (spec §10)."""
    df = cands.drop(columns=[c for c in cands.columns if c[:2] in ("A_", "B_", "C_", "D_", "E_")])
    return pd.concat([df, signals.passes(df, override)], axis=1)


def _benchmark_context(spy: pd.DataFrame, trades: pd.DataFrame,
                       cands: pd.DataFrame, blocked: set) -> dict:
    """What the same overnight window paid unconditionally.

    This is the comparison that matters: if buying ANY red S&P name overnight pays the
    same as the filtered strategy, the six filters are decoration.
    """
    spy_on = (spy["open"].shift(-1) / spy["close"] - 1.0).dropna()
    red = strategy.simulate(cands[cands["day_ret"] < 0], cost_bps=0.0)
    allc = strategy.simulate(cands, cost_bps=0.0)
    return {
        "spy_overnight_mean_bps": float(spy_on.mean() * 1e4),
        "spy_overnight_n": int(spy_on.size),
        "any_stock_overnight_mean_bps": float(allc["net_ret"].mean() * 1e4),
        "any_red_stock_overnight_mean_bps": float(red["net_ret"].mean() * 1e4),
        "any_stock_overnight_n": int(allc["gross_ret"].notna().sum()),
        "any_red_stock_overnight_n": int(red["gross_ret"].notna().sum()),
        "strategy_mean_bps": float(trades["gross_ret"].mean() * 1e4),
        "note": "all legs GROSS (no cost) so the comparison is like for like",
    }


if __name__ == "__main__":
    run()
