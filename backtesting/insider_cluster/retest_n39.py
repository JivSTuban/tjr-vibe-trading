"""Re-test of the banked n=39 insider-cluster + earnings-catalyst result (see RETEST_N39.md).

Why this exists: the original catalyst label (catalyst.py) dates an earnings beat as
`fiscal period end + 35 days` and accepts it up to 5 days AFTER the insider filing, so a beat
announced during the hold could be counted as a "coincident" catalyst. This module rebuilds the
arms on the SAME cached events and prices, then applies one fix at a time:

  L0  replica of run.py (must reproduce n=39, median +11.15% before anything else is trusted)
  L1  point-in-time catalyst: real announcement date from SEC EDGAR, announced <= event date
  L2  + entry at the t+2 open
  L3  + ex-microcap (market cap at the event >= cutoff)
  L4  + 150 bps round trip

Network is used only by `fetch_announcements` / `fetch_shares`, which cache to .cache/.

KNOWN DEFECT (found 2026-10-01): `fwd` clamps the exit to the last available bar and the frozen OHLC
stops at 2026-08-06, so the "60d" returns below include trades with far less than 60 days of data
(5 of the 24 ins + cat trades, 58 of the 262 catalyst-only). On matured trades with refreshed
prices the rule FAILS check (c). See RETEST_N39.md "Correction 2026-10-01" and
`forward_n39.py --retest-window`. L0 must keep the clamp (it replicates run.py).
"""
from __future__ import annotations

import json
import os
import random
import time
from collections import defaultdict

import pandas as pd
import requests

from backtesting.insider_cluster.catalyst import load_earnings, had_beat_near, beat_events
from backtesting.insider_cluster.panel import load_panel, build_cluster_events
from backtesting.insider_cluster.run import CAT_START, entry_index
from backtesting.swing_bounce.prices_ohlc import load_ohlc

_HERE = os.path.dirname(__file__)
_CACHE = os.path.join(_HERE, ".cache")
UA = {"User-Agent": "trader retest jivtuban14@gmail.com"}
H = 60
START, END, MAX_TICKERS = "2021-01", "2026-08", 350   # identical to run.py


# ---------- events + universe, exactly as run.py built them ----------

def load_universe():
    events = build_cluster_events(load_panel(START, END))
    by_val = defaultdict(float)
    for e in events:
        by_val[e["ticker"]] += e["total_value"]
    tickers = [t for t, _ in sorted(by_val.items(), key=lambda kv: -kv[1])][:MAX_TICKERS]
    keep = set(tickers)
    events = [e for e in events if e["ticker"] in keep]
    prices = {}
    for t in tickers:
        try:
            prices[t] = load_ohlc(t)
        except Exception:  # noqa: BLE001  (uncovered ticker, same as run.py)
            pass
    return events, tickers, prices


def fwd(ohlc: pd.DataFrame, i: int | None, cost_rt_bps: float) -> float | None:
    """Enter at open[i], exit at close[i+H-1]; same mechanics as run.fwd_return."""
    if i is None or i >= len(ohlc):
        return None
    entry = float(ohlc["open"].iloc[i])
    if not entry or entry != entry:
        entry = float(ohlc["close"].iloc[i])
    j = min(i + H - 1, len(ohlc) - 1)
    return float(ohlc["close"].iloc[j]) / entry - 1.0 - cost_rt_bps / 1e4


# ---------- stats: proper median, trimmed mean, bootstrap ----------

