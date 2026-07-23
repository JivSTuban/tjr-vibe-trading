"""Forward-only event backtest engine for TJR 4X trades.

For each trade (already causally created by ``strategy.find_trades``):
  * Walk 5m bars from ``entry_time`` forward.
  * Fill the limit entry when price trades into the zone
    (long: bar low <= entry; short: bar high >= entry).
  * From the fill bar onward, resolve SL/TP. If BOTH the SL and TP levels
    fall inside a single bar's [low, high], assume **SL hit first**
    (conservative).
  * Costs (fee + slippage) are applied to BOTH entry and exit, expressed
    in R terms so metrics are cost-net.
  * Enforce ``max_open_positions`` (default 1): a trade whose fill window
    overlaps an already-open trade is skipped.

R accounting:
    gross_R for a raw win = +rr_target, raw loss = -1.
    Round-trip cost fraction = 2 * cost_per_side_pct of notional. In R
    units that is cost_R = (2 * cost_per_side_pct * entry) / risk_per_R,
    where risk_per_R = |entry - sl|. net_R = gross_R - cost_R.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import numpy as np
import pandas as pd

from .strategy import Trade


@dataclass
class ClosedTrade:
    entry_time: pd.Timestamp
    fill_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: int
    entry: float
    sl: float
    tp: float
    exit_price: float
    outcome: str          # "tp" | "sl"
    gross_R: float
    cost_R: float
    net_R: float


@dataclass
class Result:
    trade_count: int = 0
    win_rate: float = 0.0
    avg_R: float = 0.0            # expectancy (net)
    profit_factor: float = 0.0
    avg_win_R: float = 0.0
    avg_loss_R: float = 0.0
    max_consecutive_losses: int = 0
    max_drawdown_R: float = 0.0
    gross_return_R: float = 0.0
    net_return_R: float = 0.0
    closed_trades: List[ClosedTrade] = field(default_factory=list)

    def trades_dataframe(self) -> pd.DataFrame:
        if not self.closed_trades:
            return pd.DataFrame(columns=list(ClosedTrade.__annotations__.keys()))
        return pd.DataFrame([asdict(t) for t in self.closed_trades])

    def to_csv(self, path: str) -> None:
        self.trades_dataframe().to_csv(path, index=False)

    def summary_dict(self) -> dict:
        d = asdict(self)
        d.pop("closed_trades", None)
        return d


def _cost_R(trade: Trade, cfg) -> float:
    risk = abs(trade.entry - trade.sl)
    if risk <= 0:
        return 0.0
    round_trip = 2.0 * cfg.cost_per_side_pct * trade.entry
    return round_trip / risk


def _resolve_one(df5m: pd.DataFrame, trade: Trade, cfg,
                 start_ts: pd.Timestamp) -> Optional[ClosedTrade]:
    """Fill + resolve a single trade forward from ``start_ts``.

    Returns None if the entry never fills within available data.
    """
    window = df5m.loc[start_ts:]
    if window.empty:
        return None

    entry, sl, tp, d = trade.entry, trade.sl, trade.tp, trade.direction
    fill_time = None
    fill_iloc = None
    idx = window.index
    lows = window["low"].values
    highs = window["high"].values

    for i in range(len(window)):
        lo, hi = lows[i], highs[i]
        if d == 1 and lo <= entry:
            fill_time, fill_iloc = idx[i], i
            break
        if d == -1 and hi >= entry:
            fill_time, fill_iloc = idx[i], i
            break
    if fill_time is None:
        return None

    cost_r = _cost_R(trade, cfg)

    # resolve SL/TP from the fill bar onward (fill bar can itself resolve)
    for i in range(fill_iloc, len(window)):
        lo, hi = lows[i], highs[i]
        hit_sl = (lo <= sl) if d == 1 else (hi >= sl)
        hit_tp = (hi >= tp) if d == 1 else (lo <= tp)
        if hit_sl and hit_tp:
            # both in same bar -> SL first (conservative)
            return ClosedTrade(trade.entry_time, fill_time, idx[i], d, entry,
                               sl, tp, sl, "sl", -1.0, cost_r, -1.0 - cost_r)
        if hit_sl:
            return ClosedTrade(trade.entry_time, fill_time, idx[i], d, entry,
                               sl, tp, sl, "sl", -1.0, cost_r, -1.0 - cost_r)
        if hit_tp:
            g = cfg.rr_target
            return ClosedTrade(trade.entry_time, fill_time, idx[i], d, entry,
                               sl, tp, tp, "tp", g, cost_r, g - cost_r)
    return None  # ran out of data -> unresolved, dropped


def backtest(df5m: pd.DataFrame, trades: List[Trade], cfg) -> Result:
    """Resolve all trades forward-only, enforcing max concurrent positions."""
    df5m = df5m.copy()
    df5m.columns = [c.lower() for c in df5m.columns]
    df5m = df5m.sort_index()

    closed: List[ClosedTrade] = []
    open_until: List[pd.Timestamp] = []  # exit times of currently-open trades

    for trade in sorted(trades, key=lambda t: t.entry_time):
        # prune finished positions
        open_until = [t for t in open_until if t > trade.entry_time]
        if len(open_until) >= cfg.max_open_positions:
            continue  # overlaps an open trade -> skip
        ct = _resolve_one(df5m, trade, cfg, trade.entry_time)
        if ct is None:
            continue
        closed.append(ct)
        open_until.append(ct.exit_time)

    return _metrics(closed)


def _metrics(closed: List[ClosedTrade]) -> Result:
    r = Result(closed_trades=closed)
    r.trade_count = len(closed)
    if not closed:
        return r

    net = np.array([c.net_R for c in closed], dtype=float)
    gross = np.array([c.gross_R for c in closed], dtype=float)
    wins = net[net > 0]
    losses = net[net <= 0]

    r.win_rate = len(wins) / len(closed)
    r.avg_R = float(net.mean())
    r.avg_win_R = float(wins.mean()) if len(wins) else 0.0
    r.avg_loss_R = float(losses.mean()) if len(losses) else 0.0
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    r.profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else math.inf
    r.gross_return_R = float(gross.sum())
    r.net_return_R = float(net.sum())

    # max consecutive losses
    mcl = cur = 0
    for c in closed:
        if c.net_R <= 0:
            cur += 1
            mcl = max(mcl, cur)
        else:
            cur = 0
    r.max_consecutive_losses = mcl

    # max drawdown in R (peak-to-trough of cumulative net R)
    eq = np.cumsum(net)
    peak = np.maximum.accumulate(eq)
    dd = eq - peak
    r.max_drawdown_R = float(dd.min()) if len(dd) else 0.0

    return r
