"""Insider-cluster-buy backtest driver — does an insider cluster buy add alpha, and does it need a catalyst?

Event-driven. Events = SEC Form-4 open-market CLUSTER buys (>=2 distinct insiders) from the openinsider
historical panel. For each event we enter at the open of t+1 after the public filing date (genuinely
tradeable, no look-ahead) and measure H-day forward return, then bucket into ARMS that isolate the two
questions the deep-research left open:

  1. Does an insider cluster beat the base rate?            insider_all      vs  control (unconditional)
  2. Does the cluster ADD to a catalyst, or does the        insider+catalyst vs  catalyst_only
     catalyst do all the work?                              insider+catalyst vs  insider_no_catalyst

Catalyst = a recent positive earnings surprise (Finnhub PEAD proxy). A survivorship stress marks
horizon-truncated trades (a proxy for delist/blow-up, since Yahoo drops delisted names) as -100%.

Network is touched ONLY under ``__main__`` (panel + OHLC + earnings into caches). ``run_backtest``
reads caches only. KNOWN BIAS: Yahoo has no delisted small-caps, so coverage is survivor-tilted and
every arm's raw number is an UPPER bound — read the stressed row and the relative arm deltas, not the
absolute means. Caches/runs are gitignored.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

import pandas as pd

from backtesting.insider_cluster.panel import fetch_panel, load_panel, build_cluster_events
from backtesting.insider_cluster.catalyst import (fetch_earnings, had_beat_near, beat_events, _key)
from backtesting.swing_bounce.prices_ohlc import fetch_ohlc, load_ohlc
from backtesting.swing_bounce.trade_sim import simulate_trade

_HERE = os.path.dirname(__file__)
HORIZONS = [20, 60]                 # trading-day holds
HEADLINE_H = 60
COST_BPS = 15.0                     # round-trip approx (matches swing_bounce)
BIG_VALUE = 500_000                 # "conviction" cluster $ threshold
SIM = dict(target_pct=0.20, stop_pct=0.12, horizon_days=60)   # tradeable-setup expectancy cell
# Finnhub free earnings only covers ~the last 4 quarters, so the catalyst arms are ONLY valid for
# events on/after this cutoff. Insider-alone + survivorship use the FULL panel; the catalyst
# intersection is reported on this recent slice only (see FINDINGS "catalyst-covered slice").
CAT_START = pd.Timestamp("2025-06-01")


# ---------- entry + forward-return primitives ----------

def entry_index(ohlc: pd.DataFrame, event_date) -> int | None:
    """First positional bar STRICTLY after the filing date = the tradeable t+1 open."""
    ed = pd.Timestamp(event_date).tz_localize("UTC") if pd.Timestamp(event_date).tzinfo is None else pd.Timestamp(event_date)
    pos = ohlc.index.searchsorted(ed, side="right")
    return int(pos) if pos < len(ohlc) else None


def fwd_return(ohlc: pd.DataFrame, i: int, H: int, cost_bps: float = COST_BPS) -> dict | None:
    """Enter at open[i], exit at close[i+H-1]. Flags ``truncated`` if the window runs off the data
    (a delist/blow-up or just end-of-sample) — used by the survivorship stress."""
    n = len(ohlc)
    if i is None or i >= n:
        return None
    entry = float(ohlc["open"].iloc[i])
    if not entry or entry != entry:
        entry = float(ohlc["close"].iloc[i])
    j = i + H - 1
    truncated = j >= n
    j = min(j, n - 1)
    exitp = float(ohlc["close"].iloc[j])
    gross = exitp / entry - 1.0
    return {"ret": gross - 2 * (cost_bps / 1e4), "truncated": truncated}


def _stats(rets: list[float]) -> dict:
    n = len(rets)
    if not n:
        return {"n": 0, "mean": 0.0, "median": 0.0, "hit": 0.0}
    s = sorted(rets)
    return {"n": n, "mean": sum(rets) / n, "median": s[n // 2],
            "hit": sum(1 for r in rets if r > 0) / n}


# ---------- the backtest ----------

def run_backtest(events: list[dict], tickers: list[str]) -> dict:
    ohlc_cache: dict[str, pd.DataFrame] = {}
    covered = []
    for t in tickers:
        try:
            ohlc_cache[t] = load_ohlc(t)
            covered.append(t)
        except Exception:            # noqa: BLE001
            continue
    cov = ohlc_cache

    # --- arm return collectors (keyed by horizon) ---
    arms: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    trunc_flags: dict[int, list] = defaultdict(list)     # (ret, truncated) for insider_all headline H
    sim_trades = []                                      # stop/target expectancy for insider_all
    pnl_by_ticker, pnl_by_year = defaultdict(float), defaultdict(float)
    clustered_dates: dict[str, list] = defaultdict(list)
    insider_by_year: dict = defaultdict(lambda: defaultdict(list))   # [year][H] insider_all returns

    for e in events:
        t = e["ticker"]
        if t not in cov:
            continue
        edate = pd.Timestamp(e["date"])
        clustered_dates[t].append(edate)
        i = entry_index(cov[t], e["date"])
        if i is None:
            continue
        recent = edate >= CAT_START                              # catalyst labels only valid here
        has_cat = had_beat_near(t, e["date"]) if recent else False
        for H in HORIZONS:
            fr = fwd_return(cov[t], i, H)
            if fr is None:
                continue
            arms["insider_all"][H].append(fr["ret"])
            if e["csuite"]:
                arms["insider_csuite"][H].append(fr["ret"])
            if e["total_value"] >= BIG_VALUE:
                arms["insider_big"][H].append(fr["ret"])
            if recent:                                           # apples-to-apples vs catalyst_only
                arms["insider_recent"][H].append(fr["ret"])
                (arms["insider_plus_catalyst"] if has_cat else arms["insider_no_catalyst"])[H].append(fr["ret"])
            if H == HEADLINE_H:
                insider_by_year[edate.year][H].append(fr["ret"])
                trunc_flags[H].append((fr["ret"], fr["truncated"]))
                pnl_by_ticker[t] += fr["ret"]
                pnl_by_year[edate.year] += fr["ret"]
        tr = simulate_trade(cov[t], i, **SIM)
        if tr is not None:
            sim_trades.append(tr)

    # --- catalyst-ONLY arm: earnings beats (recent slice) NOT coinciding with a cluster ---
    for t in covered:
        cds = clustered_dates.get(t, [])
        for a in beat_events(t):
            if a < CAT_START:                                    # no reliable earnings before this
                continue
            if any(abs((a - cd).days) <= 30 for cd in cds):     # skip beats that ARE the cluster catalyst
                continue
            i = entry_index(cov[t], a)
            if i is None:
                continue
            for H in HORIZONS:
                fr = fwd_return(cov[t], i, H)
                if fr:
                    arms["catalyst_only"][H].append(fr["ret"])

    # --- control: unconditional H-day base rate across covered tickers (sampled every 5 bars) ---
    for t in covered:
        c = cov[t]["close"].values
        o = cov[t]["open"].values
        n = len(c)
        for H in HORIZONS:
            for i in range(1, n - H, 5):
                entry = o[i] if o[i] == o[i] and o[i] else c[i]
                arms["control"][H].append(c[i + H - 1] / entry - 1.0 - 2 * (COST_BPS / 1e4))

    results = {H: {arm: _stats(arms[arm][H]) for arm in arms} for H in HORIZONS}

    # --- survivorship stress on insider_all (headline H): truncated -> -100% ---
    base = _stats([r for r, _ in trunc_flags[HEADLINE_H]])
    stressed = _stats([(-1.0 if tr else r) for r, tr in trunc_flags[HEADLINE_H]])
    n_trunc = sum(1 for _, tr in trunc_flags[HEADLINE_H] if tr)

    # --- concentration (headline H P&L) ---
    total_pnl = sum(pnl_by_ticker.values()) or 1e-9
    top_t = max(pnl_by_ticker.items(), key=lambda kv: abs(kv[1])) if pnl_by_ticker else ("-", 0.0)
    top_y = max(pnl_by_year.items(), key=lambda kv: abs(kv[1])) if pnl_by_year else (0, 0.0)

    # --- stop/target expectancy (insider_all tradeable setup) ---
    from backtesting.swing_bounce.metrics import expectancy
    sim = expectancy(sim_trades)

    # --- SPY benchmark ---
    spy_bench = {}
    try:
        spy = load_ohlc("SPY")["close"]
        for H in HORIZONS:
            spy_bench[H] = float((spy.shift(-H) / spy - 1.0).dropna().mean())
    except Exception:                # noqa: BLE001
        spy_bench = {"error": "SPY not cached"}

    return {
        "n_events": len(events),
        "n_events_covered": sum(1 for e in events if e["ticker"] in cov),
        "coverage_pct": round(100 * len(covered) / len(tickers), 1) if tickers else 0.0,
        "by_horizon": results,
        "headline_H": HEADLINE_H,
        "insider_by_year": {int(y): _stats(insider_by_year[y][HEADLINE_H]) for y in sorted(insider_by_year)},
        "survivorship": {"n_truncated": n_trunc, "base": base, "stressed": stressed},
        "concentration": {"top_ticker": top_t[0], "top_ticker_share": round(top_t[1] / total_pnl, 3),
                          "top_year": top_y[0], "top_year_share": round(top_y[1] / total_pnl, 3)},
        "sim_expectancy": sim,
        "spy_benchmark": spy_bench,
    }


# ---------- fetch + run ----------

START, END = "2021-01", "2026-08"                     # multi-regime: 2021 mania / 2022 bear / 23-24 recovery / 25-26
OHLC_FROM, OHLC_TO = "2020-09-01", "2026-08-08"      # covers events + the 60d horizon after END
MAX_TICKERS = 350                                     # bound the fetch; keep the largest-$ clusters


def _fetch_all():
    print(f"[1/4] panel {START}..{END}")
    panel = fetch_panel(START, END)
    print(f"      {len(panel)} P-buy txns")
    events = build_cluster_events(panel)
    print(f"[2/4] {len(events)} cluster events (>=2 insiders)")
    by_val = defaultdict(float)
    for e in events:
        by_val[e["ticker"]] += e["total_value"]
    tickers = [t for t, _ in sorted(by_val.items(), key=lambda kv: -kv[1])][:MAX_TICKERS]
    print(f"      {len(by_val)} distinct tickers -> capping to {len(tickers)}")
    token = _key()
    print(f"[3/4] OHLC + earnings for {len(tickers)} tickers (rate-limited)")
    for k, t in enumerate(tickers + ["SPY"], 1):
        fetch_ohlc(t, OHLC_FROM, OHLC_TO, use_cache=True)
        if t != "SPY":
            fetch_earnings(t, token, use_cache=True)
        if k % 25 == 0:
            print(f"      {k}/{len(tickers)+1}")
    events = [e for e in events if e["ticker"] in set(tickers)]
    return events, tickers


if __name__ == "__main__":
    import datetime as _dt
    events, tickers = _fetch_all()
    print("[4/4] running backtest")
    res = run_backtest(events, tickers)
    ts = _dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    out = os.path.join(_HERE, "runs", ts)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "results.json"), "w") as f:
        json.dump(res, f, indent=2, default=str)
    H = res["headline_H"]
    bh = res["by_horizon"][H]
    print(f"\n=== insider-cluster backtest {START}..{END} | H={H}d ===")
    print(f"events {res['n_events']} (covered {res['n_events_covered']}) | ticker coverage {res['coverage_pct']}%")
    for arm in ["control", "insider_all", "insider_csuite", "insider_big",
                "insider_recent", "catalyst_only", "insider_no_catalyst", "insider_plus_catalyst"]:
        s = bh.get(arm, {})
        if s.get("n"):
            print(f"  {arm:22s} n={s['n']:5d}  mean={s['mean']:+.2%}  median={s['median']:+.2%}  hit={s['hit']:.0%}")
    ctrl = bh["control"]["mean"]
    print(f"\n  edge vs control (mean {H}d):")
    for arm in ["insider_all", "insider_recent", "insider_plus_catalyst", "catalyst_only", "insider_no_catalyst"]:
        if bh.get(arm, {}).get("n"):
            print(f"    {arm:22s} {bh[arm]['mean'] - ctrl:+.2%}")
    print(f"\n  insider_all edge by YEAR (regime robustness, {H}d):")
    for y, s in res["insider_by_year"].items():
        if s.get("n"):
            print(f"    {y}  n={s['n']:4d}  mean={s['mean']:+.2%}  median={s['median']:+.2%}  hit={s['hit']:.0%}")
    st = res["survivorship"]
    print(f"  survivorship: base {st['base']['mean']:+.2%} -> stressed {st['stressed']['mean']:+.2%} "
          f"({st['n_truncated']} truncated)")
    print(f"  concentration: top name {res['concentration']['top_ticker']} "
          f"{res['concentration']['top_ticker_share']:+.0%} of P&L")
    print(f"  results -> {out}")
