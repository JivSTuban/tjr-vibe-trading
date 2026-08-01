"""Backtest DRIVER for the value+quality+drawdown strategy.

Wires the tested modules (fundamentals, signals, strategy, metrics, edgar,
prices) into a monthly, point-in-time long-only backtest and runs it against
three benchmarks (SPY, cheap-only, equal-weight universe), a drop-threshold
sweep, sub-period slices, a survivorship stress test, and a concentration
attribution.

Everything under __main__ touches the network (SEC EDGAR + Yahoo/Stooq) and is
BOUNDED: it fetches a small hardcoded validation universe into .cache/ (respecting
the fetchers' built-in rate limits), then runs a shorter window to prove the
pipeline. Caches and runs/ are gitignored — this file is the only committed
artifact.

Point-in-time discipline is inherited from the modules: pit_finyears uses only
facts with filed<=asof, drop_trigger uses only bars strictly before asof, and
median_dollar_volume uses only bars <= asof. The loop realizes each held book's
NEXT-month return (no look-ahead in the return leg).
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

from backtesting.value_quality.edgar import (
    fetch_company_facts,
    load_ticker_cik_map,
    pit_finyears,
)
from backtesting.value_quality.fundamentals import piotroski_fscore, valuation
from backtesting.value_quality.metrics import PortfolioResult, metrics_from_returns
from backtesting.value_quality.prices import (
    fetch_prices,
    load_prices,
    median_dollar_volume,
    passes_universe,
)
from backtesting.value_quality.signals import drop_trigger, value_composite
from backtesting.value_quality.strategy import ValueQualityCfg, select_holdings

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")
_TXN_COST_BPS = 15.0  # 15 bps per side, applied to turnover each rebalance

# --- VALIDATION STUB -------------------------------------------------------
# A small, well-known large-cap universe for the FIRST pipeline validation.
# The coarse SECTOR_STUB is a placeholder to be replaced by a real mapping
# (SEC SIC code or a sector data source) before any production run. It exists
# only so value_composite has a sector to rank within.
VALIDATION_UNIVERSE = [
    "AAPL", "MSFT", "JPM", "XOM", "KO", "PG", "JNJ", "WMT", "CVX", "PFE",
    "INTC", "CSCO", "IBM", "GE", "F", "BAC", "T", "VZ", "MRK", "DIS",
]
SECTOR_STUB = {  # STUB — replace with real SIC/sector mapping later
    "AAPL": "Tech", "MSFT": "Tech", "INTC": "Tech", "CSCO": "Tech", "IBM": "Tech",
    "JPM": "Financials", "BAC": "Financials",
    "XOM": "Energy", "CVX": "Energy",
    "KO": "Staples", "PG": "Staples", "WMT": "Staples",
    "JNJ": "Health", "PFE": "Health", "MRK": "Health",
    "GE": "Industrials", "F": "Industrials",
    "T": "Comm", "VZ": "Comm", "DIS": "Comm",
}
# ---------------------------------------------------------------------------


# ===========================================================================
# Panel building (cached-only — no network; run-path fetches happen in __main__)
# ===========================================================================

def _load_panel(universe: list[str], sectors: dict[str, str]) -> dict:
    """Load cached facts + prices for the universe. Skip any name lacking either.

    Returns {ticker: {"facts": dict, "prices_df": DataFrame, "sector": str}}.
    """
    cikmap = load_ticker_cik_map()
    lut = {r.ticker: int(r.cik) for r in cikmap.itertuples()}
    panel: dict[str, dict] = {}
    for t in universe:
        cik = lut.get(t)
        if cik is None:
            continue
        facts = fetch_company_facts(str(cik), use_cache=True)
        if facts is None:
            continue
        try:
            close = load_prices(t)
        except FileNotFoundError:
            continue
        if close.empty:
            continue
        # reconstruct a close/volume df for median_dollar_volume; volume lives
        # in the cached CSV, so re-read it directly.
        cpath = os.path.join(_CACHE, "prices", f"{t}.csv")
        pdf = pd.read_csv(cpath, index_col=0, parse_dates=True)
        if pdf.index.tzinfo is None:
            pdf.index = pdf.index.tz_localize("UTC")
        panel[t] = {"facts": facts, "prices_df": pdf, "sector": sectors.get(t, "Unknown")}
    return panel


def _month_ends(start, end) -> list[pd.Timestamp]:
    idx = pd.date_range(start=start, end=end, freq="ME", tz="UTC")
    return list(idx)


def _price_before(close: pd.Series, asof: pd.Timestamp) -> Optional[float]:
    prior = close[close.index < asof]
    if prior.empty:
        return None
    return float(prior.iloc[-1])


def _forward_return(close: pd.Series, asof: pd.Timestamp, nxt: pd.Timestamp) -> Optional[float]:
    """Return over (asof, nxt]: last bar <=nxt vs last bar <asof (entry price)."""
    entry = _price_before(close, asof)
    if entry is None or entry <= 0:
        return None
    fwd = close[close.index <= nxt]
    if fwd.empty:
        return None
    exit_px = float(fwd.iloc[-1])
    return exit_px / entry - 1.0


# ===========================================================================
# Core cross-section builder for a single rebalance date
# ===========================================================================

def _cross_section(panel: dict, asof: pd.Timestamp, cfg: ValueQualityCfg) -> tuple[pd.DataFrame, int, int]:
    """Build the candidate frame at `asof`.

    Returns (candidates, n_usable_facts, n_passing_universe) where candidates is
    indexed by ticker with columns [ep,bp,ebitda_ev,fcf_yield,sector,fscore,
    drop_fired,value_score]. coverage% = n_usable_facts / n_passing_universe.
    """
    recs = []
    n_usable = 0
    n_univ = 0
    for t, blk in panel.items():
        facts = blk["facts"]
        close = blk["prices_df"]["close"]
        pit = pit_finyears(facts, asof)
        if pit is None:
            continue
        cur, prev = pit
        price = _price_before(close, asof)
        if price is None:
            continue
        if not cur.shares or math.isnan(cur.shares) or cur.shares <= 0:
            continue
        mktcap = price * cur.shares
        dvol = median_dollar_volume(blk["prices_df"], asof)
        passes = passes_universe(price, mktcap, dvol)
        if passes:
            n_univ += 1
        n_usable += 1  # has usable facts (pit + price)
        val = valuation(cur, price)
        fscore = piotroski_fscore(cur, prev)
        fired = drop_trigger(close, asof, cfg.drop_threshold, cfg.drop_lookback)
        if not passes:
            continue
        recs.append({
            "ticker": t,
            "ep": val["ep"], "bp": val["bp"],
            "ebitda_ev": val["ebitda_ev"], "fcf_yield": val["fcf_yield"],
            "sector": blk["sector"], "fscore": fscore, "drop_fired": bool(fired),
        })
    if not recs:
        return pd.DataFrame(), n_usable, n_univ
    df = pd.DataFrame(recs).set_index("ticker")
    df["value_score"] = value_composite(df[["ep", "bp", "ebitda_ev", "fcf_yield", "sector"]])
    return df, n_usable, n_univ


def _cheap_only(candidates: pd.DataFrame, cfg: ValueQualityCfg) -> list[str]:
    """Value gate only — no quality, no drop trigger."""
    if candidates.empty:
        return []
    cutoff = candidates["value_score"].quantile(1.0 - cfg.value_top_frac, interpolation="lower")
    picked = candidates[candidates["value_score"] >= cutoff].sort_values("value_score", ascending=False)
    return list(picked.index[: cfg.max_names])


# ===========================================================================
# Monthly loop → return series
# ===========================================================================

def _book_return(panel: dict, holdings: list[str], asof, nxt,
                 stress_final: Optional[dict] = None) -> tuple[float, list[str]]:
    """Equal-weight next-month return of a book. Names with no forward price are
    dropped from the average (base) — unless stress_final marks them, in which
    case they realize -50% in this (their final) month (pessimistic survivorship).
    Returns (return, list-of-names-that-actually-contributed)."""
    if not holdings:
        return 0.0, []
    rets = []
    used = []
    for t in holdings:
        blk = panel.get(t)
        if blk is None:
            continue
        r = _forward_return(blk["prices_df"]["close"], asof, nxt)
        if r is None:
            if stress_final is not None and t in stress_final:
                rets.append(-0.50)
                used.append(t)
            continue
        rets.append(r)
        used.append(t)
    if not rets:
        return 0.0, []
    return float(sum(rets) / len(rets)), used


def _turnover_cost(prev_book: list[str], book: list[str]) -> float:
    """Two-sided turnover cost in return units. Equal-weight books: fraction of
    the book that changed * 2 sides * cost/side. A full replacement of an N-name
    book = 100% turnover both out and in."""
    ps, bs = set(prev_book), set(book)
    if not bs and not ps:
        return 0.0
    # fraction of new book that is freshly bought + fraction of old book sold,
    # normalized by book size; equal-weight => weight per name = 1/len(book).
    bought = len(bs - ps)
    sold = len(ps - bs)
    denom = max(len(bs), 1)
    turnover_frac = (bought + sold) / (2 * denom)  # 0..1 round-trip fraction
    return turnover_frac * 2.0 * (_TXN_COST_BPS / 1e4)


def run_backtest(cfg: ValueQualityCfg, start, end,
                 universe: Optional[list[str]] = None,
                 sectors: Optional[dict[str, str]] = None) -> dict:
    """Run the full monthly backtest and analysis. Returns the results dict and
    writes runs/<ts>/results.json."""
    universe = universe or VALIDATION_UNIVERSE
    sectors = sectors or SECTOR_STUB
    panel = _load_panel(universe, sectors)

    months = _month_ends(start, end)
    strat_rets, cheap_rets, ew_rets = {}, {}, {}
    coverages = []
    # per-name P&L attribution accumulators (strategy leg, net of cost)
    name_pnl: dict[str, float] = {}
    sector_pnl: dict[str, float] = {}
    strat_books: dict[pd.Timestamp, list[str]] = {}
    prev_strat: list[str] = []
    prev_cheap: list[str] = []

    for i in range(len(months) - 1):
        asof, nxt = months[i], months[i + 1]
        cand, n_usable, n_univ = _cross_section(panel, asof, cfg)
        if n_univ > 0:
            coverages.append(n_usable / n_univ)
        strat = select_holdings(cand, cfg) if not cand.empty else []
        cheap = _cheap_only(cand, cfg) if not cand.empty else []
        strat_books[asof] = strat

        s_ret, s_used = _book_return(panel, strat, asof, nxt)
        c_ret, _ = _book_return(panel, cheap, asof, nxt)
        # equal-weight universe: every panel name with a forward return
        ew_ret, _ = _book_return(panel, list(panel.keys()), asof, nxt)

        s_cost = _turnover_cost(prev_strat, strat)
        c_cost = _turnover_cost(prev_cheap, cheap)
        prev_strat, prev_cheap = strat, cheap

        strat_rets[nxt] = s_ret - s_cost
        cheap_rets[nxt] = c_ret - c_cost
        ew_rets[nxt] = ew_ret

        # attribute this month's net strategy P&L to contributing names/sectors
        if s_used:
            per_name = (s_ret - s_cost) / len(s_used)
            for t in s_used:
                name_pnl[t] = name_pnl.get(t, 0.0) + per_name
                sec = sectors.get(t, "Unknown")
                sector_pnl[sec] = sector_pnl.get(sec, 0.0) + per_name

    strat_sr = pd.Series(strat_rets).sort_index()
    cheap_sr = pd.Series(cheap_rets).sort_index()
    ew_sr = pd.Series(ew_rets).sort_index()

    strat_res = metrics_from_returns(strat_sr)
    cheap_res = metrics_from_returns(cheap_sr)
    ew_res = metrics_from_returns(ew_sr)

    # --- SPY benchmark ----------------------------------------------------
    spy_sr = _benchmark_monthly("SPY", months)
    spy_res = metrics_from_returns(spy_sr)

    # --- Drop-threshold sweep --------------------------------------------
    sweep = {}
    for thr in (0.85, 0.75, 0.65, 0.50):
        c2 = ValueQualityCfg(f_min=cfg.f_min, value_top_frac=cfg.value_top_frac,
                             drop_threshold=thr, drop_lookback=cfg.drop_lookback,
                             max_names=cfg.max_names, max_hold_months=cfg.max_hold_months)
        sr = _strategy_only_returns(panel, months, c2, sectors)
        sweep[f"{thr:.2f}"] = _res_dict(metrics_from_returns(sr))

    # --- Sub-periods ------------------------------------------------------
    subperiods = {}
    for label, lo, hi in (("2009-2013", "2009-01-01", "2013-12-31"),
                          ("2014-2019", "2014-01-01", "2019-12-31"),
                          ("2020-now", "2020-01-01", "2100-01-01")):
        lo_t = pd.Timestamp(lo, tz="UTC")
        hi_t = pd.Timestamp(hi, tz="UTC")
        seg = strat_sr[(strat_sr.index >= lo_t) & (strat_sr.index <= hi_t)]
        subperiods[label] = _res_dict(metrics_from_returns(seg)) if len(seg) else _res_dict(PortfolioResult())

    # --- Survivorship stress ---------------------------------------------
    survivorship = _survivorship(panel, months, cfg, sectors, universe, strat_res)

    # --- Concentration ----------------------------------------------------
    concentration = _concentration(name_pnl, sector_pnl, strat_res.total_return)

    coverage_pct = float(sum(coverages) / len(coverages)) if coverages else 0.0

    results = {
        "strategy": _res_dict(strat_res),
        "spy": _res_dict(spy_res),
        "cheap_only": _res_dict(cheap_res),
        "ew_universe": _res_dict(ew_res),
        "subperiods": subperiods,
        "coverage_pct": coverage_pct,
        "concentration": concentration,
        "monthly_returns": {
            "strategy": {str(k.date()): v for k, v in strat_sr.items()},
            "cheap_only": {str(k.date()): v for k, v in cheap_sr.items()},
            "ew_universe": {str(k.date()): v for k, v in ew_sr.items()},
            "spy": {str(k.date()): v for k, v in spy_sr.items()},
        },
        "sweep": sweep,
        "survivorship": survivorship,
        "meta": {
            "universe_size": len(universe),
            "panel_size": len(panel),
            "start": str(start), "end": str(end),
            "txn_cost_bps_per_side": _TXN_COST_BPS,
            "n_rebalances": len(months) - 1,
            "sector_source": "STUB (hardcoded validation mapping)",
        },
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = os.path.join(os.path.dirname(__file__), "runs", ts)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "results.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)
    results["_outdir"] = outdir
    return results


# ===========================================================================
# Helpers used by the analyses above
# ===========================================================================

def _res_dict(r: PortfolioResult) -> dict:
    return {"cagr": r.cagr, "sharpe": r.sharpe, "max_drawdown": r.max_drawdown,
            "total_return": r.total_return, "n_periods": r.n_periods, "ann_vol": r.ann_vol}


def _benchmark_monthly(ticker: str, months: list[pd.Timestamp]) -> pd.Series:
    """Monthly returns for a single ticker from cached prices."""
    try:
        close = load_prices(ticker)
    except FileNotFoundError:
        return pd.Series(dtype=float)
    out = {}
    for i in range(len(months) - 1):
        asof, nxt = months[i], months[i + 1]
        r = _forward_return(close, asof, nxt)
        if r is not None:
            out[nxt] = r
    return pd.Series(out).sort_index()


def _strategy_only_returns(panel: dict, months, cfg: ValueQualityCfg, sectors) -> pd.Series:
    """Just the strategy leg's net monthly returns (used by the sweep)."""
    out = {}
    prev: list[str] = []
    for i in range(len(months) - 1):
        asof, nxt = months[i], months[i + 1]
        cand, _, _ = _cross_section(panel, asof, cfg)
        book = select_holdings(cand, cfg) if not cand.empty else []
        r, _ = _book_return(panel, book, asof, nxt)
        cost = _turnover_cost(prev, book)
        prev = book
        out[nxt] = r - cost
    return pd.Series(out).sort_index()


