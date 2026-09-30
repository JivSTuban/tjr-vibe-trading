"""Tests for the AMM cost model and the paper-fill simulation.

The load-bearing ones are `test_quote_reserve_is_half_of_liquidity` and
`test_costs_can_flip_a_winner_to_a_loss`. The first guards the 2x error that is
easiest to make here; the second guards the entire reason the module exists.
"""

from __future__ import annotations

import math

import pytest

from fomo_radar.fill import (
    CostModel,
    buy,
    max_size_for_impact,
    round_trip_cost_pct,
    sell,
)
from fomo_radar.paper import ExitPolicy, simulate

NO_FEE = CostModel(lp_fee=0.0, priority_fee_sol=0.0, jito_tip_sol=0.0, fail_rate=0.0)


def series(*points: tuple[float, float, float]) -> list[dict]:
    """Build a price series from (age_seconds, price_usd, liquidity_usd) triples."""
    return [
        {
            "mint": "MINT",
            "age_seconds": age,
            "price_usd": price,
            "market_cap_usd": price * 1_000_000,
            "liquidity_usd": liq,
        }
        for age, price, liq in points
    ]


# --------------------------------------------------------------------------
# The cost model
# --------------------------------------------------------------------------


def test_quote_reserve_is_half_of_liquidity():
    """DexScreener liquidity counts BOTH sides; the quote side is half.

    With no fees, buying `dx` into quote reserve Q costs exactly dx/Q in impact.
    A $750 buy into a $15,000 pool (Q = $7,500) must therefore slip 10%. If
    someone "fixes" quote_share to 1.0 this drops to 5% and every net return in
    the project doubles for free.
    """
    fill = buy(liquidity_usd=15_000.0, price_usd=1.0, cost=NO_FEE, usd=750.0)
    assert fill.slippage_pct == pytest.approx(0.10, rel=1e-9)


def test_impact_is_linear_in_size_and_inverse_in_depth():
    small = buy(liquidity_usd=100_000.0, price_usd=1.0, cost=NO_FEE, usd=100.0)
    big = buy(liquidity_usd=100_000.0, price_usd=1.0, cost=NO_FEE, usd=1_000.0)
    assert big.slippage_pct == pytest.approx(small.slippage_pct * 10, rel=1e-9)

    deep = buy(liquidity_usd=1_000_000.0, price_usd=1.0, cost=NO_FEE, usd=100.0)
    assert deep.slippage_pct == pytest.approx(small.slippage_pct / 10, rel=1e-9)


def test_buy_is_never_better_than_mid():
    for liq in (5_000.0, 50_000.0, 5_000_000.0):
        fill = buy(liquidity_usd=liq, price_usd=0.004, cost=CostModel(trade_usd=500.0))
        assert fill.avg_price_usd > fill.mid_price_usd
        assert fill.slippage_pct > 0


def test_sell_is_never_better_than_mid():
    opened = buy(liquidity_usd=50_000.0, price_usd=0.004, cost=NO_FEE, usd=500.0)
    closed = sell(tokens=opened.tokens, liquidity_usd=50_000.0, price_usd=0.004, cost=NO_FEE)
    assert closed.avg_price_usd < closed.mid_price_usd
    assert closed.slippage_pct > 0


def test_round_trip_at_a_flat_price_always_loses():
    """Buy and sell with no price move must end down. There is no free round trip."""
    cost = CostModel(trade_usd=500.0)
    for liq in (15_000.0, 100_000.0, 1_000_000.0):
        assert round_trip_cost_pct(liquidity_usd=liq, cost=cost) > 0


def test_round_trip_cost_falls_as_the_pool_deepens():
    cost = CostModel(trade_usd=500.0)
    thin = round_trip_cost_pct(liquidity_usd=15_000.0, cost=cost)
    deep = round_trip_cost_pct(liquidity_usd=500_000.0, cost=cost)
    assert thin > deep
    # At the signal's own liquidity floor the hurdle is large, not marginal.
    # This is the headline fact for anyone asking whether to automate buying.
    assert thin > 0.05


