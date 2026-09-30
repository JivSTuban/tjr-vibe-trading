"""Backtest runner for the EOD 1% Previous-Low Reversal spec.

    uv run python -m backtesting.eod_1pct_reversal.run --mode daily
    uv run python -m backtesting.eod_1pct_reversal.run --mode intraday

`daily` is the long-history run (2014-2026, close-proxied 15:50). `intraday` is the
literal spec on the trailing 60-day window. Both write a JSON + CSV run manifest so a
number can always be traced back to the config that produced it.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

import numpy as np
import pandas as pd

from backtesting.eod_pressure_reversal import earnings as earnings_mod
from backtesting.eod_pressure_reversal import intraday as intraday_mod
from backtesting.eod_pressure_reversal import prices as prices_mod
from backtesting.eod_pressure_reversal import universe as universe_mod

from . import execution as ex
from . import features as ft
from . import strategy as st

RUNS = os.path.join(os.path.dirname(__file__), "runs")
PERIODS = {
    "dev_2014_2021": ("2014-01-01", "2021-12-31"),
    "val_2022_2024": ("2022-01-01", "2024-12-31"),
    "oos_2025_2026": ("2025-01-01", "2026-12-31"),
}


# ---------------------------------------------------------------- forward outcomes

def forward_table(adj: pd.DataFrame, entry: pd.Series, horizon: int,
                  target_pct: float = ex.TARGET_PCT) -> pd.DataFrame:
    """Vectorised `execution.simulate_one` over every session of one ticker.

    Computed once per (ticker, horizon) and indexed into by each ladder rung, so
    adding a rung costs nothing. The gap-before-touch ordering is preserved: for each
    forward day d we check the OPEN first, then the HIGH, and take the earliest day
    that satisfies either.
    """
    target = entry * (1.0 + target_pct / 100.0)
    exit_price = pd.Series(np.nan, index=adj.index)
    exit_kind = pd.Series("", index=adj.index, dtype=object)
    days_held = pd.Series(np.nan, index=adj.index)

    run_lo = pd.Series(np.inf, index=adj.index)
    run_hi = pd.Series(-np.inf, index=adj.index)
    unresolved = pd.Series(True, index=adj.index)

    for d in range(1, horizon + 1):
        o = adj["open"].shift(-d)
        h = adj["high"].shift(-d)
        lo = adj["low"].shift(-d)

        run_lo = np.minimum(run_lo, lo.where(unresolved, np.inf))
        run_hi = np.maximum(run_hi, h.where(unresolved, -np.inf))

        gapped = unresolved & (o >= target)
        touched = unresolved & ~gapped & (h >= target)

        exit_price = exit_price.mask(gapped, o)
        exit_kind = exit_kind.mask(gapped, "gap_open")
        exit_price = exit_price.mask(touched, target)
        exit_kind = exit_kind.mask(touched, "target")
        days_held = days_held.mask(gapped | touched, float(d))
        unresolved = unresolved & ~(gapped | touched)

    final_close = adj["close"].shift(-horizon)
    exit_price = exit_price.mask(unresolved, final_close)
    exit_kind = exit_kind.mask(unresolved, "time_stop")
    days_held = days_held.mask(unresolved, float(horizon))

    # A trade whose horizon runs past the data is dropped, never truncated.
    valid = adj["close"].shift(-horizon).notna() & entry.notna() & (entry > 0)

    out = pd.DataFrame({
        "entry_price": entry,
        "exit_price": exit_price,
        "exit_kind": exit_kind,
        "days_held": days_held,
        "gross_ret": exit_price / entry - 1.0,
        "mae": run_lo.replace(np.inf, np.nan) / entry - 1.0,
        "mfe": run_hi.replace(-np.inf, np.nan) / entry - 1.0,
    })
    out["hit_target"] = out["exit_kind"].isin(["target", "gap_open"])
    return out[valid]


def control_table(adj: pd.DataFrame, entry: pd.Series) -> pd.DataFrame:
    """Spec §6.2 close->open control: no target, exit at the next regular open."""
    nxt_open = adj["open"].shift(-1)
    valid = nxt_open.notna() & entry.notna() & (entry > 0)
    out = pd.DataFrame({
        "entry_price": entry,
        "exit_price": nxt_open,
        "exit_kind": "next_open",
        "days_held": 1.0,
        "gross_ret": nxt_open / entry - 1.0,
        "mae": np.minimum(nxt_open, adj["low"].shift(-1)) / entry - 1.0,
        "mfe": np.maximum(nxt_open, adj["high"].shift(-1)) / entry - 1.0,
    })
    out["hit_target"] = out["gross_ret"] >= ex.TARGET_PCT / 100.0
    return out[valid]


# ---------------------------------------------------------------- earnings blocking

def earnings_blocked(index: pd.DataFrame, sessions: pd.DatetimeIndex,
                     horizon: int) -> set[tuple[pd.Timestamp, str]]:
    """(signal_date, symbol) pairs where a report lands inside the hold.

    Widens `eod_pressure_reversal.earnings.blocked_pairs` from its 1-session hold to
    an h-session hold. Unknown report times block both sides for the reason documented
    there: Nasdaq leaves the flag empty on historical rows, and an unknown-time report
    on the signal day could be AMC and land inside the hold.
    """
    if index.empty:
        return set()
    sessions = pd.DatetimeIndex(sorted(sessions))
    pos = {d: i for i, d in enumerate(sessions)}
    blocked: set[tuple[pd.Timestamp, str]] = set()
    for date, sym, _when in index[["date", "symbol", "time"]].itertuples(index=False):
        i = pos.get(pd.Timestamp(date))
        if i is None:
            continue
        # A report on session i contaminates signals fired from i-h .. i.
        for j in range(max(0, i - horizon), i + 1):
            blocked.add((sessions[j], str(sym).upper()))
    return blocked


# ---------------------------------------------------------------- stats

def session_excess(tr: pd.DataFrame, control: pd.DataFrame, label: str) -> dict:
    """Return in excess of the SAME afternoon's control, weighted one vote per session.

    The strategy fires several names at once, and on the intraday window 90% of the
    result landed on three sessions. Trade-weighting counts eight correlated names as
    eight observations and inflates the t-stat accordingly; session-weighting counts
    that afternoon once. Where the two disagree, the session-weighted one is right.
    """
    if tr.empty or control.empty:
        return {"rung": label, "n_sessions": 0}
    day_mean = control.groupby("date")["gross_ret"].mean()
    per_day = (tr.assign(ex=tr["gross_ret"] - tr["date"].map(day_mean))
                 .groupby("date")["ex"].mean().dropna())
    if len(per_day) < 3 or per_day.std(ddof=1) == 0:
        return {"rung": label, "n_sessions": int(len(per_day))}
    return {
        "rung": label,
        "n_trades": int(len(tr)),
        "n_sessions": int(len(per_day)),
        "raw_bps": round(float(tr["gross_ret"].mean()) * 10000, 2),
        "control_bps": round(float(control["gross_ret"].mean()) * 10000, 2),
        "excess_bps_by_session": round(float(per_day.mean()) * 10000, 2),
        "excess_t_by_session": round(
            float(per_day.mean() / (per_day.std(ddof=1) / np.sqrt(len(per_day)))), 2),
        "pct_sessions_positive": round(float((per_day > 0).mean()), 3),
    }


def summarise(trades: pd.DataFrame, label: str, n_sessions: int) -> dict:
    """Hit rate, expectancy and the tail — spec §6.3."""
    if trades.empty:
        return {"rung": label, "n": 0}
    g = trades["gross_ret"]
    row = {
        "rung": label,
        "n": int(len(g)),
        "per_day": round(len(g) / max(n_sessions, 1), 2),
        "hit_rate": round(float(trades["hit_target"].mean()), 4),
        "gross_bps": round(float(g.mean()) * 10000, 2),
        "median_bps": round(float(g.median()) * 10000, 2),
        "t_stat": round(float(g.mean() / (g.std(ddof=1) / np.sqrt(len(g)))), 2) if len(g) > 2 and g.std(ddof=1) > 0 else np.nan,
        "mae_bps": round(float(trades["mae"].mean()) * 10000, 2),
        "worst_1pct": round(float(g.quantile(0.01)) * 10000, 2),
        "days_held": round(float(trades["days_held"].mean()), 2),
    }
    for bps in ex.COST_BPS:
        row[f"net@{int(bps)}bps"] = round(float(ex.apply_costs(g, bps).mean()) * 10000, 2)
    return row


# ---------------------------------------------------------------- daily long run

def run_daily(args) -> dict:
    print("[universe] point-in-time S&P 500 membership")
    # fetch_membership already normalises; the clean PIT slice is deliberate — the
    # EXTENDED universe is survivorship-dirty and the sibling study showed it doubles
    # the headline. Bounds get disclosed separately, never blended.
    membership = universe_mod.fetch_membership()
    sectors = universe_mod.fetch_sectors()
    sector_map = dict(zip(sectors["ticker"], sectors["sector"])) if not sectors.empty else {}

    tickers = universe_mod.universe_tickers(membership, args.start, args.end)
    print(f"[universe] {len(tickers)} tickers in {args.start}..{args.end}")

    frames, missing = {}, []
    for t in tickers:
        path = os.path.join(os.path.dirname(prices_mod.__file__), ".cache", "prices",
                            f"{t.replace('/', '_')}.csv")
        if not os.path.exists(path):
            missing.append(t)
            continue
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if len(df) < 60:
            missing.append(t)
            continue
        frames[t] = df.loc[args.start:args.end]
    print(f"[prices] loaded {len(frames)}, missing {len(missing)}")

    # Sector ETF daily returns for the relative-weakness feature.
    etf_ret: dict[str, pd.Series] = {}
    for etf in set(sector_map.values()) | {"SPY"}:
        p = os.path.join(os.path.dirname(prices_mod.__file__), ".cache", "prices", f"{etf}.csv")
        if os.path.exists(p):
            d = pd.read_csv(p, index_col=0, parse_dates=True)
            etf_ret[etf] = d["adjclose"].pct_change()

    sessions = pd.DatetimeIndex(sorted(set().union(*[set(f.index) for f in frames.values()])))
    print(f"[sessions] {len(sessions)}")

    print("[earnings] building block index from cache")
    cal_dir = os.path.join(os.path.dirname(earnings_mod.__file__), ".cache", "earnings")
    cals = {}
    for day in sessions.strftime("%Y-%m-%d"):
        p = os.path.join(cal_dir, f"{day}.json")
        if os.path.exists(p):
            try:
                with open(p) as fh:
                    cals[day] = json.load(fh)
            except Exception:
                pass
    ear_index = earnings_mod.build_index(cals)
    print(f"[earnings] {len(ear_index)} events over {len(cals)} cached days")

    feats_all, fwd_all, ctrl_all = [], defaultdict(list), []
    for i, (t, df) in enumerate(frames.items()):
        if len(df) < 40:
            continue
        etf = universe_mod.resolve_sector_etf(sector_map, t)
        bench = etf_ret.get(etf, etf_ret.get("SPY"))
        f = ft.daily_features(df, bench)
        a = ft.adjusted(df)

        bad = prices_mod.flag_corporate_actions(df).astype(bool)
        # Drop the split session AND the one before it: the distortion sits in the
        # cross-session comparison, so both sides of it are unusable.
        f = f[~bad & ~bad.shift(-1, fill_value=False)]

        f["ticker"] = t
        feats_all.append(f)

        entry = a["close"]
        for h in ex.HORIZONS:
            tab = forward_table(a, entry, h)
            tab["ticker"] = t
            fwd_all[h].append(tab)
        c = control_table(a, entry)
        c["ticker"] = t
        ctrl_all.append(c)
        if i % 200 == 0:
            print(f"  .. {i}/{len(frames)}")

    feats = pd.concat(feats_all).rename_axis("date").reset_index()
    print(f"[features] {len(feats):,} ticker-sessions")

    ok = ft.tradable(feats)
    feats = feats[ok]
    print(f"[tradable] {len(feats):,} pass price>=$10 and ADV20>=$50M")

    conds = st.conditions(feats)
    results, period_rows = [], []

    # Daily bars carry no 15:30 mark, so the `late` gate is removed from every rung
    # and the rung is renamed to say so. See strategy.ladder_for.
    ladder = st.ladder_for({"prevlow", "red", "cloc", "range", "sector"})
    spec_rung = next(n for n, _ in ladder if n.startswith(st.SPEC_CONFIG))
    print(f"[ladder] {[n for n, _ in ladder]}  (spec config -> {spec_rung})")

    excess_rows = []
    for h in ex.HORIZONS:
        fwd = pd.concat(fwd_all[h]).rename_axis("date").reset_index()
        blocked = earnings_blocked(ear_index, sessions, h)
        control_tr = None
        for name, gates in ladder:
            mask = st.rung_mask(conds, gates)
            sel = feats[mask][["date", "ticker"]]
            tr = sel.merge(fwd, on=["date", "ticker"], how="inner")
            if not tr.empty and blocked:
                keep = [(d, s) not in blocked for d, s in zip(tr["date"], tr["ticker"])]
                tr = tr[keep]
            row = summarise(tr, f"{name}|T+{h}", len(sessions))
            results.append(row)
            if name == "L0_all":
                control_tr = tr
            elif control_tr is not None:
                excess_rows.append(session_excess(tr, control_tr, f"{name}|T+{h}"))
            if name == spec_rung and not tr.empty:
                for pname, (ps, pe) in PERIODS.items():
                    sub = tr[(tr["date"] >= ps) & (tr["date"] <= pe)]
                    period_rows.append(summarise(sub, f"{name}|T+{h}|{pname}", len(sessions)))

    ctrl = pd.concat(ctrl_all).rename_axis("date").reset_index()
    for name, gates in ladder:
        mask = st.rung_mask(conds, gates)
        sel = feats[mask][["date", "ticker"]]
        tr = sel.merge(ctrl, on=["date", "ticker"], how="inner")
        results.append(summarise(tr, f"{name}|close_to_open", len(sessions)))

    # Spec §3.2 parameter sweep + §7 promotion rule ("prefer broad stable plateaus").
    # Running only the defaults would leave open whether a neighbouring threshold is
    # the real setting; sweeping answers that without tuning anything.
    sweep_rows = []
    if args.sweep:
        fwd1 = pd.concat(fwd_all[1]).rename_axis("date").reset_index()
        base_gates = [g for g in ("prevlow", "red", "cloc", "range")]
        control_tr = feats[["date", "ticker"]].merge(fwd1, on=["date", "ticker"], how="inner")
        grid = {
            "prev_low_distance_max_pct": [0.25, 0.50, 0.75, 1.00, 1.50],
            "max_day_return_pct": [-0.50, -0.75, -1.00, -1.50, -2.00],
            "max_close_location": [0.20, 0.35, 0.50],
            "min_range_capacity_pct": [1.0, 1.5, 2.0, 2.5],
        }
        for key, values in grid.items():
            for v in values:
                c = st.conditions(feats, {key: v})
                sel = feats[st.rung_mask(c, base_gates)][["date", "ticker"]]
                tr = sel.merge(fwd1, on=["date", "ticker"], how="inner")
                row = session_excess(tr, control_tr, f"{key}={v}")
                row["param"] = key
                row["value"] = v
                sweep_rows.append(row)
        print("\n[sweep | T+1, spec gates, one parameter varied at a time]\n"
              + pd.DataFrame(sweep_rows).to_string(index=False))

    return {
        "mode": "daily",
        "window": [args.start, args.end],
        "tickers_loaded": len(frames),
        "tickers_missing": len(missing),
        "sessions": len(sessions),
        "ticker_sessions": int(len(feats)),
        "ladder": results,
        "periods": period_rows,
        "excess": excess_rows,
        "sweep": sweep_rows,
        "note": "15:50 proxied by the close; the late_return gate is unavailable on "
                "daily bars, so it is removed from each rung and the rung is renamed.",
    }


# ---------------------------------------------------------------- intraday exact run

def run_intraday(args) -> dict:
    cache = os.path.join(os.path.dirname(intraday_mod.__file__), ".cache", "intraday")
    syms = sorted(f[:-4] for f in os.listdir(cache) if f.endswith(".csv"))
    print(f"[intraday] {len(syms)} tickers with 5m bars")

    sectors = universe_mod.fetch_sectors()
    sector_map = dict(zip(sectors["ticker"], sectors["sector"])) if not sectors.empty else {}

    feats_all, fwd_all, ctrl_all, proxy_rows = [], defaultdict(list), [], []
    sector_bars: dict[str, pd.DataFrame] = {}

    def load_bars(sym: str):
        p = os.path.join(cache, f"{sym}.csv")
        if not os.path.exists(p):
            return None
        b = pd.read_csv(p, index_col=0, parse_dates=True)
        if b.empty:
            return None
        if b.index.tz is None:
            b.index = b.index.tz_localize("America/New_York")
        else:
            b.index = b.index.tz_convert("America/New_York")
        return b

    for i, t in enumerate(syms):
        bars = load_bars(t)
        dp = os.path.join(os.path.dirname(prices_mod.__file__), ".cache", "prices", f"{t}.csv")
        if bars is None or not os.path.exists(dp):
            continue
        daily = pd.read_csv(dp, index_col=0, parse_dates=True)
        if len(daily) < 40:
            continue

        etf = universe_mod.resolve_sector_etf(sector_map, t)
        if etf not in sector_bars:
            sector_bars[etf] = load_bars(etf)
        f = ft.intraday_features(bars, daily, sector_bars.get(etf))
        if f.empty:
            continue

        bad = prices_mod.flag_corporate_actions(daily)
        f = f[~bad.reindex(f.index).fillna(False)]
        f["ticker"] = t
        feats_all.append(f)

        # Proxy-error measurement: the same session's close vs the true 15:55 entry.
        a = ft.adjusted(daily)
        df_p = pd.DataFrame({
            "close": a["close"].reindex(f.index),
            "entry_15_55": f["entry_px"] * f["adj_factor"],
            "signal_15_50": f["entry_ref"] * f["adj_factor"],
        }).dropna()
        if not df_p.empty:
            proxy_rows.append(df_p.assign(ticker=t))

        entry = (f["entry_px"] * f["adj_factor"]).reindex(a.index)
        for h in ex.HORIZONS:
            tab = forward_table(a, entry, h)
            tab["ticker"] = t
            fwd_all[h].append(tab)
        c = control_table(a, entry)
        c["ticker"] = t
        ctrl_all.append(c)
        if i % 100 == 0:
            print(f"  .. {i}/{len(syms)}")

    feats = pd.concat(feats_all).rename_axis("date").reset_index()
    feats = feats[ft.tradable(feats)]
    sessions = pd.DatetimeIndex(sorted(feats["date"].unique()))
    print(f"[intraday] {len(feats):,} ticker-sessions over {len(sessions)} sessions")

    conds = st.conditions(feats)
    results, kept_trades = [], []
    for h in ex.HORIZONS:
        fwd = pd.concat(fwd_all[h]).rename_axis("date").reset_index()
        for name, gates in st.LADDER:
            mask = st.rung_mask(conds, gates)
            sel = feats[mask][["date", "ticker"]]
            tr = sel.merge(fwd, on=["date", "ticker"], how="inner")
            results.append(summarise(tr, f"{name}|T+{h}", len(sessions)))
            # Persist the rungs the stress test needs: the control, the gate that
            # carries the result, and the spec's own configuration.
            if name in ("L0_all", "L2_red", "L3_late", "L5_range") and not tr.empty:
                kept_trades.append(tr.assign(rung=name, horizon=h))

    ctrl = pd.concat(ctrl_all).rename_axis("date").reset_index()
    for name, gates in st.LADDER:
        mask = st.rung_mask(conds, gates)
        sel = feats[mask][["date", "ticker"]]
        tr = sel.merge(ctrl, on=["date", "ticker"], how="inner")
        results.append(summarise(tr, f"{name}|close_to_open", len(sessions)))

    if kept_trades:
        os.makedirs(RUNS, exist_ok=True)
        pd.concat(kept_trades).to_csv(os.path.join(RUNS, "intraday_trades.csv"), index=False)

    proxy = pd.concat(proxy_rows) if proxy_rows else pd.DataFrame()
    proxy_stats = {}
    if not proxy.empty:
        e = (proxy["close"] / proxy["entry_15_55"] - 1.0) * 10000
        s = (proxy["close"] / proxy["signal_15_50"] - 1.0) * 10000
        proxy_stats = {
            "n": int(len(proxy)),
            "close_vs_1555_entry_bps_mean": round(float(e.mean()), 2),
            "close_vs_1555_entry_bps_median": round(float(e.median()), 2),
            "close_vs_1550_signal_bps_mean": round(float(s.mean()), 2),
            "close_vs_1550_signal_bps_median": round(float(s.median()), 2),
            "close_vs_1550_bps_std": round(float(s.std()), 2),
        }

    return {
        "mode": "intraday",
        "sessions": len(sessions),
        "tickers": len(feats["ticker"].unique()),
        "ticker_sessions": int(len(feats)),
        "ladder": results,
        "proxy_error": proxy_stats,
        "note": "Literal spec: features at the 15:50 bar open, entry at the 15:55 bar open.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["daily", "intraday"], default="daily")
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--tag", default="")
    ap.add_argument("--sweep", action="store_true",
                    help="run the spec §3.2 threshold sweep (daily mode only)")
    args = ap.parse_args()

    out = run_daily(args) if args.mode == "daily" else run_intraday(args)

    os.makedirs(RUNS, exist_ok=True)
    tag = args.tag or args.mode
    with open(os.path.join(RUNS, f"{tag}.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    lad = pd.DataFrame(out["ladder"])
    lad.to_csv(os.path.join(RUNS, f"{tag}_ladder.csv"), index=False)
    print("\n" + lad.to_string(index=False))
    if out.get("excess"):
        print("\n[excess over the same afternoon's control]\n"
              + pd.DataFrame(out["excess"]).to_string(index=False))
    if out.get("periods"):
        print("\n[periods]\n" + pd.DataFrame(out["periods"]).to_string(index=False))
    if out.get("proxy_error"):
        print("\n[proxy error]", json.dumps(out["proxy_error"], indent=2))


if __name__ == "__main__":
    main()
