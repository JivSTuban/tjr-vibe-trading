"""Forward (out-of-sample) extension of the n=39 re-test. Protocol: RETEST_N39.md "Forward test".

The re-test froze its result at L4: insider cluster + a beat already public, ex-microcap, t+2
open, 60 trading days, 150 bps round trip. This module keeps scoring the SAME definitions on
events dated on or after FORWARD_START, so the pre-committed kill rule runs on data nobody tuned
against. It is deliberately NOT built on journaled /stock-scan picks: the control arm
(catalyst-only) is every beat event in the universe, so a ranked-picks cohort would compare a
selected arm against an unselected one.

Three things differ from `retest_n39.ladder`, each of them a trap the frozen code cannot avoid:
  * MATURITY. `retest_n39.fwd` clamps the exit to the last bar, so a trade 10 days old would be
    graded as a "60d" return. Here a trade is graded only when a full H-bar window exists after
    the t+2 open; everything else is PENDING and counted by name.
  * FRESH DATA. Every frozen cache (OHLC, EDGAR submissions, Finnhub earnings) is written once
    and read forever, so a forward run on them reports a confident "no new events". This module
    keeps its own refresh-with-TTL cache under .cache/forward/ and never writes the frozen ones.
  * NAMED DROPS. Microcap / no-market-cap / stale-price / no-price names are listed, not counted
    (KB trap #14).

`test_forward_n39.py::test_parity_with_frozen_ladder` proves the arm definitions here reproduce the
frozen L4 result (n=24 / +4.79% / 54 / 262) when fed the frozen data with since=None.
"""
from __future__ import annotations

import json
import os
import sys
import time

import pandas as pd
import requests

from backtesting.insider_cluster import retest_n39 as R
from backtesting.insider_cluster.catalyst import _key
from backtesting.insider_cluster.panel import build_cluster_events, fetch_panel
from backtesting.insider_cluster.run import entry_index
from backtesting.swing_bounce.prices_ohlc import fetch_ohlc

# Frozen 2026-10-01, before any forward event had matured. The re-test window ends 2026-08, so the
# first month it never saw is 2026-09. Do not move this after looking at results.
FORWARD_START = pd.Timestamp("2026-09-01")
H = R.H                       # 60 trading days
SHIFT = 1                     # t+2 open: entry_index gives t+1, plus one more bar
COST = 150.0                  # bps round trip, the re-test's L4 cost
KILL_N = 30                   # pre-committed: judge at 30 graded insider + catalyst events
KILL_DIFF = 0.03              # insider + catalyst median must beat catalyst-only by 3pp
INTERIM_MIN = 8               # below this an interim diff is noise, so it is not printed
STALE_DAYS = 6                # last bar older than this (calendar days) = price data is stale
_FWD = os.path.join(os.path.dirname(__file__), ".cache", "forward")   # under the gitignored .cache/
TTL = 20 * 3600


def p20_for(p20: dict, when) -> tuple[float | None, bool]:
    """(cutoff, forward_filled). French's ME file lags by months, so a forward month may be absent;
    use the latest earlier month and say so rather than dropping the event as 'no cutoff'."""
    ym = pd.Timestamp(when).strftime("%Y%m")
    if ym in p20:
        return p20[ym], False
    prior = [k for k in p20 if k < ym]
    return (p20[max(prior)], True) if prior else (None, False)


def mature_bar(ohlc: pd.DataFrame, i: int) -> bool:
    """True when bars i .. i+H-1 all exist, i.e. the 60-day exit is a real close, not a clamp."""
    return i is not None and i + H - 1 <= len(ohlc) - 1