def stats(xs: list[float]) -> dict:
    n = len(xs)
    if not n:
        return {"n": 0}
    s = sorted(xs)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    k = int(n * 0.10)
    core = s[k:n - k] if n - 2 * k > 0 else s
    return {"n": n, "mean": sum(xs) / n, "median": med, "median_orig": s[n // 2],
            "trim10": sum(core) / len(core), "hit": sum(x > 0 for x in xs) / n}


def boot_median_diff(a: list[float], b: list[float], reps: int = 4000, seed: int = 7) -> tuple:
    """90% bootstrap interval for median(a) - median(b)."""
    if len(a) < 3 or len(b) < 3:
        return (None, None)
    rnd = random.Random(seed)
    med = lambda v: stats(v)["median"]
    d = sorted(med([rnd.choice(a) for _ in a]) - med([rnd.choice(b) for _ in b]) for _ in range(reps))
    return (d[int(0.05 * reps)], d[int(0.95 * reps)])


# ---------- point-in-time announcement dates (SEC EDGAR) ----------

_RESULT_FORMS = {"10-Q", "10-K", "20-F", "40-F", "10-Q/A", "10-K/A"}


def _cik_map() -> dict[str, str]:
    p = os.path.join(_CACHE, "sec_company_tickers.json")
    if not os.path.exists(p):
        d = requests.get("https://www.sec.gov/files/company_tickers.json", headers=UA, timeout=30).json()
        with open(p, "w") as f:
            json.dump(d, f)
    with open(p) as f:
        d = json.load(f)
    return {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in d.values()}


def fetch_results_filings(tickers: list[str]) -> dict[str, list[pd.Timestamp]]:
    """Per ticker, the dates the market could first read quarterly results: 8-K Item 2.02
    (earnings release) plus 10-Q/10-K/20-F/40-F. Cached per CIK. Missing CIK -> absent key."""
    cmap = _cik_map()
    os.makedirs(os.path.join(_CACHE, "edgar_subs"), exist_ok=True)
    out = {}
    for t in tickers:
        cik = cmap.get(t.upper())
        if not cik:
            continue
        p = os.path.join(_CACHE, "edgar_subs", f"{cik}.json")
        if not os.path.exists(p):
            r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=UA, timeout=30)
            if r.status_code != 200:
                continue
            with open(p, "w") as f:
                f.write(r.text)
            time.sleep(0.15)
        with open(p) as f:
            rec = json.load(f)["filings"]["recent"]
        dates = []
        for form, fd, items in zip(rec["form"], rec["filingDate"], rec.get("items", [""] * len(rec["form"]))):
            if form in _RESULT_FORMS or (form.startswith("8-K") and "2.02" in (items or "")):
                dates.append(pd.Timestamp(fd))
        out[t] = sorted(dates)
    return out


def actual_beat_dates(t: str, results: dict, min_surprise: float = 0.0) -> tuple[list, int]:
    """Real announcement date of each Finnhub BEAT quarter = earliest results filing within
    (period_end, period_end + 120d]. Returns (dates, n_beats_with_no_matching_filing)."""
    got, unmatched = [], 0
    fil = results.get(t)
    for e in load_earnings(t):
        sp, per = e.get("surprisePercent"), e.get("period")
        if sp is None or per is None or sp <= min_surprise:
            continue
        pe = pd.Timestamp(per)
        cand = [d for d in (fil or []) if pe < d <= pe + pd.Timedelta(days=120)]
        if cand:
            got.append(min(cand))
        else:
            unmatched += 1
    return sorted(got), unmatched


# ---------- market cap at the event (point in time) ----------

def nyse_p20() -> dict[str, float]:
    """Month -> NYSE 20th-percentile market cap in $ (Ken French ME breakpoints). The standard
    microcap line (Fama-French; Martineau 2022 uses it for 'all-but-microcap')."""
    p = os.path.join(_CACHE, "me_breakpoints_p20.json")
    if not os.path.exists(p):
        import io
        import zipfile
        u = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/ME_Breakpoints_CSV.zip"
        z = zipfile.ZipFile(io.BytesIO(requests.get(u, headers=UA, timeout=60).content))
        txt = z.read(z.namelist()[0]).decode("latin-1")
        bp = {}
        for ln in txt.splitlines():
            c = [x.strip() for x in ln.split(",")]
            if len(c) > 6 and c[0].isdigit() and len(c[0]) == 6:
                bp[c[0]] = float(c[5]) * 1e6          # col 5 = 20th percentile, $ millions
        with open(p, "w") as f:
            json.dump(bp, f)
    with open(p) as f:
        return json.load(f)


def _shares_series(t: str) -> list[tuple]:
    """(filed, shares) from EDGAR dei:EntityCommonStockSharesOutstanding, summing share classes
    reported in the same filing. Falls back to us-gaap:CommonStockSharesOutstanding."""
    cik = _cik_map().get(t.upper())
    if not cik:
        return []
    os.makedirs(os.path.join(_CACHE, "edgar_shares"), exist_ok=True)
    p = os.path.join(_CACHE, "edgar_shares", f"{cik}.json")
    if not os.path.exists(p):
        data = {}
        for tax, tag in (("dei", "EntityCommonStockSharesOutstanding"), ("us-gaap", "CommonStockSharesOutstanding")):
            r = requests.get(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{tax}/{tag}.json",
                             headers=UA, timeout=30)
            time.sleep(0.15)
            if r.status_code == 200:
                data = r.json()
                break
        with open(p, "w") as f:
            json.dump(data, f)
    with open(p) as f:
        data = json.load(f)
    by_accn = defaultdict(lambda: [None, 0.0])
    for pts in (data.get("units") or {}).values():
        for x in pts:
            k = (x.get("accn"), x.get("end"))
            by_accn[k][0] = x.get("filed")
            by_accn[k][1] += float(x.get("val") or 0)
    return sorted((pd.Timestamp(f), v) for f, v in by_accn.values() if f and v > 0)


