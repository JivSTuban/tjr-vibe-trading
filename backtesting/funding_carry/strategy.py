"""Delta-neutral funding-carry backtest.

Position = long spot + short perp (delta-neutral). The short perp RECEIVES funding
when the rate is positive (longs pay shorts) and PAYS when negative. First-order
model: the two price legs cancel, so per-interval return ≈ the funding rate on
notional. This isolates the report's question — is the funding stream capturable
net of the two-leg round-trip cost and funding flips? Basis (spot vs perp spread)
convergence is a second-order term we omit; on large-cap majors it's small and
funding keeps it pinned. Flagged as a caveat, not hidden.

Two variants:
  * ALWAYS-ON — hold delta-neutral the whole window; collect every funding interval
    (positive and negative); pay ONE round-trip (both legs) amortized over the span.
  * FUNDING-TIMED — only hold the next interval when the LAST settled funding
    (look-ahead-safe) >= threshold; flat otherwise. Avoids negative funding but pays
    a two-leg round-trip on every toggle — churn vs avoided-drag is the whole test.

Costs: opening = spot_fee + perp_fee; closing = spot_fee + perp_fee.
Default taker: spot 0.10% + perp 0.05% per side ⇒ 0.30% full round-trip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FundingCfg:
    spot_fee_pct: float = 0.001      # 0.10% per side (spot leg, taker)
    perp_fee_pct: float = 0.0005     # 0.05% per side (perp leg, taker)
    cond_threshold: float = 0.0      # funding-timed: hold if last rate >= this
    # --- regime gate (hysteresis state machine) ---
    gate_window: int = 9             # trailing intervals for the funding signal (~3 days)
    gate_enter_bps: float = 0.30     # ENTER when trailing-mean funding >= this (bps/8h)
    gate_exit_bps: float = 0.05      # EXIT when it falls below this (hysteresis band)

    @property
    def leg_cost(self) -> float:     # one side of the pair (open OR close)
        return self.spot_fee_pct + self.perp_fee_pct

    @property
    def round_trip(self) -> float:   # open + close, both legs
        return 2.0 * self.leg_cost


def _intervals_per_year(idx: pd.DatetimeIndex) -> float:
    if len(idx) < 2:
        return 1095.0  # 8h default
    hrs = np.median(np.diff(idx.values).astype("timedelta64[m]").astype(float)) / 60.0
    hrs = hrs if hrs > 0 else 8.0
    return 365.0 * 24.0 / hrs


def _max_neg_streak(rates: np.ndarray) -> int:
    m = c = 0
    for r in rates:
        c = c + 1 if r < 0 else 0
        m = max(m, c)
    return m


def gated_carry(f: np.ndarray, cfg: FundingCfg) -> dict:
    """Regime-gated carry with hysteresis (look-ahead-safe).

    A state machine on the TRAILING funding signal (mean of the prior ``gate_window``
    intervals, strictly before i): ENTER when signal >= gate_enter_bps, EXIT when it
    falls below gate_exit_bps. The enter>exit band prevents whipsaw. While IN, collect
    that interval's funding. Pay one leg_cost on each enter and each exit — with
    hysteresis these are few, unlike the toggle-every-interval 'timed' variant.
    """
    n = len(f)
    enter = cfg.gate_enter_bps / 1e4
    exit_ = cfg.gate_exit_bps / 1e4
    csum = np.concatenate([[0.0], np.cumsum(f)])
    held = np.zeros(n, dtype=bool)
    toggle_at = np.zeros(n, dtype=bool)
    state = False
    for i in range(n):
        lo = max(0, i - cfg.gate_window)
        sig = (csum[i] - csum[lo]) / (i - lo) if i - lo > 0 else -1e9  # prior-only
        if not state and sig >= enter:
            state = True; toggle_at[i] = True          # enter (pay leg_cost)
        elif state and sig < exit_:
            state = False; toggle_at[i] = True          # exit (pay leg_cost)
        held[i] = state
    toggles = int(toggle_at.sum()) + (1 if state else 0)  # +final close if still IN
    collected = np.where(held, f, 0.0)
    cost_stream = np.where(toggle_at, cfg.leg_cost, 0.0)
    cum_net = np.cumsum(collected) - np.cumsum(cost_stream)
    if state:
        cum_net[-1] -= cfg.leg_cost                    # book the final close at the end
    total = float(collected.sum()) - toggles * cfg.leg_cost
    return {"total": total, "toggles": toggles, "held_frac": float(held.mean()),
            "cum_net": cum_net}


def carry_symbol(funding: pd.DataFrame, cfg: FundingCfg) -> dict:
    """Run both carry variants on one symbol's funding history."""
    f = funding["funding_rate"].to_numpy(dtype=float)
    idx = funding.index
    n = len(f)
    if n == 0:
        return {"n": 0}
    ipy = _intervals_per_year(idx)
    years = n / ipy

    # --- always-on: collect every interval, one amortized round-trip ---
    gross_cum = np.cumsum(f)
    gross_total = float(gross_cum[-1])
    net_always_total = gross_total - cfg.round_trip
    always_cum_net = gross_cum - cfg.round_trip  # cost booked up front (conservative)

    # --- funding-timed: hold interval i iff funding[i-1] >= threshold ---
    held = np.zeros(n, dtype=bool)
    held[1:] = f[:-1] >= cfg.cond_threshold      # look-ahead-safe (prev rate only)
    collected = np.where(held, f, 0.0)
    # toggle costs: entering (flat->held) costs leg_cost, exiting costs leg_cost
    toggles = int(np.sum(held[1:] != held[:-1])) + (1 if held[0] else 0)
    if held[-1]:
        toggles += 1  # final close
    cond_cost = toggles * cfg.leg_cost
    cond_total = float(collected.sum()) - cond_cost
    cond_cum_net = np.cumsum(collected) - np.cumsum(
        np.where(np.concatenate([[held[0]], held[1:] != held[:-1]]), cfg.leg_cost, 0.0))

    # --- regime-gated (hysteresis) ---
    g = gated_carry(f, cfg)

    return {
        "n": n,
        "years": round(years, 3),
        "intervals_per_year": round(ipy, 1),
        "pct_positive": round(float((f > 0).mean()), 4),
        "mean_funding_bps": round(float(f.mean()) * 1e4, 4),
        "max_neg_streak": _max_neg_streak(f),
        "gross_APR": round(gross_total / years, 4),
        "net_APR_always": round(net_always_total / years, 4),
        "net_APR_timed": round(cond_total / years, 4),
        "timed_toggles": toggles,
        "timed_held_frac": round(float(held.mean()), 3),
        "net_APR_gated": round(g["total"] / years, 4),
        "gated_toggles": g["toggles"],
        "gated_held_frac": round(g["held_frac"], 3),
        "gross_total_frac": round(gross_total, 4),
        "_dates": [str(d) for d in idx],
        "_gross_cum": [round(x, 6) for x in gross_cum.tolist()],
        "_always_cum_net": [round(x, 6) for x in always_cum_net.tolist()],
        "_timed_cum_net": [round(x, 6) for x in cond_cum_net.tolist()],
        "_gated_cum_net": [round(x, 6) for x in g["cum_net"].tolist()],
        "_rates": [round(x, 8) for x in f.tolist()],
    }


