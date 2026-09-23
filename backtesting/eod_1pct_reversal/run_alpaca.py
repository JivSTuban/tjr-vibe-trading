"""The literal spec on Alpaca minute bars, 2016-2026 — including the late gate.

This answers the one question FINDINGS.md had to leave open. The `late_return` gate
(15:30 -> 15:50) was the only component that moved the number, and it could only be
seen on 57 days of Yahoo 5m data, where 90% of the result landed on three sessions.
Alpaca serves minute bars back to 2016, so it can now be measured on ~10 years.

IT ALSO PRICES THE THING THAT ACTUALLY KILLS RETAIL STRATEGIES: the price is moving
while you decide. A signal computed at 15:50 cannot be filled at 15:50 — you see the
print, a model or a human decides, an order routes. So every candidate is priced at
FIVE fill times (15:50, 15:51, 15:52, 15:55, 16:00) and the edge is reported as a
decay curve. If the edge only exists at a fill you could never achieve, it is not an
edge, it is a measurement artifact.

SELECTION. Minute data is fetched only for a WIDE superset of candidates chosen from
daily bars (prev-low band -2.0..+2.5%, day return <= 0), deliberately looser than the
real gate on both sides, so that no name the true 15:50 gate would have selected is
excluded by the cheap daily pre-filter. A random same-day control of tradable names
is fetched alongside, because the only number that matters is performance relative to
the other stocks available that same afternoon.

    uv run python -m backtesting.eod_1pct_reversal.run_alpaca --dates 60      # pilot
    uv run python -m backtesting.eod_1pct_reversal.run_alpaca --dates 800     # full
"""
from __future__ import annotations

import argparse
import json
import os
import random

import numpy as np
import pandas as pd
import requests

from backtesting.eod_pressure_reversal import prices as prices_mod
from backtesting.eod_pressure_reversal import universe as universe_mod

from . import alpaca_bars as ab
from . import execution as ex
from . import features as ft
from . import strategy as st
from .run import RUNS, forward_table, session_excess, summarise

# Fill times priced for every candidate. 15:50 is the signal instant and is NOT
# achievable; it is included only to size the cost of the delay.
FILL_TIMES = ["15:50", "15:51", "15:52", "15:55", "16:00"]
SIGNAL_T = "15:50"
LATE_T = "15:30"

# Pre-filter, deliberately wider than features.DEFAULTS on every axis.
WIDE = {"prev_low_lo": -2.0, "prev_low_hi": 2.5, "day_ret_max": 0.0}
CONTROL_PER_DAY = 45


def daily_panel(start: str, end: str) -> tuple[dict, pd.DataFrame]:
    membership = universe_mod.fetch_membership()
    tickers = universe_mod.universe_tickers(membership, start, end)
    cache = os.path.join(os.path.dirname(prices_mod.__file__), ".cache", "prices")
    frames = {}
    for t in tickers:
        p = os.path.join(cache, f"{t.replace('/', '_')}.csv")
        if not os.path.exists(p):
            continue
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        if len(df) < 120:
            continue
        frames[t] = df.loc[start:end]

    rows = []
    for t, df in frames.items():
        f = ft.daily_features(df)
        bad = prices_mod.flag_corporate_actions(df).astype(bool)
        f = f[~bad & ~bad.shift(-1, fill_value=False)]
        f["ticker"] = t
        rows.append(f)
    feats = pd.concat(rows).rename_axis("date").reset_index()
    feats = feats[ft.tradable(feats)]
    return frames, feats


def pick_symbols(feats_day: pd.DataFrame, rng: random.Random) -> tuple[list, list]:
    """(wide candidate superset, random control) for one session."""
    wide = feats_day[
        (feats_day["prev_low_distance_pct"] >= WIDE["prev_low_lo"])
        & (feats_day["prev_low_distance_pct"] <= WIDE["prev_low_hi"])
        & (feats_day["day_return_pct"] <= WIDE["day_ret_max"])
    ]["ticker"].tolist()
    pool = [t for t in feats_day["ticker"].tolist() if t not in set(wide)]
    rng.shuffle(pool)
    return wide, pool[:CONTROL_PER_DAY]