def forward_arms(events, prices, beats, p20, today, since=FORWARD_START, cost=COST, mcap=R.mcap_at):
    """Score events dated >= `since`. Returns {arm: {"graded": [...], "pending": [...]}, "drops": {...}}.

    events: [{ticker, date}]; prices: {t: ohlc (UTC index)}; beats: {t: [announcement Timestamp]}
    (point-in-time: the first 8-K 2.02 / 10-Q / 10-K after the quarter end).
    Record = (ticker, event_date, ret_or_None, est_mature_date, days_since_beat).
    """
    today = pd.Timestamp(today)
    arms = {k: {"graded": [], "pending": []} for k in ("ins_cat", "ins_nocat", "cat_only")}
    drops = {"microcap": [], "no_mcap": [], "no_price": [], "stale_price": [], "p20_ffill_months": set()}
    clustered: dict[str, list] = {}
    for e in events:
        clustered.setdefault(e["ticker"], []).append(pd.Timestamp(e["date"]))

    def gate(t, when) -> bool:
        mc = mcap(t, prices, when)
        cut, ff = p20_for(p20, when)
        if ff:
            drops["p20_ffill_months"].add(pd.Timestamp(when).strftime("%Y%m"))
        if mc is None or cut is None:
            drops["no_mcap"].append((t, str(pd.Timestamp(when).date())))
            return False
        if mc < cut:
            drops["microcap"].append((t, str(pd.Timestamp(when).date())))
            return False
        return True

    def score(arm, t, when, since_beat):
        oh = prices[t]
        i = entry_index(oh, when)
        est = pd.Timestamp(when) + pd.offsets.BDay(SHIFT + H)
        if oh.index[-1].tz_localize(None) < today - pd.Timedelta(days=STALE_DAYS):
            drops["stale_price"].append((t, str(oh.index[-1].date())))
        if i is None or not mature_bar(oh, i + SHIFT):
            arms[arm]["pending"].append((t, pd.Timestamp(when), None, est, since_beat))
            return
        arms[arm]["graded"].append((t, pd.Timestamp(when), R.fwd(oh, i + SHIFT, cost), est, since_beat))

    for e in events:
        t, ev = e["ticker"], pd.Timestamp(e["date"])
        if since is not None and ev < since:
            continue
        if t not in prices:
            drops["no_price"].append((t, str(ev.date())))
            continue
        prior = [a for a in beats.get(t, []) if 0 <= (ev - a).days <= 90]      # public on/before the filing
        if not gate(t, ev):
            continue
        score("ins_cat" if prior else "ins_nocat", t, ev, (ev - max(prior)).days if prior else None)

    for t, ds in beats.items():
        if t not in prices:
            continue
        for a in ds:
            if (since is not None and a < since) or any(abs((a - cd).days) <= 30 for cd in clustered.get(t, [])):
                continue
            if gate(t, a):
                score("cat_only", t, a, 0)
    drops["p20_ffill_months"] = sorted(drops["p20_ffill_months"])
    return {**arms, "drops": drops}


def verdict(ic: list[float], co: list[float], kill_n: int = KILL_N, kill_diff: float = KILL_DIFF) -> dict:
    """The pre-committed rule. Binding only at n_ic >= kill_n; below that it reports PENDING and,
    from INTERIM_MIN, a non-binding interim diff. Never returns KEEP/KILL early."""
    si, sc = R.stats(ic), R.stats(co)
    out = {"n_ic": len(ic), "n_co": len(co), "need": kill_n, "status": "PENDING"}
    if len(ic) >= INTERIM_MIN and len(co) >= INTERIM_MIN:
        out["diff"] = si["median"] - sc["median"]
        out["boot90"] = R.boot_median_diff(ic, co)
        out["med_ic"], out["med_co"] = si["median"], sc["median"]
    if len(ic) >= kill_n and "diff" in out:
        out["status"] = "KEEP" if out["diff"] >= kill_diff else "KILL"
    elif len(ic) >= kill_n:
        out["note"] = f"{len(ic)} insider+catalyst graded but only {len(co)} control events; the rule needs >= {INTERIM_MIN} in both arms"
    return out


