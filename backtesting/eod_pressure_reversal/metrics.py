"""Spec §12 metrics, §13 regime tagging, §14 left-tail review. Pure, no network.

One deliberate choice worth stating: Sharpe/Sortino are annualised on the number of
*trading days in the sample*, not the number of trades. An overnight strategy that
holds ~14 hours a day is flat the rest of the time, and scaling by trade count would
flatter it by pretending the capital compounds every trade. §12 asks for "exposure"
precisely so this is visible.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def trade_metrics(trades: pd.DataFrame, ret_col: str = "net_ret") -> dict:
    """Pure: the §12 table for a set of trades."""
    if trades.empty:
        return {"n_trades": 0}
    r = trades[ret_col].dropna().astype(float)
    if r.empty:
        return {"n_trades": 0}
    wins, losses = r[r > 0], r[r <= 0]
    gross_win, gross_loss = wins.sum(), -losses.sum()
    return {
        "n_trades": int(r.size),
        "win_rate": float((r > 0).mean()),
        "mean_ret": float(r.mean()),
        "median_ret": float(r.median()),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "payoff": float(wins.mean() / abs(losses.mean())) if len(losses) and losses.mean() != 0 else np.nan,
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else np.inf,
        "std": float(r.std(ddof=1)) if r.size > 1 else 0.0,
        "worst": float(r.min()),
        "best": float(r.max()),
        "p01": float(r.quantile(0.01)),
        "p05": float(r.quantile(0.05)),
        "expected_value": float(r.mean()),
        "t_stat": float(r.mean() / (r.std(ddof=1) / np.sqrt(r.size))) if r.size > 1 and r.std(ddof=1) > 0 else np.nan,
    }


def portfolio_metrics(daily: pd.DataFrame, n_sessions: int | None = None) -> dict:
    """Pure: §12 portfolio-level metrics from the equal-weighted daily curve."""
    if daily.empty:
        return {"n_days": 0}
    r = daily["ret"].astype(float)
    total = float((1.0 + r).prod() - 1.0)
    span = n_sessions or int(r.size)
    years = max(span / TRADING_DAYS, 1e-9)
    downside = r[r < 0]
    curve = (1.0 + r).cumprod()
    dd = curve / curve.cummax() - 1.0
    return {
        "n_days": int(r.size),
        "exposure": float(r.size / span) if span else np.nan,
        "total_return": total,
        "cagr": float((1.0 + total) ** (1.0 / years) - 1.0) if total > -1 else -1.0,
        "sharpe": float(r.mean() / r.std(ddof=1) * np.sqrt(TRADING_DAYS)) if r.size > 1 and r.std(ddof=1) > 0 else np.nan,
        "sortino": float(r.mean() / downside.std(ddof=1) * np.sqrt(TRADING_DAYS)) if len(downside) > 1 and downside.std(ddof=1) > 0 else np.nan,
        "max_drawdown": float(dd.min()),
        "avg_positions": float(daily["n"].mean()),
    }


def tag_regimes(trades: pd.DataFrame, vix: pd.Series, spy_ret: pd.Series) -> pd.DataFrame:
    """Pure: §13 regime labels on the SIGNAL day (information available at 3:50 PM).

    VIX and SPY are taken from the signal session itself, not the exit session — using
    tomorrow's tape to bucket today's trade would be look-ahead dressed up as analysis.
    """
    out = trades.copy()
    v = vix.reindex(pd.DatetimeIndex(out["date"])).to_numpy()
    s = spy_ret.reindex(pd.DatetimeIndex(out["date"])).to_numpy()
    out["vix"] = v
    out["spy_ret"] = s
    out["vix_bucket"] = pd.cut(
        out["vix"], [-np.inf, 15, 20, 30, np.inf],
        labels=["VIX<15", "VIX 15-20", "VIX 20-30", "VIX>30"],
    )
    out["spy_bucket"] = pd.cut(
        out["spy_ret"], [-np.inf, -0.01, 0.0, np.inf],
        labels=["SPY<-1%", "SPY -1%..0%", "SPY>0%"],
    )
    return out


def regime_table(trades: pd.DataFrame, by: str, ret_col: str = "net_ret") -> pd.DataFrame:
    """Pure: per-regime §12 summary."""
    if trades.empty or by not in trades:
        return pd.DataFrame()
    rows = []
    for label, grp in trades.groupby(by, observed=True):
        m = trade_metrics(grp, ret_col)
        m[by] = str(label)
        rows.append(m)
    cols = [by, "n_trades", "win_rate", "mean_ret", "median_ret", "profit_factor", "worst"]
    df = pd.DataFrame(rows)
    return df[[c for c in cols if c in df]].sort_values(by).reset_index(drop=True)


def left_tail(trades: pd.DataFrame, ret_col: str = "net_ret", n: int = 100) -> dict:
    """Pure: §14. The distribution question — can a handful of gaps eat the wins?

    ``tail_share_of_pnl`` is the headline: if removing the worst 1% flips the strategy
    from negative to positive, the edge was never there; if removing the BEST 1% flips
    it from positive to negative, the edge is a few lottery tickets, which §17 forbids.
    """
    if trades.empty:
        return {}
    r = trades[ret_col].dropna().sort_values()
    total = float(r.sum())
    k1 = max(int(len(r) * 0.01), 1)
    k5 = max(int(len(r) * 0.05), 1)
    worst = r.head(min(n, len(r)))
    return {
        "n": int(len(r)),
        "sum_all": total,
        "worst_trade": float(r.iloc[0]),
        f"worst_{n}_sum": float(worst.sum()),
        "worst_1pct_sum": float(r.head(k1).sum()),
        "worst_5pct_sum": float(r.head(k5).sum()),
        "best_1pct_sum": float(r.tail(k1).sum()),
        "mean_ex_worst_1pct": float(r.iloc[k1:].mean()),
        "mean_ex_best_1pct": float(r.iloc[:-k1].mean()) if len(r) > k1 else np.nan,
        "tail_ratio": float(abs(r.head(k1).sum()) / r.tail(k1).sum()) if r.tail(k1).sum() > 0 else np.inf,
    }


def worst_trades(trades: pd.DataFrame, ret_col: str = "net_ret", n: int = 25) -> pd.DataFrame:
    """Pure: the §14 worklist — the individual disasters, for cause classification."""
    if trades.empty:
        return pd.DataFrame()
    cols = [c for c in ["date", "ticker", "day_ret", "rel_vol", "price", "next_open", ret_col] if c in trades]
    return trades.nsmallest(n, ret_col)[cols].reset_index(drop=True)


def by_year(trades: pd.DataFrame, ret_col: str = "net_ret") -> pd.DataFrame:
    """Pure: per-calendar-year summary.

    A strategy whose whole edge lives in one year (March 2020, say) is not an edge,
    it is one regime. This is the concentration check that `swing_bounce`'s positive
    cells failed.
    """
    if trades.empty:
        return pd.DataFrame()
    t = trades.copy()
    t["year"] = pd.DatetimeIndex(t["date"]).year
    rows = []
    for y, grp in t.groupby("year"):
        m = trade_metrics(grp, ret_col)
        m["year"] = int(y)
        m["sum_ret"] = float(grp[ret_col].sum())
        rows.append(m)
    cols = ["year", "n_trades", "win_rate", "mean_ret", "median_ret", "profit_factor", "sum_ret", "worst"]
    df = pd.DataFrame(rows)
    return df[[c for c in cols if c in df]].sort_values("year").reset_index(drop=True)


def jackknife_years(trades: pd.DataFrame, ret_col: str = "net_ret") -> dict:
    """Pure: leave-one-year-out means — does any single year carry the result?

    The honest test of a result with one standout year. If dropping the best year
    leaves the mean comfortably positive, the effect is not that year. If it collapses,
    it is, and the headline is a story about one regime.
    """
    if trades.empty:
        return {}
    t = trades.copy()
    t["year"] = pd.DatetimeIndex(t["date"]).year
    full = float(t[ret_col].mean())
    rows = {}
    for y in sorted(t["year"].unique()):
        kept = t[t["year"] != y][ret_col]
        rows[int(y)] = float(kept.mean()) if len(kept) else np.nan
    worst_y = min(rows, key=lambda k: rows[k])
    return {
        "full_mean_bps": full * 1e4,
        "leave_one_out_bps": {y: v * 1e4 for y, v in rows.items()},
        "min_loo_bps": rows[worst_y] * 1e4,
        "most_influential_year": worst_y,
        "survives_dropping_best_year": bool(rows[worst_y] > 0),
    }


def by_period(trades: pd.DataFrame, splits: dict[str, tuple[str, str]], ret_col: str = "net_ret") -> pd.DataFrame:
    """Pure: §11 out-of-sample split summary (dev / validation / final)."""
    rows = []
    for name, (lo, hi) in splits.items():
        mask = (trades["date"] >= pd.Timestamp(lo)) & (trades["date"] <= pd.Timestamp(hi))
        m = trade_metrics(trades[mask], ret_col)
        m["period"] = name
        m["span"] = f"{lo}..{hi}"
        rows.append(m)
    df = pd.DataFrame(rows)
    cols = ["period", "span", "n_trades", "win_rate", "mean_ret", "median_ret", "profit_factor", "t_stat", "worst"]
    return df[[c for c in cols if c in df]]