def _survivorship(panel, months, cfg, sectors, universe, base_res) -> dict:
    """Base vs pessimistic-stress strategy metrics + missing-price census."""
    missing_path = os.path.join(_CACHE, "missing_prices.txt")
    missing = []
    if os.path.exists(missing_path):
        with open(missing_path) as f:
            missing = [ln.strip() for ln in f if ln.strip()]
    missing_set = set(missing)

    # names held at some point that later lose all price data → mark for -50%
    # in their final available month. In this validation panel every held name
    # has cached prices, so stress mainly bites names in missing_prices.txt that
    # were also in the universe.
    stress_final = {t: True for t in universe if t in missing_set}

    out = {}
    prev: list[str] = []
    for i in range(len(months) - 1):
        asof, nxt = months[i], months[i + 1]
        cand, _, _ = _cross_section(panel, asof, cfg)
        book = select_holdings(cand, cfg) if not cand.empty else []
        r, _ = _book_return(panel, book, asof, nxt, stress_final=stress_final)
        cost = _turnover_cost(prev, book)
        prev = book
        out[nxt] = r - cost
    stressed = metrics_from_returns(pd.Series(out).sort_index())

    return {
        "universe_size": len(universe),
        "missing_prices_count": len(missing_set),
        "missing_tickers": sorted(missing_set),
        "base": _res_dict(base_res),
        "stressed": _res_dict(stressed),
    }