def retest_rule(ic: list[float], co: list[float]) -> dict:
    """The RETEST_N39.md pre-committed survival rule, evaluated on whatever arms it is given:
    (a) n >= 20, (b) 10%-trimmed mean of ins + cat > 0 net, (c) median beats catalyst-only by >= 3pp."""
    si, sc = R.stats(ic), R.stats(co)
    diff = si["median"] - sc["median"] if si["n"] and sc["n"] else None
    a, b = si["n"] >= 20, bool(si["n"]) and si["trim10"] > 0
    c = diff is not None and diff >= KILL_DIFF
    return {"a_n": a, "b_trim": b, "c_diff": c, "survives": a and b and c, "diff": diff, "n_ic": si["n"], "n_co": sc["n"],
            "med_ic": si.get("median"), "med_co": sc.get("median"), "trim_ic": si.get("trim10"), "boot90": R.boot_median_diff(ic, co)}


# ---------- fresh data (own cache, TTL) ----------

def _ttl_json(path: str, fetch):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < TTL:
        with open(path) as f:
            return json.load(f)
    v = fetch()
    with open(path, "w") as f:
        json.dump(v, f)
    return v


def fresh_ohlc(t: str, today) -> pd.DataFrame | None:
    p = os.path.join(_FWD, "ohlc", f"{t.upper()}.csv")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < TTL:
        df = pd.read_csv(p, index_col=0, parse_dates=True)
    else:
        df = fetch_ohlc(t, "2025-01-01", pd.Timestamp(today) + pd.Timedelta(days=2), use_cache=False)
        if df is None:
            return None
        os.makedirs(os.path.dirname(p), exist_ok=True)
        df.to_csv(p)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def fresh_beats(t: str, cmap: dict, token: str) -> list | None:
    """Announcement dates of Finnhub BEAT quarters, from a fresh Finnhub + EDGAR pull. None on a
    source failure (the caller names it); [] only when the sources genuinely have no beat."""
    cik = cmap.get(t.upper())
    if not cik:
        return None
    try:
        earn = _ttl_json(os.path.join(_FWD, "earnings", f"{t.upper()}.json"),
                         lambda: requests.get(f"https://finnhub.io/api/v1/stock/earnings?symbol={t}&token={token}", timeout=30).json())
        sub = _ttl_json(os.path.join(_FWD, "subs", f"{cik}.json"),
                        lambda: requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=R.UA, timeout=30).json())
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(earn, list):
        return None
    rec = sub["filings"]["recent"]
    fil = [pd.Timestamp(d) for f, d, it in zip(rec["form"], rec["filingDate"], rec.get("items", [""] * len(rec["form"])))
           if f in R._RESULT_FORMS or (f.startswith("8-K") and "2.02" in (it or ""))]
    out = []
    for e in earn:
        sp, per = e.get("surprisePercent"), e.get("period")
        if sp is None or per is None or sp <= 0:
            continue
        pe = pd.Timestamp(per)
        cand = [d for d in fil if pe < d <= pe + pd.Timedelta(days=120)]
        if cand:
            out.append(min(cand))
    return sorted(out)


def rescore_retest_window(today=None) -> dict:
    """Re-score the frozen re-test window (events 2025-06..2026-08) on MATURED trades only.
    `retest_n39.fwd` clamps an exit to the last bar, and the frozen OHLC stops at 2026-08-06, so the
    banked L4 numbers include trades with far less than 60 days of data. Refreshes prices only for
    tickers that have an immature trade (matured trades cannot change)."""
    today = pd.Timestamp(today or pd.Timestamp.now().normalize())
    events, tickers, prices = R.load_universe()
    results, p20 = R.fetch_results_filings(tickers), R.nyse_p20()
    beats = {t: R.actual_beat_dates(t, results)[0] for t in prices}
    first = forward_arms(events, prices, beats, p20, today, since=R.CAT_START)
    need = sorted({r[0] for k in ("ins_cat", "ins_nocat", "cat_only") for r in first[k]["pending"]})
    fresh, failed = {}, []
    for t in need:
        oh = fresh_ohlc(t, today)
        (fresh.__setitem__(t, oh) if oh is not None else failed.append(t))
    res = forward_arms(events, {**prices, **fresh}, beats, p20, today, since=R.CAT_START)
    res["refreshed"], res["price_failures"] = len(fresh), failed
    return res


