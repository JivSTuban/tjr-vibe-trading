r"""Causality + catalyst overlay: is this selloff PRESSURE or INFORMATION?

Motivation. The base backtest's sharpest result is that the spec's signature filter is
backwards: demanding abnormal late volume COSTS 2.19 bps. The reading is that heavy
late volume marks *information*, and information does not reverse overnight. The spec
itself anticipates the fix in §16 ("news/event classification to distinguish temporary
pressure from new information"; "beta-adjusted market/sector residual returns"). This
module implements that distinction and tests it.

The decomposition. For each (stock, date) we split the day's move into two parts using
a beta fitted ONLY on data before the signal day:

    day_ret  =  alpha + beta * theme_ret  +  residual
                \________ common ________/   \_ idiosyncratic _/

  - COMMON = the stock fell because its whole demand chain fell. Nothing was learned
    about the company. This is flow/pressure and is the part the hypothesis says
    should snap back.
  - RESIDUAL = the stock fell while its chain held up. Something was learned about
    THIS company. Information does not un-happen overnight.

The look-ahead trap, and how this avoids it.

  Knowing in 2026 that "AI" is the dominant theme — and that MRAM, rare earths,
  copper, uranium and power are its supply chain — is hindsight. Hard-coding that
  basket back to 2014 would manufacture an edge out of knowledge we did not have, the
  single most common way a thematic backtest lies.

  So no theme is ever named or dated here. Instead:
    1. Themes are REAL, TRADABLE ETFs that existed at the time, each gated by its own
       inception date (`THEME_ETFS`).
    2. A stock is assigned to a theme by trailing return CORRELATION over a window
       ending before the signal day — the data says Everspin trades with semis, we
       never assert it.
    3. Whether a theme is "in demand" is trailing relative strength vs SPY, again
       computed only from data <= t.

  "AI demand lifted memory, minerals, rare earths and power" therefore becomes a
  PREDICTION this module can confirm or refute, not an assumption it is built on: if
  the thesis holds, those baskets should show tailwind in 2023-2026 without anyone
  telling the code so, and dips inside a tailwind theme should reverse better.

Network is touched only by `fetch_theme_prices`. Everything else is pure.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from . import prices

# Real ETFs, each with its true inception. A theme is invisible to the model before
# its ETF existed, which is what keeps the basket point-in-time.
THEME_ETFS: dict[str, str] = {
    "SMH": "2000-06-05",    # semiconductors  (the compute layer)
    "SOXX": "2001-07-13",   # semiconductors  (alternate construction)
    "IGV": "2001-07-13",    # software
    "XME": "2006-06-22",    # metals & mining (the materials layer)
    "COPX": "2009-04-20",   # copper miners
    "REMX": "2010-10-27",   # rare earth / strategic metals
    "URA": "2010-11-05",    # uranium
    "XLE": "1998-12-22",    # energy
    "XLU": "1998-12-22",    # utilities      (the power layer)
    "ITA": "2006-05-05",    # aerospace & defense
    "IYT": "2003-10-06",    # transports
    "XBI": "2006-02-06",    # biotech
    "KRE": "2006-06-19",    # regional banks
    "XHB": "2006-02-06",    # homebuilders
    "XRT": "2006-06-22",    # retail
}

CORR_WINDOW = 120      # sessions used to decide which theme a stock belongs to
BETA_WINDOW = 60       # sessions used to fit the common/idiosyncratic split
STRENGTH_WINDOW = 60   # sessions used to judge whether a theme is in demand
MIN_ABS_CORR = 0.30    # below this the stock has no coherent theme at all


def fetch_theme_prices(start: str, end: str, fmp_key: Optional[str] = None,
                       use_cache: bool = True) -> dict[str, pd.DataFrame]:
    """Daily bars for every theme ETF. Missing ones are simply absent downstream."""
    frames, _ = prices.load_panel(list(THEME_ETFS), start, end,
                                  fmp_key=fmp_key, use_cache=use_cache)
    return frames


def theme_returns(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Pure: daily simple returns per theme, NaN before each ETF's inception.

    The inception mask matters: Yahoo occasionally serves a few pre-inception rows for
    an ETF, and a theme that "existed" before it traded would be look-ahead.
    """
    cols = {}
    for etf, df in frames.items():
        r = df["close"].pct_change()
        start = pd.Timestamp(THEME_ETFS.get(etf, "1900-01-01"))
        cols[etf] = r.where(r.index >= start)
    return pd.DataFrame(cols).sort_index()