def _concentration(name_pnl: dict, sector_pnl: dict, total_return: float) -> dict:
    def top(d):
        if not d:
            return (None, 0.0)
        k = max(d, key=lambda x: d[x])
        return (k, d[k])
    tn, tnv = top(name_pnl)
    ts, tsv = top(sector_pnl)
    total = sum(name_pnl.values())
    name_share = (tnv / total) if total not in (0, 0.0) else 0.0
    sector_share = (tsv / total) if total not in (0, 0.0) else 0.0
    return {
        "top_name": tn, "top_name_contrib": tnv, "top_name_share": name_share,
        "top_sector": ts, "top_sector_contrib": tsv, "top_sector_share": sector_share,
        "single_name_over_50pct": bool(name_share > 0.5),
        "sum_of_monthly_name_pnl": total,
    }


# ===========================================================================
# NETWORK: fetch the validation universe into .cache/ (bounded, one-off)
# ===========================================================================

def fetch_universe(universe: list[str], start, end) -> None:
    """One-off: download company_tickers.json, then companyfacts + prices for
    the validation universe (plus SPY). Respects the fetchers' built-in sleeps/
    retries. Safe to re-run — everything is cached."""
    os.makedirs(_CACHE, exist_ok=True)
    ct_path = os.path.join(_CACHE, "company_tickers.json")
    if not os.path.exists(ct_path):
        print("Downloading company_tickers.json ...")
        ua = {"User-Agent": "vibe-trading research jivtuban14@gmail.com"}
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers=ua, timeout=30)
        r.raise_for_status()
        with open(ct_path, "w") as f:
            f.write(r.text)

    cikmap = load_ticker_cik_map()
    lut = {r.ticker: int(r.cik) for r in cikmap.itertuples()}

    # prices: universe + SPY benchmark
    for t in universe + ["SPY"]:
        print(f"  prices {t} ...", end=" ")
        df = fetch_prices(t, start, end, use_cache=True)
        print("ok" if df is not None else "MISSING")

    # companyfacts for universe (SPY is an ETF — no companyfacts)
    for t in universe:
        cik = lut.get(t)
        if cik is None:
            print(f"  facts {t}: no CIK in map")
            continue
        print(f"  facts {t} (CIK {cik}) ...", end=" ")
        facts = fetch_company_facts(str(cik), use_cache=True)
        print("ok" if facts is not None else "MISSING")


