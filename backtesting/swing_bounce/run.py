"""Swing-bounce backtest driver.

Event-driven: detect beaten-down drop events across a universe, tag each with the point-in-time
"financially alive" gate, then simulate a stop/target/time trade across a sweep grid for BOTH the
gated (alive-only) and ungated (all events) legs. Reports expectancy per cell, a SPY-window
benchmark, a survivorship stress, and a concentration check.

Network is touched ONLY under ``__main__`` (fetching OHLC + EDGAR facts into caches); ``run_backtest``
reads caches only. Caches/runs are gitignored.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

import pandas as pd

from backtesting.value_quality.edgar import fetch_company_facts, load_ticker_cik_map, pit_finyears
from backtesting.swing_bounce.gate import financially_alive
from backtesting.swing_bounce.events import is_drop_event
from backtesting.swing_bounce.trade_sim import simulate_trade
from backtesting.swing_bounce.metrics import expectancy
from backtesting.swing_bounce.prices_ohlc import fetch_ohlc, load_ohlc

_HERE = os.path.dirname(__file__)
GRID_TARGETS = [0.10, 0.20, 0.30]
GRID_STOPS = [0.08, 0.10, 0.15]
GRID_HORIZONS = [10, 20, 40]
THRESHOLDS = [0.85, 0.75, 0.65]
COOLDOWN = 40                       # >= max horizon so trades on one name don't overlap
HEADLINE = (0.75, 0.20, 0.10, 20)   # (threshold, target, stop, horizon) — summary cell


def alive_at(facts, date_t) -> bool:
    if not facts:
        return False
    try:
        res = pit_finyears(facts, pd.Timestamp(date_t))
    except Exception:
        return False
    if res is None:
        return False
    return financially_alive(res[0])


def build_events(close: pd.Series, threshold: float, cooldown: int = COOLDOWN) -> list[int]:
    events, last = [], -10 ** 9
    for i in range(len(close)):
        if i - last < cooldown:
            continue
        if is_drop_event(close, i, threshold):
            events.append(i)
            last = i
    return events


def _facts_for(ticker: str, cik_map: dict):
    cik = cik_map.get(ticker.upper())
    if cik is None:
        return None
    return fetch_company_facts(str(cik), use_cache=True)


def _cell_key(leg, thr, tgt, stp, hor):
    return f"{leg}|thr{thr}|t{tgt}|s{stp}|h{hor}"


def run_backtest(universe: list[str], cik_map: dict | None = None) -> dict:
    if cik_map is None:
        m = load_ticker_cik_map()
        cik_map = {r.ticker.upper(): int(r.cik) for r in m.itertuples()}
    buckets: dict[str, list] = defaultdict(list)
    headline_trades = []           # gated headline-cell trades w/ attribution
    n_events = {"gated": 0, "ungated": 0}
    covered, total = 0, 0

    for ticker in universe:
        if ticker.upper() == "SPY":
            continue
        try:
            ohlc = load_ohlc(ticker)
        except Exception:
            continue
        close = ohlc["close"]
        facts = _facts_for(ticker, cik_map)
        total += 1
        if facts:
            covered += 1
        for thr in THRESHOLDS:
            for ei in build_events(close, thr):
                date_t = close.index[ei]
                alive = alive_at(facts, date_t)
                n_events["ungated"] += 1
                if alive:
                    n_events["gated"] += 1
                for tgt in GRID_TARGETS:
                    for stp in GRID_STOPS:
                        for hor in GRID_HORIZONS:
                            tr = simulate_trade(ohlc, ei, tgt, stp, hor)
                            if tr is None:
                                continue
                            buckets[_cell_key("ungated", thr, tgt, stp, hor)].append(tr)
                            if alive:
                                buckets[_cell_key("gated", thr, tgt, stp, hor)].append(tr)
                            if alive and (thr, tgt, stp, hor) == HEADLINE:
                                truncated = ei + hor >= len(ohlc) - 1
                                headline_trades.append({**tr, "ticker": ticker,
                                                        "year": int(date_t.year), "truncated": truncated})

    cells = {k: expectancy(v) for k, v in buckets.items()}

    # SPY-window benchmark: avg forward return over each horizon across all event dates
    spy_bench = {}
    try:
        spy = load_ohlc("SPY")["close"]
        # baseline: average hor-day forward return of SPY (unconditional "just be long" comparison)
        for hor in GRID_HORIZONS:
            fwd = (spy.shift(-hor) / spy - 1.0).dropna()
            spy_bench[f"h{hor}"] = float(fwd.mean())
    except Exception:
        spy_bench = {"error": "SPY not cached"}

    # survivorship stress: truncated (possibly delisted) gated headline trades -> assign -100%
    base = expectancy([{"outcome": t["outcome"], "net_ret": t["net_ret"], "R": t["R"]}
                       for t in headline_trades])
    stressed = expectancy([
        {"outcome": ("stop" if t["truncated"] else t["outcome"]),
         "net_ret": (-1.0 if t["truncated"] else t["net_ret"]),
         "R": ((-1.0 / HEADLINE[2]) if t["truncated"] else t["R"])}
        for t in headline_trades])

    # concentration: gated headline P&L by ticker / year
    by_ticker = defaultdict(float)
    by_year = defaultdict(float)
    for t in headline_trades:
        by_ticker[t["ticker"]] += t["net_ret"]
        by_year[t["year"]] += t["net_ret"]
    total_pnl = sum(by_ticker.values()) or 1e-9
    top_ticker = max(by_ticker.items(), key=lambda kv: abs(kv[1])) if by_ticker else ("-", 0.0)
    top_year = max(by_year.items(), key=lambda kv: abs(kv[1])) if by_year else (0, 0.0)

    return {
        "n_events": n_events,
        "coverage_pct": round(100 * covered / total, 1) if total else 0.0,
        "cells": cells,
        "headline_cell": {"threshold": HEADLINE[0], "target": HEADLINE[1],
                          "stop": HEADLINE[2], "horizon": HEADLINE[3],
                          "gated": base},
        "spy_benchmark": spy_bench,
        "survivorship": {"n_truncated": sum(1 for t in headline_trades if t["truncated"]),
                         "base": base, "stressed": stressed},
        "concentration": {"top_ticker": top_ticker[0],
                          "top_ticker_share": round(top_ticker[1] / total_pnl, 3),
                          "top_year": top_year[0],
                          "top_year_share": round(top_year[1] / total_pnl, 3)},
    }


# ---- starter universe: names that actually had big drawdowns 2015-2023 ----
UNIVERSE = ["AAPL", "MSFT", "MU", "NVDA", "META", "NFLX", "PYPL", "SQ", "ROKU", "ZM",
            "PTON", "CVNA", "INTC", "NKE", "PFE", "DIS", "F", "BAC", "T", "VZ",
            "CSCO", "XOM", "CVX", "KO", "PG", "JNJ", "WMT", "JPM", "MRK", "IBM"]


def _fetch_universe(start="2015-01-01", end="2023-12-31"):
    m = load_ticker_cik_map()
    cik_map = {r.ticker.upper(): int(r.cik) for r in m.itertuples()}
    for t in UNIVERSE + ["SPY"]:
        got = fetch_ohlc(t, start, end, use_cache=True)
        print(f"  OHLC {t}: {'ok ' + str(len(got)) + ' bars' if got is not None else 'MISSING'}")
        if t != "SPY":
            f = _facts_for(t, cik_map)
            print(f"  facts {t}: {'ok' if f else 'MISSING'}")
    return cik_map


if __name__ == "__main__":
    import datetime as _dt
    print("Fetching bounded universe (2015-2023)...")
    cik_map = _fetch_universe()
    print("Running backtest...")
    res = run_backtest(UNIVERSE, cik_map)
    ts = _dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    out = os.path.join(_HERE, "runs", ts)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "results.json"), "w") as f:
        json.dump(res, f, indent=2, default=str)
    from backtesting.swing_bounce.viz import render_dashboard
    render_dashboard(res, out)
    h = res["headline_cell"]["gated"]
    print(f"\nEvents: {res['n_events']} | coverage {res['coverage_pct']}%")
    print(f"HEADLINE gated cell (thr .75 / +20% / -10% / 20d): "
          f"n={h['n']} hit={h['hit_rate']:.0%} expectancy={h['expectancy_R']:+.3f}R")
    # gated vs ungated at headline
    ug = res["cells"].get(_cell_key("ungated", *HEADLINE))
    if ug:
        print(f"  ungated same cell: n={ug['n']} hit={ug['hit_rate']:.0%} "
              f"expectancy={ug['expectancy_R']:+.3f}R  -> gate delta "
              f"{h['expectancy_R'] - ug['expectancy_R']:+.3f}R")
    print(f"  survivorship stressed expectancy: {res['survivorship']['stressed']['expectancy_R']:+.3f}R "
          f"({res['survivorship']['n_truncated']} truncated)")
    print(f"  concentration: top name {res['concentration']['top_ticker']} "
          f"{res['concentration']['top_ticker_share']:.0%} of P&L")
    print(f"  results.json -> {out}")