def assign_theme(stock_ret: pd.Series, themes: pd.DataFrame,
                 window: int = CORR_WINDOW, step: int = 21,
                 min_abs_corr: float = MIN_ABS_CORR) -> pd.Series:
    """Pure: point-in-time theme label per session, re-decided about monthly.

    At each rebalance date we correlate the stock's trailing ``window`` returns with
    each theme's over the SAME window, both ending at the PREVIOUS session, and take
    the best match. The label is then held until the next rebalance, so a signal on
    day t is always scored with a theme chosen strictly before t.

    Returns a Series of theme names (NaN where no theme clears ``min_abs_corr``).
    """
    idx = stock_ret.index
    out = pd.Series(index=idx, dtype=object)
    if len(idx) < window + 2:
        return out

    aligned = themes.reindex(idx)
    for i in range(window, len(idx), step):
        lo, hi = i - window, i               # [lo, hi) — excludes session i itself
        s = stock_ret.iloc[lo:hi]
        if s.notna().sum() < window * 0.6:
            continue
        block = aligned.iloc[lo:hi]
        corr = block.corrwith(s)
        corr = corr[corr.notna()]
        if corr.empty:
            continue
        best = corr.abs().idxmax()
        if abs(corr[best]) < min_abs_corr:
            continue
        out.iloc[i:i + step] = best
    return out


def rolling_beta(stock_ret: pd.Series, theme_ret: pd.Series,
                 window: int = BETA_WINDOW) -> pd.Series:
    """Pure: rolling OLS beta of stock on theme, SHIFTED so day t uses only t-1 back.

    The shift is the whole anti-lookahead point. A beta fitted on a window that
    includes the signal day would partly explain the selloff with itself.
    """
    df = pd.concat([stock_ret.rename("s"), theme_ret.rename("t")], axis=1)
    cov = df["s"].rolling(window).cov(df["t"])
    var = df["t"].rolling(window).var()
    beta = (cov / var.replace(0.0, np.nan))
    return beta.shift(1)


def decompose(stock_ret: pd.Series, themes: pd.DataFrame, theme_label: pd.Series,
              window: int = BETA_WINDOW) -> pd.DataFrame:
    """Pure: split each session's return into common vs idiosyncratic.

    ``common_share`` is the fraction of the day's move explained by the theme. It is
    the quantity the causal question turns on:
        near 1  -> the whole chain fell, the stock was carried  (PRESSURE)
        near 0  -> the chain was fine and this name broke        (INFORMATION)
    """
    out = pd.DataFrame(index=stock_ret.index)
    out["theme"] = theme_label
    out["beta"] = np.nan
    out["theme_ret"] = np.nan

    aligned = themes.reindex(stock_ret.index)
    for etf in pd.unique(theme_label.dropna()):
        mask = (theme_label == etf).to_numpy()
        if not mask.any() or etf not in aligned:
            continue
        b = rolling_beta(stock_ret, aligned[etf], window)
        out.loc[mask, "beta"] = b[mask]
        out.loc[mask, "theme_ret"] = aligned[etf][mask]

    out["common"] = out["beta"] * out["theme_ret"]
    out["residual"] = stock_ret - out["common"]
    denom = out["common"].abs() + out["residual"].abs()
    out["common_share"] = (out["common"].abs() / denom.replace(0.0, np.nan))
    return out


def theme_strength(themes: pd.DataFrame, spy_ret: pd.Series,
                   window: int = STRENGTH_WINDOW) -> pd.DataFrame:
    """Pure: trailing relative strength of each theme vs SPY, ending at t-1.

    This is the "is this chain in demand right now" measure, and it is the piece that
    lets a demand narrative be discovered instead of assumed. Nothing here knows what
    the demand is FOR.
    """
    cum = (1.0 + themes).rolling(window).apply(np.prod, raw=True) - 1.0
    spy_cum = (1.0 + spy_ret).rolling(window).apply(np.prod, raw=True) - 1.0
    return (cum.sub(spy_cum, axis=0)).shift(1)


def label_cells(trades: pd.DataFrame, common_cut: float = 0.5,
                strength_cut: float = 0.0) -> pd.DataFrame:
    """Pure: tag each trade with the causal bucket it belongs to.

    Two binary axes, four cells:
      cause     PRESSURE (common_share >= cut)  vs  INFORMATION (below)
      demand    TAILWIND (theme beat SPY)       vs  HEADWIND
    """
    out = trades.copy()
    out["cause"] = np.where(out["common_share"] >= common_cut, "PRESSURE", "INFORMATION")
    out.loc[out["common_share"].isna(), "cause"] = np.nan
    out["demand"] = np.where(out["theme_strength"] >= strength_cut, "TAILWIND", "HEADWIND")
    out.loc[out["theme_strength"].isna(), "demand"] = np.nan
    out["cell"] = out["cause"] + " / " + out["demand"]
    return out
