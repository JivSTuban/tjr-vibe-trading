"""Stress the intraday result before believing it.

The 57-day intraday window is the ONLY place the spec's late-pressure gate can be
measured, and it produces a much larger number than the 12.7-year run. Three things
have to be ruled out before that number means anything:

  1. REGIME. The whole window may simply be rich. Measured as the excess of each
     rung over the SAME-WINDOW control, not against the long-history baseline.
  2. CONCENTRATION. `stock-scan-performance-audit` found 5 of 7 stops died on two
     days — one trade in seven tickers. If a handful of sessions carry the result it
     is one observation, not 526.
  3. STABILITY. First half vs second half of the window.

    uv run python -m backtesting.eod_1pct_reversal.analyze
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

RUNS = os.path.join(os.path.dirname(__file__), "runs")


def load(tag: str = "intraday_trades") -> pd.DataFrame:
    path = os.path.join(RUNS, f"{tag}.csv")
    if not os.path.exists(path):
        raise SystemExit(f"missing {path} — run `run.py --mode intraday` first")
    df = pd.read_csv(path, parse_dates=["date"])
    return df


def bps(s: pd.Series) -> float:
    return round(float(s.mean()) * 10000, 2)


def concentration(tr: pd.DataFrame) -> dict:
    """How much of the total return comes from the best few sessions and tickers."""
    total = tr["gross_ret"].sum()
    by_day = tr.groupby("date")["gross_ret"].sum().sort_values(ascending=False)
    by_tkr = tr.groupby("ticker")["gross_ret"].sum().sort_values(ascending=False)
    out = {
        "n_trades": int(len(tr)),
        "n_sessions": int(tr["date"].nunique()),
        "n_tickers": int(tr["ticker"].nunique()),
        "total_ret_sum": round(float(total), 4),
    }
    for k in (1, 3, 5):
        out[f"top{k}_sessions_share"] = round(float(by_day.head(k).sum() / total), 3) if total else np.nan
        out[f"top{k}_tickers_share"] = round(float(by_tkr.head(k).sum() / total), 3) if total else np.nan
    # Median trade count per session: a "strategy" firing 9 names a day into one theme
    # is one bet, not nine.
    out["median_trades_per_session"] = float(tr.groupby("date").size().median())
    out["mean_bps"] = bps(tr["gross_ret"])
    out["median_bps"] = round(float(tr["gross_ret"].median()) * 10000, 2)
    # Drop the best session entirely and see what survives.
    if len(by_day):
        worst = tr[tr["date"] != by_day.index[0]]
        out["mean_bps_ex_best_session"] = bps(worst["gross_ret"])
    return out


def halves(tr: pd.DataFrame) -> list[dict]:
    days = sorted(tr["date"].unique())
    mid = days[len(days) // 2]
    rows = []
    for name, sub in (("first_half", tr[tr["date"] < mid]), ("second_half", tr[tr["date"] >= mid])):
        if sub.empty:
            continue
        g = sub["gross_ret"]
        rows.append({
            "half": name, "n": int(len(g)), "mean_bps": bps(g),
            "hit_rate": round(float(sub["hit_target"].mean()), 3),
            "t_stat": round(float(g.mean() / (g.std(ddof=1) / np.sqrt(len(g)))), 2)
            if len(g) > 2 and g.std(ddof=1) > 0 else np.nan,
        })
    return rows


def main() -> None:
    tr = load()
    out = {}
    for rung, sub in tr.groupby("rung"):
        for h, s2 in sub.groupby("horizon"):
            key = f"{rung}|T+{h}"
            out[key] = {"concentration": concentration(s2), "halves": halves(s2)}

    with open(os.path.join(RUNS, "intraday_stress.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)

    rows = []
    for key, v in out.items():
        c = v["concentration"]
        rows.append({
            "rung": key, "n": c["n_trades"], "sessions": c["n_sessions"],
            "mean_bps": c["mean_bps"], "ex_best_day": c["mean_bps_ex_best_session"],
            "top1_day": c["top1_sessions_share"], "top3_days": c["top3_sessions_share"],
            "top3_tkrs": c["top3_tickers_share"],
            "per_session": c["median_trades_per_session"],
        })
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n[halves]")
    for key, v in out.items():
        for r in v["halves"]:
            print(f"  {key:26s} {r['half']:12s} n={r['n']:5d} {r['mean_bps']:8.2f} bps  "
                  f"hit={r['hit_rate']:.3f}  t={r['t_stat']}")


if __name__ == "__main__":
    main()