def portfolio(per_symbol: dict) -> dict:
    """Equal-weight portfolio: average APR across symbols + pooled positivity."""
    syms = [s for s, r in per_symbol.items() if r.get("n")]
    if not syms:
        return {}
    def avg(k):
        return round(float(np.mean([per_symbol[s][k] for s in syms])), 4)
    return {
        "symbols": syms,
        "gross_APR": avg("gross_APR"),
        "net_APR_always": avg("net_APR_always"),
        "net_APR_timed": avg("net_APR_timed"),
        "net_APR_gated": avg("net_APR_gated"),
        "gated_held_frac": avg("gated_held_frac"),
        "pct_positive": avg("pct_positive"),
        "mean_funding_bps": avg("mean_funding_bps"),
    }


def gate_sweep(frames: dict, cfg: FundingCfg, enter_bps_list) -> List[dict]:
    """Sweep the gate ENTER threshold; report equal-weight portfolio net APR per level.

    For each enter threshold, re-run gated_carry on every symbol and average the net
    APR. Answers: is there a 'switch on when funding is elevated' band that beats
    always-on, or does the fuel never justify turning it on?
    """
    from dataclasses import replace
    out = []
    for eb in enter_bps_list:
        c = replace(cfg, gate_enter_bps=eb, gate_exit_bps=min(cfg.gate_exit_bps, eb / 2))
        aprs, helds, toggs = [], [], []
        for df in frames.values():
            f = df["funding_rate"].to_numpy(dtype=float)
            if len(f) < 2:
                continue
            ipy = _intervals_per_year(df.index)
            g = gated_carry(f, c)
            aprs.append(g["total"] / (len(f) / ipy))
            helds.append(g["held_frac"]); toggs.append(g["toggles"])
        if aprs:
            out.append({"enter_bps": eb,
                        "net_APR": round(float(np.mean(aprs)), 4),
                        "held_frac": round(float(np.mean(helds)), 3),
                        "avg_toggles": round(float(np.mean(toggs)), 1)})
    return out