def minute_features(bars: pd.DataFrame, feats_day: pd.DataFrame) -> pd.DataFrame:
    """True 15:50 features + every fill price, from minute bars for one session.

    A bar is stamped with the LEFT edge of its minute, so the open of the 15:50 bar is
    a price that exists at 15:50:00. Everything "through the signal" uses bars opening
    at or before 15:49, plus that 15:50 open itself. Using the 15:50 bar's high or
    close here would leak a minute of the future into the signal.
    """
    if bars.empty:
        return pd.DataFrame()
    b = bars.copy()
    b["hm"] = b["ts"].dt.strftime("%H:%M")

    at = {t: b[b["hm"] == t].set_index("ticker")["open"] for t in set(FILL_TIMES) | {LATE_T}}
    sig = at[SIGNAL_T]
    if sig.empty:
        return pd.DataFrame()

    pre = b[b["hm"] <= "15:49"]
    hi = pre.groupby("ticker")["high"].max()
    lo = pre.groupby("ticker")["low"].min()
    hi = pd.concat([hi, sig], axis=1).max(axis=1)
    lo = pd.concat([lo, sig], axis=1).min(axis=1)

    d = feats_day.set_index("ticker")
    idx = sig.index.intersection(d.index)
    if len(idx) == 0:
        return pd.DataFrame()

    out = pd.DataFrame(index=idx)
    out["signal_px"] = sig.reindex(idx)
    # Ratio to that day's raw close, so the minute price can be lifted into the daily
    # cache's split+dividend-adjusted space without mixing adjustment conventions.
    out["px_to_close"] = out["signal_px"] / d["price"].reindex(idx)

    # Prior-session marks come from daily bars, already adjusted.
    prev_close_adj = (d["price"] / (1 + d["day_return_pct"] / 100.0)).reindex(idx)
    prev_low_adj = (d["price"] / (1 + d["prev_low_distance_pct"] / 100.0)).reindex(idx)
    sig_equiv = d["price"].reindex(idx) * out["px_to_close"]

    out["day_return_pct"] = (sig_equiv / prev_close_adj - 1.0) * 100.0
    out["prev_low_distance_pct"] = (sig_equiv / prev_low_adj - 1.0) * 100.0
    out["late_return_pct"] = (out["signal_px"] / at[LATE_T].reindex(idx) - 1.0) * 100.0
    rng_ = (hi - lo).replace(0.0, np.nan).reindex(idx)
    out["close_location_value"] = (out["signal_px"] - lo.reindex(idx)) / rng_
    out["range_capacity_pct"] = d["range_capacity_pct"].reindex(idx)
    out["sector_relative_pct"] = np.nan          # not used by the rungs we can measure
    out["price"] = d["price"].reindex(idx)
    out["adv20"] = d["adv20"].reindex(idx)

    for t in FILL_TIMES:
        out[f"fill_{t}"] = at[t].reindex(idx)
    return out.reset_index().rename(columns={"index": "ticker"})