def _yf_shares(t: str) -> list[tuple]:
    """Fallback: Yahoo's dated share-count history. Needed because SEC's concept API drops
    class-dimensioned facts (multi-class issuers such as AMH, TKO, BGC return nothing) and
    recent IPOs have no SEC share count before the event. Dates are as-of, not publication."""
    os.makedirs(os.path.join(_CACHE, "yf_shares"), exist_ok=True)
    p = os.path.join(_CACHE, "yf_shares", f"{t.upper()}.csv")
    if not os.path.exists(p):
        try:
            import yfinance as yf
            s = yf.Ticker(t).get_shares_full(start="2024-01-01", end="2026-09-30")
        except Exception:  # noqa: BLE001
            s = None
        df = pd.DataFrame({"date": [], "shares": []}) if s is None or not len(s) else \
            pd.DataFrame({"date": [d.tz_localize(None) if d.tzinfo else d for d in s.index], "shares": s.values})
        df.to_csv(p, index=False)
        time.sleep(0.3)
    df = pd.read_csv(p, parse_dates=["date"])
    return sorted((pd.Timestamp(d), float(v)) for d, v in zip(df["date"], df["shares"]) if v and v > 0)


MCAP_SOURCE: dict = defaultdict(int)          # which source priced each lookup (reported, not silent)


def mcap_at(t: str, prices: dict, when) -> float | None:
    ev = pd.Timestamp(when)
    sh = [v for f, v in _shares_series(t) if f <= ev]
    src = "sec"
    if not sh:
        sh = [v for d, v in _yf_shares(t) if d <= ev]
        src = "yahoo"
    if not sh:
        MCAP_SOURCE["none"] += 1
        return None
    px = prices[t]["close"]
    idx = px.index.tz_localize(None) if px.index.tz is not None else px.index
    before = px[idx <= ev]
    if not len(before):
        MCAP_SOURCE["none"] += 1
        return None
    MCAP_SOURCE[src] += 1
    return float(before.iloc[-1]) * sh[-1]


# ---------- the ladder ----------

def ladder(events, prices, level: int, cost_rt_bps: float, results: dict, p20: dict) -> dict:
    """Rebuild the three arms with fixes L1..level applied (see module docstring)."""
    arms, clustered, dropped = defaultdict(list), defaultdict(list), defaultdict(int)
    real = {t: actual_beat_dates(t, results)[0] for t in prices}
    shift = 1 if level >= 2 else 0

    def big_enough(t, when) -> bool:
        if level < 3:
            return True
        mc = mcap_at(t, prices, when)
        cut = p20.get(pd.Timestamp(when).strftime("%Y%m"))
        if mc is None or cut is None:
            dropped["no_mcap"] += 1
            return False
        if mc < cut:
            dropped["microcap"] += 1
            return False
        return True

    for e in events:
        t = e["ticker"]
        if t not in prices:
            continue
        ev = pd.Timestamp(e["date"])
        clustered[t].append(ev)
        if ev < CAT_START:
            continue
        if level >= 1:
            prior = [a for a in real[t] if 0 <= (ev - a).days <= 90]      # public on/before the filing
            has_cat = bool(prior)
        else:
            prior, has_cat = [], had_beat_near(t, e["date"])
        i = entry_index(prices[t], e["date"])
        if i is None or not big_enough(t, ev):
            continue
        r = fwd(prices[t], i + shift, cost_rt_bps)
        if r is None:
            continue
        rec = (t, ev, r, (ev - max(prior)).days if prior else None)
        (arms["ins_cat"] if has_cat else arms["ins_nocat"]).append(rec)

    for t in prices:
        for a in (real[t] if level >= 1 else beat_events(t)):
            if a < CAT_START or any(abs((a - cd).days) <= 30 for cd in clustered.get(t, [])):
                continue
            i = entry_index(prices[t], a)
            if i is None or not big_enough(t, a):
                continue
            r = fwd(prices[t], i + shift, cost_rt_bps)
            if r is not None:
                arms["cat_only"].append((t, a, r, 0))
    arms["_dropped"] = dict(dropped)
    return arms