def test_fail_rate_raises_expected_fee_burn():
    clean = CostModel(fail_rate=0.0)
    flaky = CostModel(fail_rate=0.5)
    assert flaky.fixed_cost_usd == pytest.approx(clean.fixed_cost_usd * 2, rel=1e-9)


def test_max_size_for_impact_inverts_the_buy_equation():
    cost = CostModel(lp_fee=0.0025)
    size = max_size_for_impact(liquidity_usd=15_000.0, max_impact_pct=0.02, cost=cost)
    achieved = buy(liquidity_usd=15_000.0, price_usd=1.0, cost=cost, usd=size)
    assert achieved.slippage_pct == pytest.approx(0.02, rel=1e-6)


def test_unpriceable_pool_raises_rather_than_filling_free():
    """A data gap must never be modelled as a costless fill."""
    with pytest.raises(ValueError):
        buy(liquidity_usd=0.0, price_usd=1.0, cost=NO_FEE, usd=100.0)
    with pytest.raises(ValueError):
        buy(liquidity_usd=10_000.0, price_usd=0.0, cost=NO_FEE, usd=100.0)


# --------------------------------------------------------------------------
# The simulation
# --------------------------------------------------------------------------


def test_take_profit_exits_at_the_target_observation():
    trade = simulate(
        series((0, 1.0, 100_000.0), (300, 2.0, 100_000.0), (900, 4.0, 100_000.0)),
        policy=ExitPolicy(stop_pct=0.5, take_profit_x=3.0),
        cost=CostModel(trade_usd=100.0),
    )
    assert trade is not None
    assert trade.exit_reason == "take_profit"
    assert trade.exit_age_s == 900
    assert trade.gross_return_pct == pytest.approx(3.0)


def test_stop_exits_and_beats_holding_to_zero():
    trade = simulate(
        series((0, 1.0, 100_000.0), (300, 0.4, 80_000.0), (900, 0.01, 5_000.0)),
        policy=ExitPolicy(stop_pct=0.5, take_profit_x=None),
        cost=CostModel(trade_usd=100.0),
    )
    assert trade is not None
    assert trade.exit_reason == "stop"
    assert trade.exit_age_s == 300


def test_stop_wins_a_tie_against_the_target():
    """When one snapshot step is consistent with both, assume the worse one."""
    trade = simulate(
        series((0, 1.0, 100_000.0), (300, 0.2, 100_000.0)),
        policy=ExitPolicy(stop_pct=0.5, take_profit_x=3.0),
        cost=CostModel(trade_usd=100.0),
    )
    assert trade is not None
    assert trade.exit_reason == "stop"


def test_trailing_stop_fires_off_the_peak():
    trade = simulate(
        series((0, 1.0, 100_000.0), (300, 2.0, 100_000.0), (900, 1.2, 100_000.0)),
        policy=ExitPolicy(stop_pct=0.9, take_profit_x=None, trail_pct=0.3),
        cost=CostModel(trade_usd=100.0),
    )
    assert trade is not None
    assert trade.exit_reason == "trailing"
    assert trade.exit_age_s == 900


def test_time_stop_closes_the_position():
    trade = simulate(
        series((0, 1.0, 100_000.0), (3600, 1.1, 100_000.0), (86_400, 1.2, 100_000.0)),
        policy=ExitPolicy(stop_pct=0.9, take_profit_x=None, max_hold_s=3600.0),
        cost=CostModel(trade_usd=100.0),
    )
    assert trade is not None
    assert trade.exit_reason == "time_stop"
    assert trade.exit_age_s == 3600


def test_costs_can_flip_a_winner_to_a_loss():
    """The entire reason this module exists.

    A token that gains 8% on the chart is a LOSS once a $500 position pays
    round-trip impact in a $15k pool. Any refactor that makes this pass on gross
    return alone has reintroduced the bug.
    """
    trade = simulate(
        series((0, 1.0, 15_000.0), (300, 1.08, 15_000.0)),
        policy=ExitPolicy(stop_pct=0.9, take_profit_x=None),
        cost=CostModel(trade_usd=500.0),
    )
    assert trade is not None
    assert trade.gross_return_pct > 0
    assert trade.net_return_pct < 0
    assert trade.cost_drag_pct > 0