def drop_price_basis_mismatches(m: pd.DataFrame, tol: float = 0.05) -> pd.DataFrame:
    """Reject rows where the minute tape and the daily bar disagree about the price.

    Entry comes from Alpaca minute bars and the exit legs come from the Yahoo daily
    cache, so the two must agree on what a share cost at the close. Normally they
    agree to within 0.1% (measured: 5th-95th percentile 0.9998-1.0007). When they do
    not, it is never a market event — it is the two providers handling a spin-off or
    reverse split differently.

    Measured on the pilot: 48 of 3,357 rows, ratios up to 9.6x. Left in, they price a
    trade at 9.6x its real entry, which books a fake -90% and dragged the CONTROL's
    average to -103 bps when the daily study puts it at +5. A handful of rows can
    invert a whole study; this is the same shape as the pair-flip corruption already
    banked in this repo.

    The check is one-sided in spirit but two-sided in form, and it is reported, never
    silent.
    """
    ref = m["fill_16:00"].fillna(m["fill_15:55"])
    ratio = ref / m["price"]
    ok = ratio.between(1 - tol, 1 + tol) & ratio.notna()
    dropped = int((~ok).sum())
    if dropped:
        worst = (ratio[~ok].abs() - 1).abs().sort_values(ascending=False).head(3)
        print(f"[integrity] dropped {dropped} of {len(m)} rows where minute and daily "
              f"prices disagree by >{tol:.0%} (worst ratios: "
              f"{[round(float(ratio.loc[i]), 2) for i in worst.index]})")
    return m[ok].reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--dates", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--tag", default="alpaca")
    args = ap.parse_args()

    print("[daily] loading cached panel")
    frames, feats = daily_panel(args.start, args.end)
    sessions = sorted(feats["date"].unique())
    print(f"[daily] {len(frames)} tickers, {len(sessions)} sessions, {len(feats):,} ticker-sessions")

    rng = random.Random(args.seed)
    chosen = sorted(rng.sample(sessions, min(args.dates, len(sessions))))
    print(f"[sample] {len(chosen)} sessions, {str(chosen[0])[:10]} .. {str(chosen[-1])[:10]}")

    by_day = {d: g for d, g in feats.groupby("date")}

    # Prefetch concurrently. Alpaca Basic allows 200 requests/min and the serial loop
    # was using roughly 0.3/s, so the wall-clock was network latency, not the limit.
    # Workers stay modest because each request is multi-symbol and already fat.
    plan = {}
    for d in chosen:
        wide, ctrl = pick_symbols(by_day[d], rng)
        if wide or ctrl:
            plan[d] = sorted(set(wide) | set(ctrl))

    todo = [d for d in plan if not os.path.exists(ab.cache_path(pd.Timestamp(d).strftime("%Y-%m-%d")))]
    print(f"[fetch] {len(todo)} sessions to pull, {len(plan) - len(todo)} already cached")
    if todo:
        from concurrent.futures import ThreadPoolExecutor

        def pull(d):
            day = pd.Timestamp(d).strftime("%Y-%m-%d")
            try:
                # Each worker needs its own Session: requests.Session is not thread-safe.
                ab.load_or_fetch(plan[d], day, session=requests.Session())
                return None
            except Exception as e:
                return f"{day}: {e}"

        done = 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            for err in pool.map(pull, todo):
                done += 1
                if err:
                    print("  !!", err)
                if done % 50 == 0:
                    print(f"  .. fetched {done}/{len(todo)}")

    sess = requests.Session()
    mins, misses = [], 0
    for i, d in enumerate(chosen):
        day = pd.Timestamp(d).strftime("%Y-%m-%d")
        fd = by_day[d]
        syms = plan.get(d)
        if not syms:
            continue
        wide = set(fd[
            (fd["prev_low_distance_pct"] >= WIDE["prev_low_lo"])
            & (fd["prev_low_distance_pct"] <= WIDE["prev_low_hi"])
            & (fd["day_return_pct"] <= WIDE["day_ret_max"])
        ]["ticker"])
        try:
            bars = ab.load_or_fetch(syms, day, session=sess)
        except Exception as e:
            print(f"  !! {day}: {e}")
            misses += 1
            continue
        mf = minute_features(bars, fd)
        if mf.empty:
            misses += 1
            continue
        mf["date"] = pd.Timestamp(d)
        mf["in_wide"] = mf["ticker"].isin(wide)
        mins.append(mf)
        if i % 20 == 0:
            print(f"  .. {i}/{len(chosen)} {day} symbols={len(syms)} rows={len(mf)}")

    m = pd.concat(mins, ignore_index=True)
    print(f"[minute] {len(m):,} ticker-sessions over {m['date'].nunique()} sessions "
          f"({misses} sessions unusable)")
    m = drop_price_basis_mismatches(m)

    # Forward outcomes per fill time, from adjusted daily bars.
    adj = {t: ft.adjusted(df) for t, df in frames.items()}
    results, excess_rows, decay_rows = [], [], []
    conds = st.conditions(m)

    for fill in FILL_TIMES:
        fwd_by_h = {}
        for h in ex.HORIZONS:
            parts = []
            for t, a in adj.items():
                sub = m[m["ticker"] == t]
                if sub.empty:
                    continue
                entry_adj = pd.Series(np.nan, index=a.index)
                ratio = (sub[f"fill_{fill}"] / sub["price"]).values
                dates = pd.DatetimeIndex(sub["date"].values)
                valid = dates.isin(a.index)
                entry_adj.loc[dates[valid]] = (a["close"].reindex(dates[valid]).values
                                               * ratio[valid])
                tab = forward_table(a, entry_adj, h)
                if tab.empty:
                    continue
                tab["ticker"] = t
                parts.append(tab)
            fwd_by_h[h] = pd.concat(parts).rename_axis("date").reset_index() if parts else pd.DataFrame()

        for h in ex.HORIZONS:
            fwd = fwd_by_h[h]
            if fwd.empty:
                continue
            control = m[["date", "ticker"]].merge(fwd, on=["date", "ticker"], how="inner")
            results.append(summarise(control, f"L0_all|{fill}|T+{h}", m["date"].nunique()))
            for name, gates in st.LADDER:
                if not gates:
                    continue
                sel = m[st.rung_mask(conds, gates)][["date", "ticker"]]
                tr = sel.merge(fwd, on=["date", "ticker"], how="inner")
                results.append(summarise(tr, f"{name}|{fill}|T+{h}", m["date"].nunique()))
                row = session_excess(tr, control, f"{name}|{fill}|T+{h}")
                row["fill"] = fill
                row["horizon"] = h
                row["rung"] = name
                excess_rows.append(row)

    # Price-is-moving: how far the tape runs between the signal and each fill.
    gate_mask = st.rung_mask(conds, ["prevlow", "red", "late", "cloc", "range"])
    for label, sub in (("spec_gate", m[gate_mask]), ("all_fetched", m)):
        for fill in FILL_TIMES:
            slip = (sub[f"fill_{fill}"] / sub["signal_px"] - 1.0) * 10000
            decay_rows.append({
                "population": label, "fill": fill, "n": int(slip.notna().sum()),
                "mean_bps": round(float(slip.mean()), 2),
                "median_bps": round(float(slip.median()), 2),
                "p90_bps": round(float(slip.quantile(0.90)), 2),
                "p10_bps": round(float(slip.quantile(0.10)), 2),
            })

    out = {
        "mode": "alpaca_minute",
        "window": [args.start, args.end],
        "sessions_sampled": int(m["date"].nunique()),
        "ticker_sessions": int(len(m)),
        "ladder": results,
        "excess": excess_rows,
        "fill_decay": decay_rows,
    }
    os.makedirs(RUNS, exist_ok=True)
    with open(os.path.join(RUNS, f"{args.tag}.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    m.to_csv(os.path.join(RUNS, f"{args.tag}_features.csv"), index=False)

    ed = pd.DataFrame(excess_rows)
    print("\n[excess over same-afternoon control, session-weighted]")
    print(ed[ed["horizon"] == 1].to_string(index=False))
    print("\n[price drift from the 15:50 signal to each fill]")
    print(pd.DataFrame(decay_rows).to_string(index=False))


if __name__ == "__main__":
    main()