def matched_delay_control(prices, results, events, delays, cost_rt_bps, p20, shift=1) -> list:
    """Catalyst-only beats entered at the SAME delays after the announcement that the insider
    arm actually had. Diagnostic only (not the pre-committed control)."""
    clustered = defaultdict(list)
    for e in events:
        clustered[e["ticker"]].append(pd.Timestamp(e["date"]))
    out = []
    for t in prices:
        for a in actual_beat_dates(t, results)[0]:
            if a < CAT_START or any(abs((a - cd).days) <= 30 for cd in clustered.get(t, [])):
                continue
            for d in delays:
                when = a + pd.Timedelta(days=d)
                mc, cut = mcap_at(t, prices, when), p20.get(when.strftime("%Y%m"))
                if mc is None or cut is None or mc < cut:
                    continue
                i = entry_index(prices[t], when)
                r = fwd(prices[t], None if i is None else i + shift, cost_rt_bps)
                if r is not None:
                    out.append(r)
    return out


# ---------- L0: replica ----------

def arms_replica(events, prices, cost_rt_bps=30.0):
    arms = defaultdict(list)
    clustered = defaultdict(list)
    for e in events:
        t = e["ticker"]
        if t not in prices:
            continue
        clustered[t].append(pd.Timestamp(e["date"]))
        if pd.Timestamp(e["date"]) < CAT_START:
            continue
        r = fwd(prices[t], entry_index(prices[t], e["date"]), cost_rt_bps)
        if r is None:
            continue
        (arms["ins_cat"] if had_beat_near(t, e["date"]) else arms["ins_nocat"]).append((t, e["date"], r))
    for t in prices:
        for a in beat_events(t):
            if a < CAT_START or any(abs((a - cd).days) <= 30 for cd in clustered.get(t, [])):
                continue
            r = fwd(prices[t], entry_index(prices[t], a), cost_rt_bps)
            if r is not None:
                arms["cat_only"].append((t, a, r))
    return arms


