"""Applies the decision rule pre-registered in VETO_REPLAY_CATONLY.md to the rows `veto_replay` wrote.

The rule lives here as code so the verdict is computed, not read off a table. It was committed before the
replay ran; do not change the thresholds after seeing a result (write a new pre-registration instead).

    PYTHONPATH=. uv run python -W ignore -m backtesting.insider_cluster.veto_replay_decide [--arm cat_only]
"""
from __future__ import annotations

import json
import os
import sys

from backtesting.insider_cluster import retest_n39 as R

_ROWS = os.path.join(os.path.dirname(__file__), ".cache", "veto_replay_rows.json")

MIN_VETOES = 15      # below this the veto cannot be shown to earn a place
MIN_DIFF = 0.03      # median(not vetoed) - median(vetoed), 3.0pp
BOOT_REPS = 10_000   # pre-registered; the library default is 4,000


def decide(rows: list[dict], arm: str) -> dict:
    """rows: veto_replay rows. ERROR rows are counted and excluded, never treated as CLEAR."""
    mine = [r for r in rows if r["arm"] == arm]
    errors = [(r["ticker"], r["date"]) for r in mine if r["verdict"] == "ERROR"]
    ok = [r for r in mine if r["verdict"] != "ERROR"]
    v = [r["ret"] for r in ok if r["verdict"] == "VETO"]
    n = [r["ret"] for r in ok if r["verdict"] != "VETO"]
    out = {"arm": arm, "events": len(mine), "errors": errors, "n_veto": len(v), "n_not_veto": len(n)}
    if len(v) < MIN_VETOES or len(n) < MIN_VETOES:
        return {**out, "outcome": "INCONCLUSIVE", "reason": f"n(V)={len(v)} < {MIN_VETOES}" if len(v) < MIN_VETOES else f"n(N)={len(n)} < {MIN_VETOES}"}
    sv, sn = R.stats(v), R.stats(n)
    diff = sn["median"] - sv["median"]
    lo, hi = R.boot_median_diff(n, v, reps=BOOT_REPS)   # median(N) - median(V)
    earns = diff >= MIN_DIFF and lo is not None and lo > 0
    allr = [r["ret"] for r in ok]
    ranked = sorted(allr, reverse=True)
    top = set(ranked[: max(1, len(ranked) // 10)])
    return {**out, "outcome": "VETO EARNS ITS PLACE" if earns else "NO EVIDENCE IT HELPS",
            "diff": diff, "boot90": (lo, hi), "veto": sv, "not_veto": sn,
            "all_median": R.stats(allr)["median"], "all_mean": R.stats(allr)["mean"],
            "excl_veto_median": sn["median"], "excl_veto_mean": sn["mean"],
            "top_decile_vetoed": sum(1 for r in ok if r["verdict"] == "VETO" and r["ret"] in top), "top_decile_n": len(top)}


def main(arm: str = "cat_only") -> None:
    with open(_ROWS) as f:
        rows = json.load(f)
    print(json.dumps(decide(rows, arm), indent=1, default=str))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[a.index("--arm") + 1] if "--arm" in a else "cat_only")
