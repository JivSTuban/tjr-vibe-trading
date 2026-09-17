"""Intraday calibration: run the EXACT spec on the 60-day 5m window.

    PYTHONPATH=. uv run python -m backtesting.eod_pressure_reversal.calibrate

Three questions the full-history daily run cannot answer about itself:

1. ENTRY BIAS. The daily run buys at the official close; the spec buys at 3:55 PM.
   If these stocks keep sliding into the bell, buying at the close is buying cheaper
   than the spec allows, and the daily result is optimistic by that amount. §3 calls
   this out by name and it is the single most likely way this backtest flatters itself.
2. EXIT CHOICE. Variant A (9:30 open) vs B (9:35) vs C (10:00) — the daily run can
   only do A, and the spec's baseline is B.
3. PROXY FIDELITY. Does "closed in the bottom quarter of its range" actually select
   the same sessions as "fell >=0.5% between 3:30 and 3:50"? Same for whole-day
   relative volume vs the 3:30-3:50 window. Reported as hit/miss rates, not vibes.

Sample is small by construction (60 sessions). It calibrates bias; it does not decide
the strategy.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import requests

from . import intraday, metrics, signals, strategy, universe

N_NAMES = None          # None = every current index member
LATE_RET_THRESH = -0.005
LATE_VOL_WINDOW = 20


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def sector_returns_1550(bench_frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    """Per sector ETF: its own 3:50 PM return vs the prior close.

    Filter D carries 25% of the ranking weight, so measuring it against a DAILY sector
    return while the stock leg is intraday would compare two different clocks. Both
    legs are taken at 15:50 here.
    """
    out: dict[str, pd.Series] = {}
    for etf, df in bench_frames.items():
        sessions = intraday.session_frames(df)
        days = sorted(sessions)
        vals = {}
        for i, d in enumerate(days):
            if i == 0:
                continue
            prev_close = float(sessions[days[i - 1]]["close"].iloc[-1])
            p1550 = intraday._at(sessions[d], intraday.SIGNAL_T)
            if prev_close and not np.isnan(p1550):
                vals[d] = p1550 / prev_close - 1.0
        out[etf] = pd.Series(vals)
    return out


def build_exact_table(frames: dict[str, pd.DataFrame],
                      sector_ret: dict[str, pd.Series] | None = None,
                      sector_map: dict[str, str] | None = None) -> pd.DataFrame:
    """Per (date, ticker): exact spec features + the daily proxies + all three exits."""
    rows = []
    for tkr, df in frames.items():
        sessions = intraday.session_frames(df)
        days = sorted(sessions)
        if len(days) < LATE_VOL_WINDOW + 2:
            continue
        late_vols: list[float] = []
        full_vols: list[float] = []
        for i, d in enumerate(days[:-1]):
            bars = sessions[d]
            prev_close = float(sessions[days[i - 1]]["close"].iloc[-1]) if i else np.nan
            f = intraday.exact_session_features(bars, prev_close)

            # Spec E: late volume vs the median of the SAME window over prior 20 days.
            # Both histories exclude today, mirroring signals.compute_features.
            hist = late_vols[-LATE_VOL_WINDOW:]
            f["late_rel_vol"] = (f["late_vol"] / np.median(hist)
                                 if len(hist) >= LATE_VOL_WINDOW and np.median(hist) > 0 else np.nan)
            full_hist = full_vols[-LATE_VOL_WINDOW:]
            f["full_rel_vol"] = (f["full_day_vol"] / np.median(full_hist)
                                 if len(full_hist) >= LATE_VOL_WINDOW and np.median(full_hist) > 0 else np.nan)
            late_vols.append(f["late_vol"])
            full_vols.append(f["full_day_vol"])

            # Filter D, both legs measured at 15:50.
            f["rel_sector_exact"] = np.nan
            if sector_ret and sector_map is not None:
                etf = universe.resolve_sector_etf(sector_map, tkr)
                series = sector_ret.get(etf)
                if series is not None and d in series.index and not np.isnan(f["day_ret_exact"]):
                    f["rel_sector_exact"] = f["day_ret_exact"] - float(series.loc[d])

            f.update(intraday.next_morning_prices(sessions[days[i + 1]]))
            f["date"], f["ticker"] = d, tkr
            rows.append(f)
    return pd.DataFrame(rows)


def entry_and_exit_bias(tbl: pd.DataFrame) -> dict:
    """Q1 + Q2, measured only on sessions that actually look like signals.

    Restricting to genuine selloff sessions matters: the 3:55-to-close drift on a
    random session is not the drift on a session that has been dumping all afternoon,
    and it is the latter the strategy would be trading.
    """
    sel = tbl[(tbl["day_ret_exact"] <= -0.015) & (tbl["dd_high_exact"] <= -0.02)].dropna(
        subset=["entry_1555", "close", "exit_open", "exit_0935"]
    )
    if sel.empty:
        return {"n": 0}
    # Buying at the close instead of 15:55: positive = the close was cheaper = the
    # daily backtest gets a discount the spec does not allow.
    entry_edge = (sel["entry_1555"] / sel["close"] - 1.0)
    return {
        "n": int(len(sel)),
        "close_vs_1555_mean_bps": float(entry_edge.mean() * 1e4),
        "close_vs_1555_median_bps": float(entry_edge.median() * 1e4),
        "close_below_1555_share": float((sel["close"] < sel["entry_1555"]).mean()),
        "spec_entry_to_open_bps": float((sel["exit_open"] / sel["entry_1555"] - 1).mean() * 1e4),
        "spec_entry_to_0935_bps": float((sel["exit_0935"] / sel["entry_1555"] - 1).mean() * 1e4),
        "spec_entry_to_1000_bps": float((sel["exit_1000"] / sel["entry_1555"] - 1).mean() * 1e4),
        "close_entry_to_open_bps": float((sel["exit_open"] / sel["close"] - 1).mean() * 1e4),
        "open_to_0935_bps": float((sel["exit_0935"] / sel["exit_open"] - 1).mean() * 1e4),
        "open_to_1000_bps": float((sel["exit_1000"] / sel["exit_open"] - 1).mean() * 1e4),
    }


def proxy_fidelity(tbl: pd.DataFrame) -> dict:
    """Q3: confusion between each daily proxy and the intraday quantity it stands for."""
    out = {}

    b = tbl.dropna(subset=["late_ret_exact", "close_loc_proxy"])
    if len(b):
        truth = b["late_ret_exact"] <= LATE_RET_THRESH
        proxy = b["close_loc_proxy"] <= signals.DEFAULT_THRESHOLDS["close_loc"]
        out["filter_B"] = _confusion(truth, proxy, len(b))

    e = tbl.dropna(subset=["late_rel_vol", "full_rel_vol"])
    if len(e):
        truth = e["late_rel_vol"] >= 1.5
        proxy = e["full_rel_vol"] >= 1.5
        out["filter_E"] = _confusion(truth, proxy, len(e))
        out["filter_E"]["corr"] = float(e["late_rel_vol"].corr(e["full_rel_vol"]))
    return out


def _confusion(truth: pd.Series, proxy: pd.Series, n: int) -> dict:
    tp = int((truth & proxy).sum()); fp = int((~truth & proxy).sum())
    fn = int((truth & ~proxy).sum()); tn = int((~truth & ~proxy).sum())
    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": float(tp / (tp + fp)) if tp + fp else np.nan,   # of proxy picks, how many are real
        "recall": float(tp / (tp + fn)) if tp + fn else np.nan,      # of real ones, how many we catch
        "agreement": float((tp + tn) / n) if n else np.nan,
    }


def exact_spec_backtest(tbl: pd.DataFrame, cost_bps: float = 5.0, top_n: int = 5) -> dict:
    """The unmodified V1 rules on real intraday data — all three exit variants.

    Filters A-E are all applied on intraday data. Filter F (earnings) is NOT: the
    60-day sample is too small to lose names to it, and the point here is the
    execution geometry. That makes these numbers slightly PESSIMISTIC vs the full spec,
    since some earnings gaps that the real rules would have excluded are left in.
    """
    need = ["day_ret_exact", "late_ret_exact", "dd_high_exact",
            "late_rel_vol", "entry_1555", "exit_0935"]
    has_sector = "rel_sector_exact" in tbl and tbl["rel_sector_exact"].notna().any()
    if has_sector:
        need.append("rel_sector_exact")
    t = tbl.dropna(subset=need)
    qual = t[
        (t["day_ret_exact"] <= -0.015)
        & (t["late_ret_exact"] <= -0.005)
        & (t["dd_high_exact"] <= -0.02)
        & (t["late_rel_vol"] >= 1.5)
        & ((t["rel_sector_exact"] <= -0.010) if has_sector else True)
    ].copy()
    if qual.empty:
        return {"n_qualifying": 0}

    # Spec §6 ranking, with the exact intraday features in place of the proxies.
    ranked = qual.rename(columns={
        "day_ret_exact": "day_ret", "dd_high_exact": "dd_from_high", "late_rel_vol": "rel_vol",
    })
    ranked["close_loc"] = ranked["late_ret_exact"]      # severity ordering is the same direction
    ranked["rel_sector"] = (ranked["rel_sector_exact"] if has_sector else ranked["day_ret"])
    score = pd.Series(np.nan, index=ranked.index, dtype=float)
    for _, grp in ranked.groupby("date", sort=False):
        score.loc[grp.index] = signals.percentile_scores(grp[signals.FEATURES])
    ranked["score"] = score
    picked = (ranked.sort_values(["date", "score"], ascending=[True, False])
                    .groupby("date", group_keys=False).head(top_n))

    out = {"n_qualifying": int(len(qual)), "n_trades": int(len(picked)),
           "sessions": int(picked["date"].nunique())}
    c = 2.0 * cost_bps / 1e4
    for label, col in [("A_open", "exit_open"), ("B_0935", "exit_0935"), ("C_1000", "exit_1000")]:
        r = (picked[col] / picked["entry_1555"] - 1.0 - c).dropna()
        if r.empty:
            continue
        out[label] = {
            "n": int(r.size), "mean_bps": float(r.mean() * 1e4),
            "median_bps": float(r.median() * 1e4), "win_rate": float((r > 0).mean()),
            "worst": float(r.min()), "best": float(r.max()),
            "t_stat": float(r.mean() / (r.std(ddof=1) / np.sqrt(r.size))) if r.size > 1 and r.std(ddof=1) > 0 else np.nan,
        }
    return out


def run() -> dict:
    membership = universe.fetch_membership()
    current = membership[membership["end"].isna()]["ticker"].tolist()
    names = current if N_NAMES is None else current[:N_NAMES]
    log(f"fetching 5m bars for {len(names)} current index members (60-day window)")

    sess = requests.Session()
    frames, missing = {}, []
    for i, t in enumerate(names):
        df = intraday.fetch_5m(t, session=sess)
        if df is None or df.empty:
            missing.append(t)
        else:
            frames[t] = df
        if i % 50 == 0:
            log(f"  {i}/{len(names)} ok={len(frames)} missing={len(missing)}")
    log(f"  {len(frames)} tickers with intraday bars")

    log("fetching 5m bars for the sector ETFs (filter D, both legs at 15:50)")
    bench = {}
    for etf in sorted(set(universe.SECTOR_ETF.values())) + ["SPY"]:
        df = intraday.fetch_5m(etf, session=sess)
        if df is not None and not df.empty:
            bench[etf] = df
    log(f"  {len(bench)} benchmark series")
    sector_ret = sector_returns_1550(bench)

    sectors = universe.fetch_sectors()
    sector_map = dict(zip(sectors["ticker"], sectors["sector"]))

    log("building exact-spec feature table")
    tbl = build_exact_table(frames, sector_ret=sector_ret, sector_map=sector_map)
    log(f"  {len(tbl):,} (date, ticker) sessions")

    results = {
        "generated_utc": datetime.utcnow().isoformat(),
        "n_tickers": len(frames),
        "n_sessions_rows": int(len(tbl)),
        "window": [str(tbl["date"].min())[:10], str(tbl["date"].max())[:10]] if len(tbl) else [],
        "entry_exit_bias": entry_and_exit_bias(tbl),
        "proxy_fidelity": proxy_fidelity(tbl),
        "exact_spec": exact_spec_backtest(tbl),
        "sector_filter_applied": bool("rel_sector_exact" in tbl and tbl["rel_sector_exact"].notna().any()),
    }

    out_dir = os.path.join(os.path.dirname(__file__), "runs",
                           datetime.now().strftime("%Y%m%d-%H%M%S") + "-calibration")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "calibration.json"), "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    tbl.assign(date=lambda d: d["date"].astype(str)).to_csv(
        os.path.join(out_dir, "intraday_sessions.csv"), index=False)
    log(f"wrote {out_dir}")
    print(json.dumps(results, indent=2, default=str))
    return results


if __name__ == "__main__":
    run()