if __name__ == "__main__":
    events, tickers, prices = load_universe()
    print(f"events {len(events)} | tickers {len(tickers)} | priced {len(prices)}")
    arms = arms_replica(events, prices)
    for k in ("ins_cat", "cat_only", "ins_nocat"):
        s = stats([r for *_, r in arms[k]])
        print(f"L0 {k:10s} n={s['n']:4d} mean={s['mean']:+.2%} median(orig s[n//2])={s['median_orig']:+.2%} "
              f"median={s['median']:+.2%} trim10={s['trim10']:+.2%} hit={s['hit']:.0%}")

    # --- diagnostic: for each of the n=39, when was its beat REALLY announced? ---
    results = fetch_results_filings(sorted(prices))
    print(f"\nEDGAR results filings found for {len(results)}/{len(prices)} priced tickers")
    rows = []
    for t, d, r in arms["ins_cat"]:
        ev = pd.Timestamp(d)
        approx = [a for a in beat_events(t) if -5 <= (ev - a).days <= 90]       # what the label used
        real, _ = actual_beat_dates(t, results)
        # the real announcement of the SAME quarter(s) the label matched
        pairs = []
        for e in load_earnings(t):
            sp, per = e.get("surprisePercent"), e.get("period")
            if sp is None or per is None or sp <= 0:
                continue
            a = pd.Timestamp(per) + pd.Timedelta(days=35)
            if -5 <= (ev - a).days <= 90:
                pe = pd.Timestamp(per)
                cand = [x for x in results.get(t, []) if pe < x <= pe + pd.Timedelta(days=120)]
                pairs.append((pe.date(), a.date(), min(cand).date() if cand else None))
        known = any(p[2] is not None and pd.Timestamp(p[2]) <= ev for p in pairs)
        unknown = all(p[2] is None for p in pairs)
        rows.append((t, ev.date(), r, pairs, "KNOWN" if known else ("NO-FILING" if unknown else "AFTER-ENTRY")))
    from collections import Counter
    print("n=39 catalyst status at the insider event:", dict(Counter(x[4] for x in rows)))
    for t, ev, r, pairs, st in sorted(rows, key=lambda x: x[4]):
        pp = "; ".join(f"q{pe} approx {a} real {re_}" for pe, a, re_ in pairs)
        print(f"  {st:11s} {t:6s} event {ev} ret {r:+7.2%}  {pp}")
    for st in ("KNOWN", "AFTER-ENTRY", "NO-FILING"):
        s = stats([x[2] for x in rows if x[4] == st])
        if s["n"]:
            print(f"  -> {st:11s} n={s['n']:3d} median={s['median']:+.2%} trim10={s['trim10']:+.2%} hit={s['hit']:.0%}")

    # --- the ladder ---
    p20 = nyse_p20()
    names = {0: "L0 replica (t+1, approx date)", 1: "L1 + point-in-time catalyst",
             2: "L2 + t+2 open", 3: "L3 + ex-microcap (NYSE p20)", 4: "L4 + 150 bps round trip"}
    final = None
    print("\n=== LADDER (60d) ===")
    for lvl in range(5):
        cost = 150.0 if lvl >= 4 else 30.0
        a = ladder(events, prices, min(lvl, 3), cost, results, p20)
        ic, co, nc = ([r for _, _, r, _ in a[k]] for k in ("ins_cat", "cat_only", "ins_nocat"))
        si, sc, sn = stats(ic), stats(co), stats(nc)
        lo, hi = boot_median_diff(ic, co)
        print(f"{names[lvl]}  dropped={a['_dropped']}")
        for lab, s in (("ins+cat", si), ("cat_only", sc), ("ins_nocat", sn)):
            if s["n"]:
                print(f"    {lab:9s} n={s['n']:4d} median={s['median']:+7.2%} trim10={s['trim10']:+7.2%} "
                      f"mean={s['mean']:+7.2%} hit={s['hit']:.0%}")
        if lo is not None:
            print(f"    median(ins+cat) - median(cat_only) = {si['median'] - sc['median']:+.2%}  "
                  f"90% boot [{lo:+.2%}, {hi:+.2%}]")
        final = (a, si, sc, lo, hi)

    a, si, sc, lo, hi = final
    delays = [d for *_, d in a["ins_cat"] if d is not None]
    print(f"\nins+cat delay after the announcement (days): median {sorted(delays)[len(delays)//2] if delays else '-'}"
          f", range {min(delays) if delays else '-'}..{max(delays) if delays else '-'}")
    md = matched_delay_control(prices, results, events, delays, 150.0, p20)
    sm = stats(md)
    if sm["n"]:
        print(f"DIAGNOSTIC matched-delay cat_only (L4): n={sm['n']} median={sm['median']:+.2%} "
              f"trim10={sm['trim10']:+.2%} hit={sm['hit']:.0%}")
    print("\nfinal ins+cat names:", ", ".join(f"{t}{r:+.0%}" for t, _, r, _ in sorted(a["ins_cat"], key=lambda x: -x[2])))
    print("market-cap lookups by source:", dict(MCAP_SOURCE))

    # --- diagnostics (not pre-committed): repeat events and borderline caps ---
    by_t = defaultdict(list)
    for t, _, r, _ in a["ins_cat"]:
        by_t[t].append(r)
    per_t = [sum(v) / len(v) for v in by_t.values()]
    sp = stats(per_t)
    print(f"DIAGNOSTIC one-vote-per-ticker ins+cat: {len(by_t)} tickers, median={sp['median']:+.2%} "
          f"trim10={sp['trim10']:+.2%} hit={sp['hit']:.0%}")
    border = []
    for t, ev, r, _ in a["ins_cat"]:
        mc, cut = mcap_at(t, prices, ev), p20.get(pd.Timestamp(ev).strftime("%Y%m"))
        if mc and cut and mc < 2 * cut:
            border.append(f"{t} ${mc/1e9:.2f}B vs cut ${cut/1e9:.2f}B")
    print("borderline (<2x cutoff):", "; ".join(border) or "none")

    print("\n=== PRE-COMMITTED RULE (L4) ===")
    ca, cb, cc = si.get("n", 0) >= 20, si.get("trim10", -1) > 0, (si.get("median", 0) - sc.get("median", 0)) >= 0.03
    print(f"(a) n >= 20: {si.get('n')} -> {'PASS' if ca else 'FAIL'}")
    print(f"(b) trim10 > 0 net: {si.get('trim10', float('nan')):+.2%} -> {'PASS' if cb else 'FAIL'}")
    print(f"(c) median - cat_only median >= 3pp: {si.get('median', 0) - sc.get('median', 0):+.2%} -> {'PASS' if cc else 'FAIL'}")
    print("VERDICT:", "SURVIVES" if (ca and cb and cc) else "DOWNGRADED to not established")
