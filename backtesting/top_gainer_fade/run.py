"""Run the top-gainer intraday fade over the cached 8-perp large-cap universe.

    python3 -m backtesting.top_gainer_fade.run

Reads the newest cached 5m CSV per symbol (no network), builds one fade/day
(short the single biggest gainer), and reports:
  * headline metrics (funding=0: pure price + fees)
  * cost sensitivity (gross -> fees -> fees+funding scenarios)
  * equal-count walk-forward (is any edge consistent across time?)
  * per-instrument breakdown (which coin got faded, and how it did)
Dumps runs/top_gainer_fade.json (+ trades.csv) and writes an HTML dashboard.
"""

from __future__ import annotations

import dataclasses
import glob
import json
import os
from dataclasses import replace
from typing import Dict, List

import numpy as np
import pandas as pd

from backtesting.tjr_4x.engine import metrics_from_closed
from backtesting.tjr_4x.validation import load_5m, _CACHE
from .strategy import FadeConfig, FadeTrade, find_fades
from .viz import render_html

_HERE = os.path.dirname(__file__)
_RUNS = os.path.join(_HERE, "runs")


def _symbols() -> List[str]:
    out = []
    for p in sorted(glob.glob(os.path.join(_CACHE, "*_5m_*.csv"))):
        sym = os.path.basename(p).split("_", 1)[0].upper()
        if sym not in out:
            out.append(sym)
    return out


def load_universe() -> Dict[str, pd.DataFrame]:
    frames: Dict[str, pd.DataFrame] = {}
    for sym in _symbols():
        try:
            frames[sym] = load_5m(f"*{sym}*_5m_*.csv")
        except Exception:
            continue
    return frames


def _m(closed) -> dict:
    r = metrics_from_closed(closed)
    return {
        "trades": r.trade_count, "win_rate": round(r.win_rate, 4),
        "avg_R": round(r.avg_R, 4), "profit_factor": round(r.profit_factor, 3),
        "net_return_R": round(r.net_return_R, 2),
        "max_drawdown_R": round(r.max_drawdown_R, 2),
        "max_consec_losses": r.max_consecutive_losses,
    }


def _net_ct(t: FadeTrade, cfg: FadeConfig, *, gross=False):
    """Return a copy of t.ct with net_R recomputed under cfg (or gross = price only)."""
    from .strategy import _cost_R
    ct = t.ct
    risk = abs(ct.entry - ct.sl)
    if gross:
        return dataclasses.replace(ct, net_R=ct.gross_R)
    tc = _cost_R(ct.entry, ct.exit_price, risk, cfg)
    # position funding P&L = -direction * market_rate (short earns / long pays)
    fund = (-ct.direction * cfg.funding_bps_per_interval / 10000.0
            * t.n_funding * ct.entry / risk)
    return dataclasses.replace(ct, net_R=ct.gross_R - tc + fund)


def _recost(trades: List[FadeTrade], cfg: FadeConfig, *, gross=False):
    """Rebuild net_R for each trade under a cfg variant (or gross = price only)."""
    return [_net_ct(t, cfg, gross=gross) for t in trades]


def walk_forward(trades: List[FadeTrade], cfg: FadeConfig, k: int = 6) -> List[dict]:
    closed = [_net_ct(t, cfg) for t in trades]
    if not closed:
        return []
    out = []
    for i, fold in enumerate(np.array_split(np.array(closed, dtype=object), k)):
        fold = list(fold)
        if not fold:
            out.append({"fold": i + 1, "n": 0})
            continue
        r = metrics_from_closed(fold)
        out.append({
            "fold": i + 1, "n": r.trade_count,
            "start": str(fold[0].entry_time.date()),
            "end": str(fold[-1].entry_time.date()),
            "win_rate": round(r.win_rate, 3),
            "net_avg_R": round(r.avg_R, 4),
        })
    return out


