"""Daily-bias engine ablation on the SAME candidate setups.

Isolation: ``find_trades`` runs ONCE with ``apply_bias_filter=False`` to
produce ALL directional candidates (both long & short). Each bias mode then
filters those candidates to the ones whose direction matches the bias in
force at the candidate's ``confirm_time``; the engine re-derives position
overlaps + metrics. Any metric change is attributable purely to the bias
engine.

Uses the cached 5m CSV in .cache/ if present (no re-fetch). Run:
    python3 -m backtesting.tjr_4x.bias_sweep
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from .config import Config
from .strategy import find_trades, _bias_at
from .engine import backtest
from .bias import compute_bias_modes

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")

_MODES = ["current", "A", "B", "C", "A+4h", "B+4h", "C+4h"]


def _load_5m(cfg: Config, months: int = 18) -> pd.DataFrame:
    csvs = sorted(glob.glob(os.path.join(_CACHE, "*_5m_*.csv")))
    if csvs:
        df = pd.read_csv(csvs[-1], index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        return df.sort_index()
    from .data import fetch_ohlcv  # network only if no cache
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=30 * months)
    return fetch_ohlcv(cfg.symbol, cfg.base_timeframe, since, until)


def main() -> None:
    cfg = Config()
    df5m = _load_5m(cfg)

    # ALL directional candidates, detected once (no bias filter).
    cand = find_trades(df5m, Config(apply_bias_filter=False))
    modes = compute_bias_modes(df5m, cfg)
    print(f"loaded {len(df5m):,} bars; {len(cand)} directional candidates\n")

    header = (f"{'mode':<10}{'trades':>7}{'win%':>8}{'exp_R':>9}"
              f"{'PF':>7}{'net_R':>9}{'maxDD_R':>9}")
    print(header)
    print("-" * len(header))
    rows = []
    for name in _MODES:
        series = modes[name]
        filt = [t for t in cand if _bias_at(series, t.confirm_time) == t.direction]
        res = backtest(df5m, filt, cfg)
        rows.append({
            "mode": name, "trades": res.trade_count, "win_rate": res.win_rate,
            "avg_R": res.avg_R, "profit_factor": res.profit_factor,
            "net_return_R": res.net_return_R, "max_drawdown_R": res.max_drawdown_R,
        })
        pf = res.profit_factor if res.profit_factor != float("inf") else 999
        print(f"{name:<10}{res.trade_count:>7}{res.win_rate*100:>7.1f}%"
              f"{res.avg_R:>9.3f}{pf:>7.2f}{res.net_return_R:>9.1f}"
              f"{res.max_drawdown_R:>9.1f}")

    out_dir = os.path.join(os.path.dirname(__file__), "runs")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "bias_sweep.json")
    with open(out, "w") as f:
        json.dump(rows, f, indent=2, default=str)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
