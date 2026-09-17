"""Piotroski F-score + valuation ratios from point-in-time annual line items.

Pure functions over FinYear snapshots — no I/O, no look-ahead: the caller is
responsible for passing only rows whose `filed` date is known as of the
decision date (see strategy.py). F-score per Piotroski (2000), "Value
Investing: The Use of Historical Financial Statement Information".
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import pandas as pd


@dataclass
class FinYear:
    net_income: float
    total_assets: float
    cfo: float
    revenue: float
    gross_profit: float
    cur_assets: float
    cur_liab: float
    lt_debt: float
    shares: float
    book_equity: float
    ebitda: float
    total_debt: float
    cash: float
    capex: float
    filed: pd.Timestamp


def _safe_div(a: float, b: float) -> float:
    return a / b if b not in (0, 0.0) and not math.isnan(b) else math.nan


def piotroski_fscore(cur: FinYear, prev: FinYear) -> int:
    roa = _safe_div(cur.net_income, cur.total_assets)
    roa_prev = _safe_div(prev.net_income, prev.total_assets)
    cur_ratio = _safe_div(cur.cur_assets, cur.cur_liab)
    cur_ratio_prev = _safe_div(prev.cur_assets, prev.cur_liab)
    lev = _safe_div(cur.lt_debt, cur.total_assets)
    lev_prev = _safe_div(prev.lt_debt, prev.total_assets)
    gm = _safe_div(cur.gross_profit, cur.revenue)
    gm_prev = _safe_div(prev.gross_profit, prev.revenue)
    turn = _safe_div(cur.revenue, cur.total_assets)
    turn_prev = _safe_div(prev.revenue, prev.total_assets)

    signals = [
        cur.net_income > 0,                 # 1 profitability
        cur.cfo > 0,                        # 2 positive operating cash flow
        roa > roa_prev,                     # 3 rising ROA
        cur.cfo > cur.net_income,           # 4 accruals (cash-backed earnings)
        lev < lev_prev,                     # 5 falling leverage
        cur_ratio > cur_ratio_prev,         # 6 rising liquidity
        cur.shares <= prev.shares,          # 7 no dilution
        gm > gm_prev,                       # 8 rising gross margin
        turn > turn_prev,                   # 9 rising asset turnover
    ]
    return int(sum(1 for s in signals if s is True))


def valuation(cur: FinYear, price: float) -> dict:
    mktcap = price * cur.shares
    ev = mktcap + cur.total_debt - cur.cash
    fcf = cur.cfo - cur.capex
    return {
        "ep": _safe_div(cur.net_income, mktcap),
        "bp": _safe_div(cur.book_equity, mktcap),
        "ebitda_ev": _safe_div(cur.ebitda, ev),
        "fcf_yield": _safe_div(fcf, mktcap),
    }
