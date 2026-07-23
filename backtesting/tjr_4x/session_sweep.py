"""Compare session-gating presets on the SAME candidate setups.

Isolation: `find_trades` runs once to produce all candidate setups, then
each session preset filters those candidates by entry time and the engine
re-derives position overlaps + metrics. Any metric change is attributable
purely to session gating.

Uses the cached 5m CSV in .cache/ if present (no re-fetch). Run:
    python3 -m backtesting.tjr_4x.session_sweep
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from .config import Config
from .strategy import find_trades
from .engine import backtest
from .sessions import PRESETS, filter_by_session

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")


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
    trades = find_trades(df5m, cfg)
    print(f"loaded {len(df5m):,} bars; {len(trades)} candidate setups\n")

    header = f"{'preset':<14}{'trades':>7}{'win%':>8}{'exp_R':>9}{'PF':>7}{'net_R':>9}{'maxDD_R':>9}"
    print(header)
    print("-" * len(header))
    rows = []
    for name, windows in PRESETS.items():
        filt = filter_by_session(trades, windows)
        res = backtest(df5m, filt, cfg)
        rows.append({
            "preset": name, "windows_utc": windows, "trades": res.trade_count,
            "win_rate": res.win_rate, "avg_R": res.avg_R,
            "profit_factor": res.profit_factor, "net_return_R": res.net_return_R,
            "max_drawdown_R": res.max_drawdown_R,
        })
        pf = res.profit_factor if res.profit_factor != float("inf") else 999
        print(f"{name:<14}{res.trade_count:>7}{res.win_rate*100:>7.1f}%"
              f"{res.avg_R:>9.3f}{pf:>7.2f}{res.net_return_R:>9.1f}{res.max_drawdown_R:>9.1f}")

    out_dir = os.path.join(os.path.dirname(__file__), "runs")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "session_sweep.json")
    with open(out, "w") as f:
        json.dump(rows, f, indent=2, default=str)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
