"""Equity-curve portfolio metrics: CAGR, annualized Sharpe/vol, max drawdown."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

_MONTHS = 12


@dataclass
class PortfolioResult:
    cagr: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    total_return: float = 0.0
    n_periods: int = 0
    ann_vol: float = 0.0


def equity_curve(monthly_returns: pd.Series) -> pd.Series:
    return (1.0 + monthly_returns.fillna(0.0)).cumprod()


def metrics_from_returns(monthly_returns: pd.Series, rf_annual: float = 0.0) -> PortfolioResult:
    r = monthly_returns.dropna()
    n = len(r)
    if n == 0:
        return PortfolioResult()
    ec = (1.0 + r).cumprod()
    total = ec.iloc[-1] - 1.0
    years = n / _MONTHS
    cagr = (ec.iloc[-1]) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    vol = r.std(ddof=1)
    ann_vol = vol * np.sqrt(_MONTHS) if n > 1 else 0.0
    rf_m = rf_annual / _MONTHS
    sharpe = ((r.mean() - rf_m) / vol * np.sqrt(_MONTHS)) if (n > 1 and vol > 0) else 0.0
    peak = ec.cummax()
    max_dd = (ec / peak - 1.0).min()
    return PortfolioResult(cagr=float(cagr), sharpe=float(sharpe),
                           max_drawdown=float(max_dd), total_return=float(total),
                           n_periods=n, ann_vol=float(ann_vol))