def test_net_is_always_worse_than_gross():
    trade = simulate(
        series((0, 1.0, 250_000.0), (300, 5.0, 400_000.0)),
        policy=ExitPolicy(stop_pct=0.9, take_profit_x=None),
        cost=CostModel(trade_usd=500.0),
    )
    assert trade is not None
    assert trade.net_return_pct < trade.gross_return_pct


def test_entry_latency_picks_a_later_observation():
    points = series((0, 1.0, 100_000.0), (300, 2.0, 100_000.0), (900, 2.5, 100_000.0))
    early = simulate(points, policy=ExitPolicy(take_profit_x=None), cost=CostModel(trade_usd=100.0))
    late = simulate(
        points, policy=ExitPolicy(take_profit_x=None), cost=CostModel(trade_usd=100.0),
        entry_age_s=300.0,
    )
    assert early is not None and late is not None
    assert early.entry_age_actual_s == 0
    assert late.entry_age_actual_s == 300
    # Entering after the token already doubled captures much less of the move.
    assert late.gross_return_pct < early.gross_return_pct


def test_series_too_short_returns_none_not_a_flat_trade():
    """A data gap must be absent from the results, never a 0% trade."""
    assert simulate(series((0, 1.0, 100_000.0)), policy=ExitPolicy(), cost=CostModel()) is None
    assert simulate([], policy=ExitPolicy(), cost=CostModel()) is None


def test_unusable_rows_are_dropped_not_treated_as_a_crash():
    """A null price is missing data, not a price of zero."""
    points = series((0, 1.0, 100_000.0), (300, 1.5, 100_000.0))
    points.insert(1, {"mint": "MINT", "age_seconds": 100, "price_usd": None,
                      "market_cap_usd": None, "liquidity_usd": None})
    trade = simulate(points, policy=ExitPolicy(take_profit_x=None), cost=CostModel(trade_usd=100.0))
    assert trade is not None
    assert trade.observations == 2
    assert trade.gross_return_pct == pytest.approx(0.5)


def test_entry_after_last_observation_returns_none():
    points = series((0, 1.0, 100_000.0), (300, 1.5, 100_000.0))
    assert simulate(points, policy=ExitPolicy(), cost=CostModel(), entry_age_s=9_999.0) is None


def test_unobserved_gap_is_reported():
    """The reader must be able to see how blind the simulation was."""
    trade = simulate(
        series((0, 1.0, 100_000.0), (300, 1.1, 100_000.0), (21_600, 1.2, 100_000.0)),
        policy=ExitPolicy(stop_pct=0.9, take_profit_x=None),
        cost=CostModel(trade_usd=100.0),
    )
    assert trade is not None
    assert trade.max_unobserved_gap_s == 21_300


def test_collapsing_liquidity_makes_the_exit_ruinous():
    """A rug is not just a price fall: the pool that has to absorb the sell is gone."""
    healthy = simulate(
        series((0, 1.0, 100_000.0), (300, 0.5, 100_000.0)),
        policy=ExitPolicy(stop_pct=0.4, take_profit_x=None),
        cost=CostModel(trade_usd=500.0),
    )
    rugging = simulate(
        series((0, 1.0, 100_000.0), (300, 0.5, 2_000.0)),
        policy=ExitPolicy(stop_pct=0.4, take_profit_x=None),
        cost=CostModel(trade_usd=500.0),
    )
    assert healthy is not None and rugging is not None
    assert rugging.net_return_pct < healthy.net_return_pct
    assert rugging.sell_slippage_pct > healthy.sell_slippage_pct


def test_simulation_is_deterministic():
    """No RNG anywhere: a backtest that changes between runs cannot inform a decision."""
    points = series((0, 1.0, 50_000.0), (300, 1.4, 60_000.0), (900, 0.8, 40_000.0))
    runs = {
        simulate(points, policy=ExitPolicy(), cost=CostModel(trade_usd=500.0)).net_return_pct
        for _ in range(5)
    }
    assert len(runs) == 1
    assert all(math.isfinite(r) for r in runs)