def run(today=None) -> dict:
    today = pd.Timestamp(today or pd.Timestamp.now().normalize())
    _, frozen_tickers, _ = R.load_universe()
    txns = fetch_panel(FORWARD_START.strftime("%Y-%m"), today.strftime("%Y-%m"), use_cache=False)
    events = [e for e in build_cluster_events(txns) if pd.Timestamp(e["date"]) >= FORWARD_START]
    tickers = sorted(set(frozen_tickers) | {e["ticker"] for e in events})
    cmap, token, p20 = R._cik_map(), _key(), R.nyse_p20()
    prices, beats, failed = {}, {}, []
    for t in tickers:
        oh = fresh_ohlc(t, today)
        b = fresh_beats(t, cmap, token)
        if oh is None or b is None:
            failed.append((t, "no price" if oh is None else "no beats"))
            continue
        prices[t], beats[t] = oh, b
    res = forward_arms(events, prices, beats, p20, today)
    res["source_failures"] = failed
    res["universe"], res["events"] = len(tickers), len(events)
    return res


def report(res: dict) -> str:
    L = [f"forward window since {FORWARD_START.date()} | universe {res.get('universe', '?')} | cluster events {res.get('events', '?')}"]
    g = {k: [r[2] for r in res[k]["graded"]] for k in ("ins_cat", "ins_nocat", "cat_only")}
    for k in ("ins_cat", "ins_nocat", "cat_only"):
        pend = res[k]["pending"]
        nxt = min((r[3] for r in pend), default=None)
        L.append(f"  {k:10s} graded {len(g[k]):3d}  pending {len(pend):3d}" + (f"  next matures ~{nxt.date()}" if nxt is not None else ""))
    v = verdict(g["ins_cat"], g["cat_only"])
    L.append(f"RULE: {v['status']}  ins+cat graded {v['n_ic']}/{v['need']}")
    if "diff" in v:
        lo, hi = v["boot90"]
        L.append(f"  interim (non-binding) median diff {v['diff']:+.2%}  [ins+cat {v['med_ic']:+.2%} vs cat-only {v['med_co']:+.2%}]  90% [{lo}, {hi}]")
    d = res["drops"]
    for k in ("microcap", "no_mcap", "no_price", "stale_price"):
        if d[k]:
            L.append(f"  dropped {k}: " + ", ".join(f"{t}@{w}" for t, w in d[k][:25]) + (" ..." if len(d[k]) > 25 else ""))
    if d["p20_ffill_months"]:
        L.append(f"  p20 cutoff forward-filled for months {d['p20_ffill_months']}")
    for t, why in res.get("source_failures", [])[:25]:
        L.append(f"  SOURCE FAILURE {t}: {why}")
    return "\n".join(L)


def report_window(res: dict) -> str:
    g = {k: [r[2] for r in res[k]["graded"]] for k in ("ins_cat", "ins_nocat", "cat_only")}
    v = retest_rule(g["ins_cat"], g["cat_only"])
    L = [f"re-test window on MATURED trades ({res['refreshed']} tickers refreshed, price failures: {res['price_failures'] or 'none'})"]
    for k in ("ins_cat", "cat_only", "ins_nocat"):
        s = R.stats(g[k])
        L.append(f"  {k:10s} n={s['n']:3d} median={s['median']:+.2%} trim10={s['trim10']:+.2%} hit={s['hit']:.0%} pending={len(res[k]['pending'])}")
    lo, hi = v["boot90"]
    L.append(f"  diff {v['diff']:+.2%}  90% [{lo:+.2%}, {hi:+.2%}]")
    L.append(f"  rule: (a) n>=20 {v['a_n']} | (b) trim10>0 {v['b_trim']} | (c) diff>=3pp {v['c_diff']}  ->  {'SURVIVES' if v['survives'] else 'DOWNGRADED (not established)'}")
    return "\n".join(L)


if __name__ == "__main__":
    if "--retest-window" in sys.argv:
        print(report_window(rescore_retest_window()))
        sys.exit(0)
    res = run()
    print(report(res))
    sys.exit(1 if res.get("source_failures") else 0)