def per_instrument(trades: List[FadeTrade], cfg: FadeConfig) -> List[dict]:
    by: Dict[str, list] = {}
    for t in trades:
        by.setdefault(t.symbol, []).append(_net_ct(t, cfg))
    rows = []
    for sym, closed in by.items():
        r = metrics_from_closed(closed)
        rows.append({"symbol": sym, "faded_days": r.trade_count,
                     "win_rate": round(r.win_rate, 3),
                     "net_avg_R": round(r.avg_R, 4),
                     "net_total_R": round(r.net_return_R, 2)})
    rows.sort(key=lambda x: -x["faded_days"])
    return rows


def run_side(frames, cfg: FadeConfig) -> dict:
    """Backtest one side ('short'=fade | 'long'=ride) and package a report block."""
    trades = find_fades(frames, cfg)
    taker = replace(cfg, cost_model="taker_both")
    maker = replace(cfg, cost_model="maker_entry")
    headline = _m(_recost(trades, maker))                  # headline = best realistic exec
    gross = _m(_recost(trades, cfg, gross=True))
    # execution ladder: raw edge -> conservative taker -> maker-entry -> maker + funding stress
    scenarios = [
        ("gross (price only)", gross),
        ("net · taker entry + taker exit", _m(_recost(trades, taker))),
        ("net · MAKER entry + taker exit", _m(_recost(trades, maker))),
        ("net · maker entry + funding +5bp/8h stress",
         _m(_recost(trades, replace(maker, funding_bps_per_interval=5.0)))),
    ]
    # equity curve uses the maker-entry net (matches the headline)
    maker_closed = _recost(trades, maker)
    eq = np.cumsum([c.net_R for c in maker_closed]).tolist() if trades else []
    curve = [{"day": t.day, "sym": t.symbol, "runup": round(t.runup, 4),
              "net_R": round(maker_closed[i].net_R, 4), "cum_R": round(eq[i], 4),
              "outcome": t.ct.outcome} for i, t in enumerate(trades)]
    return {
        "side": cfg.side, "config": dataclasses.asdict(cfg),
        "headline": headline, "gross": gross, "scenarios": scenarios,
        "walk_forward": walk_forward(trades, maker), "per_instrument": per_instrument(trades, maker),
        "curve": curve, "_trades": trades,
    }


def main():
    frames = load_universe()
    short = run_side(frames, FadeConfig(side="short"))
    long_ = run_side(frames, FadeConfig(side="long"))

    report = {
        "universe": sorted(frames.keys()),
        "decision_hour": FadeConfig().decision_hour,
        "min_gain": FadeConfig().min_gain,
        "sides": {"short": {k: v for k, v in short.items() if k != "_trades"},
                  "long": {k: v for k, v in long_.items() if k != "_trades"}},
    }

    os.makedirs(_RUNS, exist_ok=True)
    with open(os.path.join(_RUNS, "top_gainer_fade.json"), "w") as f:
        json.dump(report, f, indent=2)
    for name, blk in (("short", short), ("long", long_)):
        pd.DataFrame([dataclasses.asdict(t.ct) | {"symbol": t.symbol, "runup": t.runup}
                     for t in blk["_trades"]]).to_csv(
            os.path.join(_RUNS, f"trades_{name}.csv"), index=False)

    html_path = os.path.join(_RUNS, "top_gainer_fade.html")
    render_html(report, html_path)

    print(f"Universe A / large-cap majors: {report['universe']}")
    for name, blk in (("SHORT (fade)", short), ("LONG (ride) ", long_)):
        h, g = blk["headline"], blk["gross"]
        print(f"\n{name}: {h['trades']} trades  win%: {h['win_rate']:.1%}")
        print(f"  GROSS avg_R {g['avg_R']:+.4f}  PF {g['profit_factor']}")
        print(f"  NET   avg_R {h['avg_R']:+.4f}  PF {h['profit_factor']}  "
              f"total {h['net_return_R']:+.1f}R  (maker entry)")
        for sc, m in blk["scenarios"][1:]:
            print(f"    {sc:52s} avg_R {m['avg_R']:+.4f}  net {m['net_return_R']:+.1f}R")
    print(f"\nWrote {html_path}")


if __name__ == "__main__":
    main()
