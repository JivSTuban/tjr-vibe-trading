"""Sanity tests for delta-neutral funding carry: look-ahead safety, cost accounting."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.funding_carry.strategy import FundingCfg, carry_symbol, gated_carry


def _fund(rates, start="2025-01-01"):
    idx = pd.date_range(start, periods=len(rates), freq="8h", tz="UTC")
    return pd.DataFrame({"funding_rate": rates}, index=idx)


def test_always_on_gross_is_sum_of_funding():
    rates = [0.0001] * 300  # +1bp/8h, all positive
    r = carry_symbol(_fund(rates), FundingCfg())
    assert abs(r["gross_total_frac"] - sum(rates)) < 1e-9
    # net always-on = gross - one round-trip (APR fields rounded to 4dp)
    assert abs(r["net_APR_always"] * r["years"]
               - (sum(rates) - FundingCfg().round_trip)) < 1e-3


def test_timed_is_lookahead_safe():
    # one negative spike at i=5; timed must still HOLD i=5 (decided on i=4>=0),
    # then SKIP i=6 (decided on i=5<0). It cannot avoid the spike it can't foresee.
    rates = [0.0001] * 10
    rates[5] = -0.001
    r = carry_symbol(_fund(rates), FundingCfg(cond_threshold=0.0))
    # held[i] uses funding[i-1]; so held[6] is False (prev was negative), held[5] True
    assert r["timed_held_frac"] < 1.0
    assert r["timed_toggles"] >= 2  # exit after the spike, re-enter later


def test_annualization_uses_interval_spacing():
    rates = [0.00005] * 1095  # ~1 year of 8h intervals
    r = carry_symbol(_fund(rates), FundingCfg())
    assert abs(r["intervals_per_year"] - 1095) < 5
    assert abs(r["years"] - 1.0) < 0.02


def test_gate_holds_only_elevated_regime_and_low_churn():
    # 100 flat-low intervals (0.02bps), then 100 elevated (0.5bps), then 100 low again.
    rates = [0.000002] * 100 + [0.00005] * 100 + [0.000002] * 100
    cfg = FundingCfg(gate_window=9, gate_enter_bps=0.30, gate_exit_bps=0.05)
    g = gated_carry(np.array(rates), cfg)
    # should be IN only during the elevated block -> held ~1/3, and FEW toggles
    assert 0.25 < g["held_frac"] < 0.45
    assert g["toggles"] <= 4              # enter once, exit once (+/- edges) — not churning
    # and it should beat always-collect-everything net (it skips the dead regimes' cost drag)
    assert g["total"] > 0


def test_gate_is_lookahead_safe():
    # single elevated spike at i=50; the gate signal uses only prior intervals,
    # so entry can only happen AFTER the trailing mean rises — never on/ before the spike.
    rates = [0.000001] * 200
    rates[50] = 0.01
    cfg = FundingCfg(gate_window=9, gate_enter_bps=0.30, gate_exit_bps=0.05)
    g = gated_carry(np.array(rates), cfg)
    # the huge spike lifts the trailing mean AFTER i=50, so any holding starts > i=50
    # (cannot have collected the spike itself)
    assert g["held_frac"] < 0.2


def test_negative_funding_makes_carry_negative():
    rates = [-0.0002] * 200  # persistent negative funding: short pays
    r = carry_symbol(_fund(rates), FundingCfg())
    assert r["gross_APR"] < 0
    assert r["net_APR_always"] < 0
    # timed should hold ~nothing (last rate always < 0) -> near-zero, beats always-on
    assert r["net_APR_timed"] > r["net_APR_always"]
    assert r["max_neg_streak"] == 200