if __name__ == "__main__":
    # FIRST validation run: small universe, shorter window (2015–2020).
    START = pd.Timestamp("2014-06-01", tz="UTC")  # buffer for lookback/prev-year
    END = pd.Timestamp("2020-12-31", tz="UTC")
    RUN_START = pd.Timestamp("2015-01-01", tz="UTC")

    print("=== Fetching validation universe (bounded) ===")
    fetch_universe(VALIDATION_UNIVERSE, START, END)

    print("\n=== Running backtest 2015-01 → 2020-12 ===")
    cfg = ValueQualityCfg()
    res = run_backtest(cfg, RUN_START, END)

    def fmt(d):
        return (f"CAGR={d['cagr']*100:6.2f}%  Sharpe={d['sharpe']:5.2f}  "
                f"MaxDD={d['max_drawdown']*100:6.2f}%  TotRet={d['total_return']*100:7.2f}%  "
                f"n={d['n_periods']}")

    print(f"\nwrote {res['_outdir']}/results.json")
    print(f"panel_size = {res['meta']['panel_size']} / {res['meta']['universe_size']}")
    print(f"coverage%  = {res['coverage_pct']*100:.1f}%")
    print("-" * 78)
    print(f"strategy   : {fmt(res['strategy'])}")
    print(f"cheap_only : {fmt(res['cheap_only'])}")
    print(f"SPY        : {fmt(res['spy'])}")
    print(f"ew_universe: {fmt(res['ew_universe'])}")
    print("-" * 78)
    c = res["concentration"]
    print(f"top name   : {c['top_name']} share={c['top_name_share']*100:.1f}% "
          f"(>{50}%? {c['single_name_over_50pct']})")
    print(f"top sector : {c['top_sector']} share={c['top_sector_share']*100:.1f}%")
    s = res["survivorship"]
    print(f"survivorship: missing={s['missing_prices_count']}/{s['universe_size']}  "
          f"base CAGR={s['base']['cagr']*100:.2f}%  stressed CAGR={s['stressed']['cagr']*100:.2f}%")
