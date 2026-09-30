"""Replay the 8-K/6-K veto (stock-scan/engines/veto_extract.mjs) AS OF each historical insider event.

Question: among the re-test's insider events (2025-06..2026-08), did the events the veto would have
blocked do worse over the next 60 trading days? That is the standard the DD gate was held to
("12 vetoes avg -1.4%, 0 winners missed"), and it is the only honest precision test: judge a gate on
a replayed sample, never on the fixtures it was built from.

Look-ahead guard: each run passes `--asof <event date>`; `listFilings` treats it as an UPPER bound,
so the veto never reads a filing made after the event. Returns come from `forward_n39`'s matured
grading (full 60-bar window, t+2 open, 150 bps, ex-microcap), so the outcome side is clean too.

Not independent of the taxonomy's authors: the prompts were written after GME / RWT / ADC / INR
(2026-09), none of which is in this sample, but the sample is small. Read the table as a sanity
check on direction and on "did it veto a winner", not as a significance test.

    uv run python -m backtesting.insider_cluster.veto_replay [--limit N] [--workers 4] [--arms ins_cat,ins_nocat]
Results are cached per (ticker, date) under .cache/veto_replay/ so a rerun costs nothing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from backtesting.insider_cluster import forward_n39 as F
from backtesting.insider_cluster import retest_n39 as R

_HERE = os.path.dirname(__file__)
_CACHE = os.path.join(_HERE, ".cache", "veto_replay")
_ENGINE = os.path.abspath(os.path.join(_HERE, "..", "..", "stock-scan", "engines", "veto_extract.mjs"))


def run_one(ticker: str, date: str, *, runner=None) -> dict:
    """Veto result for one event, cached. A crash or unparseable output is an ERROR row, never a
    silent CLEAR (the same fail-closed rule as the engine)."""
    os.makedirs(_CACHE, exist_ok=True)
    p = os.path.join(_CACHE, f"{ticker}_{date}.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    try:
        if runner is not None:
            res = runner(ticker, date)
        else:
            r = subprocess.run(["node", _ENGINE, ticker, "--asof", date, "--json"], capture_output=True, text=True, timeout=3600)   # a serial ATM issuer (MSTR) has 20+ filings
            res = json.loads(r.stdout)[0]
            if r.returncode != 0 and "verdict" not in res:
                raise RuntimeError(r.stderr[-200:])
    except Exception as e:  # noqa: BLE001
        return {"ticker": ticker, "verdict": "ERROR", "error": str(e)[:200], "rows": [], "unknowns": []}
    with open(p, "w") as f:
        json.dump(res, f)
    return res


def summarize(rows: list[dict]) -> dict:
    """rows: [{ticker, date, arm, ret, verdict}] -> per (arm, verdict) stats plus named lists."""
    out: dict = {"by": {}, "vetoed": [], "errors": []}
    for r in rows:
        if r["verdict"] == "ERROR":
            out["errors"].append((r["ticker"], r["date"]))
            continue
        out["by"].setdefault((r["arm"], r["verdict"]), []).append(r["ret"])
        if r["verdict"] == "VETO":
            out["vetoed"].append(r)
    out["stats"] = {k: R.stats(v) for k, v in out["by"].items()}
    return out


def render(s: dict) -> str:
    L = ["arm        verdict   n   median    hit"]
    for (arm, v), st in sorted(s["stats"].items()):
        L.append(f"{arm:10s} {v:7s} {st['n']:3d}  {st['median']:+7.2%}  {st['hit']:4.0%}")
    for r in sorted(s["vetoed"], key=lambda r: r["ret"]):
        L.append(f"  VETO {r['arm']:9s} {r['ticker']:6s} {r['date']}  ret {r['ret']:+7.2%}  {r.get('why', '')}")
    if s["errors"]:
        L.append("  ERRORS (excluded, named): " + ", ".join(f"{t}@{d}" for t, d in s["errors"]))
    return "\n".join(L)


def why(res: dict) -> str:
    """One-line reason for a veto: the confirmed/provisional VETO-class findings, by label."""
    k = [f"{x['label']}" + (f" {x['amount']}" if x.get("amount") else "") + (f" {x['shares']}" if x.get("shares") else "")
         for x in res.get("rows", []) if x.get("status") in ("CONFIRMED", "PROVISIONAL") and x.get("cls") == "VETO"]
    return "; ".join(k[:3])


def main(limit: int | None = None, workers: int = 4, arms: tuple = ("ins_cat",)) -> None:
    """Default arms = ins_cat only. In production the beat gate refuses a bare insider buy BEFORE the
    veto runs, so the veto's real population is the names that already have a public beat; vetoing
    the ins_nocat events would cost ~3x as much and answer a question nobody asks."""
    res = F.rescore_retest_window()
    events = [(arm, t, d, r) for arm in arms for (t, d, r, *_ ) in res[arm]["graded"]]
    events.sort(key=lambda e: (e[2], e[1]))
    if limit:
        events = events[:limit]
    print(f"{len(events)} matured insider events; veto as-of each event date, {workers} workers", flush=True)

    def job(e):
        arm, t, d, r = e
        ds = str(d.date())
        v = run_one(t, ds)
        return {"arm": arm, "ticker": t, "date": ds, "ret": r, "verdict": v["verdict"], "why": why(v), "n_unknown": len(v.get("unknowns", []))}

    with ThreadPoolExecutor(workers) as ex:
        rows = []
        for i, row in enumerate(ex.map(job, events), 1):
            rows.append(row)
            if i % 5 == 0:
                print(f"  {i}/{len(events)}", flush=True)
    s = summarize(rows)
    print(render(s))
    with open(os.path.join(_HERE, ".cache", "veto_replay_rows.json"), "w") as f:
        json.dump(rows, f)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[a.index("--limit") + 1]) if "--limit" in a else None, int(a[a.index("--workers") + 1]) if "--workers" in a else 4,
         tuple(a[a.index("--arms") + 1].split(",")) if "--arms" in a else ("ins_cat",))
