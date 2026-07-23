"""CLI runner for the TJR 4X backtest.

Loads (or fetches) a bounded window of 5m OHLCV, runs find_trades ->
backtest, prints a metrics table, and writes results.json + trades.csv
to a timestamped run directory. The network fetch is guarded behind
``if __name__ == '__main__'`` so importing this module is side-effect
free.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pandas as pd

from .config import Config
from .strategy import find_trades
from .engine import backtest


def run_backtest(df5m: pd.DataFrame, cfg: Config):
    trades = find_trades(df5m, cfg)
    result = backtest(df5m, trades, cfg)
    return trades, result


def _print_metrics(result) -> None:
    m = result.summary_dict()
    width = max(len(k) for k in m)
    print("\n=== TJR 4X backtest metrics ===")
    for k, v in m.items():
        if isinstance(v, float):
            print(f"{k:<{width}} : {v:,.4f}")
        else:
            print(f"{k:<{width}} : {v}")


def _write_outputs(run_dir: str, cfg: Config, result) -> None:
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "results.json"), "w") as f:
        json.dump({"config": asdict(cfg), "metrics": result.summary_dict()},
                  f, indent=2, default=str)
    result.to_csv(os.path.join(run_dir, "trades.csv"))
    print(f"\nwrote results.json + trades.csv to {run_dir}")


def main() -> None:
    p = argparse.ArgumentParser(description="Run the TJR 4X backtest.")
    p.add_argument("--months", type=int, default=18,
                   help="lookback window in months (default 18)")
    p.add_argument("--symbol", default=Config.symbol)
    p.add_argument("--out", default=None, help="run output dir")
    args = p.parse_args()

    from .data import fetch_ohlcv  # local import keeps network out of import

    cfg = Config(symbol=args.symbol)
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=30 * args.months)
    print(f"fetching {cfg.symbol} {cfg.base_timeframe} "
          f"{since.date()} -> {until.date()} ...")
    df5m = fetch_ohlcv(cfg.symbol, cfg.base_timeframe, since, until)
    print(f"loaded {len(df5m):,} bars")

    trades, result = run_backtest(df5m, cfg)
    _print_metrics(result)

    run_dir = args.out or os.path.join(
        os.path.dirname(__file__), "runs",
        datetime.now().strftime("%Y%m%d_%H%M%S"))
    _write_outputs(run_dir, cfg, result)


if __name__ == "__main__":
    main()
