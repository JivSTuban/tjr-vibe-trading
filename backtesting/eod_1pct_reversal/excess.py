"""Same-session excess return — the test the headline numbers cannot pass on their own.

Both runs show the gated rungs earning more than the ungated control, but the stress
test shows 90% of the intraday result landing on three sessions, and the strategy
fires ~8 names at once. That is the signature of ONE market bet wearing eight tickers,
which `stock-scan-performance-audit` already paid for (5 of 7 stops died on two days).

So the question is not "did these trades make money" but "did they beat the other
stocks available the same afternoon". Subtracting the same-session control mean
removes the day effect exactly. What survives is stock selection; what vanishes was
market timing dressed up as a filter.

    uv run python -m backtesting.eod_1pct_reversal.excess
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

RUNS = os.path.join(os.path.dirname(__file__), "runs")


def excess_table(tr: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for h, sub in tr.groupby("horizon"):
        ctrl = sub[sub["rung"] == "L0_all"]
        day_mean = ctrl.groupby("date")["gross_ret"].mean()
        for rung, s in sub.groupby("rung"):
            if rung == "L0_all":
                continue
            m = s["date"].map(day_mean)
            e = (s["gross_ret"] - m).dropna()
            if e.empty:
                continue
            # Session-level too: average the daily excess, so a day with 30 trades
            # does not outvote a day with 2.
            per_day = (s.assign(ex=s["gross_ret"] - m)
                        .groupby("date")["ex"].mean().dropna())
            rows.append({
                "rung": f"{rung}|T+{h}",
                "n_trades": int(len(e)),
                "n_sessions": int(len(per_day)),
                "raw_bps": round(float(s["gross_ret"].mean()) * 10000, 2),
                "control_bps": round(float(ctrl["gross_ret"].mean()) * 10000, 2),
                "excess_bps": round(float(e.mean()) * 10000, 2),
                "excess_t": round(float(e.mean() / (e.std(ddof=1) / np.sqrt(len(e)))), 2)
                if len(e) > 2 and e.std(ddof=1) > 0 else np.nan,
                "excess_bps_by_session": round(float(per_day.mean()) * 10000, 2),
                "excess_t_by_session": round(
                    float(per_day.mean() / (per_day.std(ddof=1) / np.sqrt(len(per_day)))), 2)
                if len(per_day) > 2 and per_day.std(ddof=1) > 0 else np.nan,
                "pct_sessions_positive": round(float((per_day > 0).mean()), 3),
            })
    return pd.DataFrame(rows)


def main() -> None:
    path = os.path.join(RUNS, "intraday_trades.csv")
    tr = pd.read_csv(path, parse_dates=["date"])
    out = excess_table(tr)
    out.to_csv(os.path.join(RUNS, "intraday_excess.csv"), index=False)
    print(out.to_string(index=False))
    print("\nexcess_t_by_session is the honest one: it weights each afternoon once,")
    print("so a single day with 8 correlated winners counts as one observation.")


if __name__ == "__main__":
    main()
