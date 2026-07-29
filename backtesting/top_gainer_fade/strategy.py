"""Intraday top-gainer fade: short the day's single biggest large-cap perp gainer.

Deterministic and look-ahead-safe. For each UTC calendar day:

  1. RANK — at ``decision_hour`` (default 12:00 UTC) compute each instrument's
     intraday run-up = close[t_dec] / day_open - 1, using ONLY bars at/before
     t_dec. Pick the SINGLE instrument with the highest run-up that also clears
     ``min_gain`` (the day's "top earner so far").
  2. ENTER — market SHORT at close[t_dec] (taker fill).
  3. STOP  — SL = intraday high through t_dec * (1 + sl_buffer_pct). This IS the
     "prior resistance" the price ran into; risk = sl - entry. Setups whose
     risk/entry < ``min_stop_pct`` are skipped (kills degenerate tiny-stop R blowups,
     same lever that first turned TJR-4X gross-positive).
  4. EXIT  — walk 5m bars AFTER t_dec to the day's last bar (~23:55). If any bar
     high >= sl -> stopped out (-1R). Else exit at the day's close (time exit);
     short gross_R = (entry - exit_close) / risk. Same-day only, never held over.

Costs are outcome-aware, in R units (fraction of |entry - sl|):
  * TRADING — both legs are market/taker: (taker+slip)*entry + (taker+slip)*exit.
  * FUNDING — we have NO funding data in cache (OHLCV only), so funding is a signed
    SCENARIO: ``funding_bps_per_interval`` is the SHORT's P&L per 8h boundary crossed
    (positive = short EARNS, which is what actually happens when longs are crowded in
    a pump). Boundaries are 00:00 / 08:00 / 16:00 UTC. funding_R adds to net.

The headline metric uses funding=0 (pure price + fees) so no edge is fabricated;
funding is reported as a separate sensitivity band.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from backtesting.tjr_4x.engine import ClosedTrade

_FUNDING_HOURS = (0, 8, 16)  # Binance USDⓈ-M funding boundaries (UTC)


@dataclass(frozen=True)
class FadeConfig:
    side: str = "short"              # "short" = fade the gainer | "long" = ride it
    decision_hour: int = 12          # UTC hour to rank + enter
    min_gain: float = 0.02           # top gainer must be up >= this at t_dec (2%)
    sl_buffer_pct: float = 0.001     # 0.1% beyond the intraday extreme (S/R)
    min_stop_pct: float = 0.002      # skip if risk/entry < this (tiny-stop tax)
    # execution cost model:
    #   "taker_both"  -> entry AND exit are market/taker fills + slippage (conservative)
    #   "maker_entry" -> entry rests as a limit (maker, no slippage); exit stays
    #                    market/taker (same-day close + stops are market orders).
    #                    Optimistic bound: assumes the limit fills at the entry price.
    cost_model: str = "taker_both"
    taker_fee_pct: float = 0.0005    # 0.05%
    maker_fee_pct: float = 0.0002    # 0.02% (resting limit)
    slippage_pct: float = 0.0005     # 0.05% (taker legs only)
    # MARKET funding rate in bps per 8h boundary crossed (+ = longs pay shorts,
    # the usual sign during a pump). Position P&L = -direction * rate, so a short
    # EARNS and a long PAYS positive funding automatically.
    funding_bps_per_interval: float = 0.0


@dataclass
class FadeTrade:
    """A resolved top-gainer fade, extends ClosedTrade with the faded symbol + runup."""
    symbol: str
    day: str
    runup: float           # intraday run-up at decision time
    n_funding: int         # 8h boundaries crossed while in the trade
    ct: ClosedTrade


def _funding_intervals(entry_ts: pd.Timestamp, exit_ts: pd.Timestamp) -> int:
    """Count 00/08/16 UTC funding boundaries strictly after entry, up to exit."""
    n = 0
    cur = entry_ts.floor("h")
    while cur <= exit_ts:
        if cur > entry_ts and cur.hour in _FUNDING_HOURS:
            n += 1
        cur += pd.Timedelta(hours=1)
    return n


def _day_features(group: pd.DataFrame, t_dec: pd.Timestamp):
    """Per-day (open, high-through-t_dec, entry close, entry_time, post frame).

    Returns None if the decision bar is missing or there are no bars after it.
    Look-ahead-safe: ranking inputs use only bars at/<= t_dec.
    """
    pre = group[group.index <= t_dec]
    post = group[group.index > t_dec]
    if pre.empty or post.empty:
        return None
    day_open = float(group.iloc[0]["open"])
    if day_open <= 0:
        return None
    entry = float(pre.iloc[-1]["close"])
    return {
        "day_open": day_open,
        "high_pre": float(pre["high"].max()),
        "low_pre": float(pre["low"].min()),
        "entry": entry,
        "entry_time": pre.index[-1],
        "runup": entry / day_open - 1.0,
        "post": post,
    }


def _cost_R(entry: float, exit_price: float, risk: float, cfg: FadeConfig) -> float:
    taker = cfg.taker_fee_pct + cfg.slippage_pct
    if cfg.cost_model == "maker_entry":
        entry_leg = cfg.maker_fee_pct * entry        # resting limit -> maker, no slip
    else:
        entry_leg = taker * entry                    # market entry -> taker + slip
    exit_leg = taker * exit_price                    # close/stop is always a market order
    return (entry_leg + exit_leg) / risk


def _resolve(feat: dict, cfg: FadeConfig, symbol: str, day: str
             ) -> Optional[FadeTrade]:
    """Resolve one same-day trade on the top gainer for cfg.side ('short'|'long').

    short: SL at intraday high (resistance) above entry; stop when high>=SL.
    long:  SL at intraday low  (support)   below entry; stop when low<=SL.
    """
    entry = feat["entry"]
    direction = -1 if cfg.side == "short" else 1
    if direction == -1:
        sl = feat["high_pre"] * (1.0 + cfg.sl_buffer_pct)
        risk = sl - entry
    else:
        sl = feat["low_pre"] * (1.0 - cfg.sl_buffer_pct)
        risk = entry - sl
    if risk <= 0 or (risk / entry) < cfg.min_stop_pct:
        return None  # degenerate / tiny-stop -> skip (R blows up otherwise)

    post = feat["post"]
    highs = post["high"].values
    lows = post["low"].values
    entry_time = feat["entry_time"]

    exit_price = float(post.iloc[-1]["close"])  # default: same-day time exit
    exit_time = post.index[-1]
    outcome = "time"
    for i in range(len(post)):
        hit = (highs[i] >= sl) if direction == -1 else (lows[i] <= sl)
        if hit:                                  # stopped out at the S/R level
            exit_price, exit_time, outcome = sl, post.index[i], "sl"
            break

    gross_R = direction * (exit_price - entry) / risk   # long: up=win, short: down=win
    trade_cost_R = _cost_R(entry, exit_price, risk, cfg)

    n_funding = _funding_intervals(entry_time, exit_time)
    # position P&L = -direction * market_rate: short earns / long pays positive funding
    funding_R = -direction * (cfg.funding_bps_per_interval / 10000.0) * n_funding * entry / risk
    net_R = gross_R - trade_cost_R + funding_R

    ct = ClosedTrade(
        entry_time=entry_time, fill_time=entry_time, exit_time=exit_time,
        direction=direction, entry=entry, sl=sl, tp=entry, exit_price=exit_price,
        outcome=outcome, gross_R=gross_R, cost_R=trade_cost_R - funding_R,
        net_R=net_R,
    )
    return FadeTrade(symbol=symbol, day=day, runup=feat["runup"],
                     n_funding=n_funding, ct=ct)


def find_fades(frames: Dict[str, pd.DataFrame], cfg: FadeConfig) -> List[FadeTrade]:
    """Build one fade per day: short the single biggest gainer across ``frames``.

    ``frames`` maps symbol -> 5m OHLCV (lowercased cols, UTC datetime index).
    Returns resolved FadeTrades sorted by entry_time.
    """
    # per-symbol, per-day features keyed by date string
    per_sym_day: Dict[str, Dict[str, dict]] = {}
    all_days: set = set()
    for sym, df in frames.items():
        df = df.sort_index()
        by_day = per_sym_day.setdefault(sym, {})
        for date, group in df.groupby(df.index.normalize()):
            t_dec = date + pd.Timedelta(hours=cfg.decision_hour)
            feat = _day_features(group, t_dec)
            if feat is not None:
                key = date.strftime("%Y-%m-%d")
                by_day[key] = feat
                all_days.add(key)

    trades: List[FadeTrade] = []
    for day in sorted(all_days):
        # rank instruments that have data this day and clear the gain threshold
        cands: List[Tuple[float, str]] = []
        for sym, by_day in per_sym_day.items():
            feat = by_day.get(day)
            if feat is not None and feat["runup"] >= cfg.min_gain:
                cands.append((feat["runup"], sym))
        if not cands:
            continue
        _, top_sym = max(cands)                  # the day's single biggest gainer
        ft = _resolve(per_sym_day[top_sym][day], cfg, top_sym, day)
        if ft is not None:
            trades.append(ft)

    trades.sort(key=lambda t: t.ct.entry_time)
    return trades
