"""Tests for the ENTER NOW gate: the only thing that gets notified.

The gate exists because a tier says a token is interesting while a notification
claims money should move. The three tests that matter most are the three ways
the old behaviour sent an unactionable alert: too late in the social timeline,
too long after the thesis was posted, and into a pool too thin to trade.
"""

from __future__ import annotations

from fomo_radar.config import SignalConfig
from fomo_radar.conviction import ConvictionCluster
from fomo_radar.signal import (
    TIER_CONVICTION,
    TIER_ENTER,
    TIER_PRIORITY,
    LiquidityState,
    TokenSignal,
    entry_gate,
)


def make_signal(
    *,
    rank: int = 0,
    liquidity_usd: float = 250_000.0,
    tier: str | None = TIER_CONVICTION,
    blocked: list[str] | None = None,
) -> TokenSignal:
    return TokenSignal(
        token_address="MINT",
        network_id=1399811149,
        ticker="TEST",
        cluster=ConvictionCluster(),
        liquidity=LiquidityState(
            known=True,
            liquidity_usd=liquidity_usd,
            volume_h1_usd=50_000.0,
            market_cap_usd=1_000_000.0,
            buys_m5=10,
            sells_m5=5,
            price_usd=0.001,
        ),
        thesis_rank=rank,
        distinct_authors=3,
        leaderboard_authors=0,
        total_usd=10_000.0,
        tier=tier,
        score=60.0,
        blocked_by=blocked or [],
    )


def test_a_fresh_early_liquid_signal_is_an_entry():
    verdict = entry_gate(make_signal(), thesis_age_s=120.0)
    assert verdict.enter
    assert not verdict.blocked_by
    assert verdict.round_trip_pct > 0


def test_a_stale_thesis_is_never_an_entry():
    """The gate that did not exist before, and the one that kills $CATE-shaped alerts.

    Discovery evaluates the NEWEST thesis on a liquid launch, which can be hours
    old. Everything else about it can look perfect.
    """
    verdict = entry_gate(make_signal(), thesis_age_s=4 * 3600.0)
    assert not verdict.enter
    assert any("old" in b for b in verdict.blocked_by)


def test_a_late_rank_is_never_an_entry():
    verdict = entry_gate(make_signal(rank=400), thesis_age_s=60.0)
    assert not verdict.enter
    assert any("entry window" in b for b in verdict.blocked_by)


def test_a_pool_too_thin_to_trade_is_never_an_entry():
    """A $15k pool costs 13.5% round trip at $500. That is not a trade."""
    verdict = entry_gate(make_signal(liquidity_usd=15_000.0), thesis_age_s=60.0)
    assert not verdict.enter
    assert any("round trip" in b for b in verdict.blocked_by)
    assert verdict.round_trip_pct > 0.06


def test_a_deep_pool_clears_the_execution_budget():
    verdict = entry_gate(make_signal(liquidity_usd=1_000_000.0), thesis_age_s=60.0)
    assert verdict.enter
    assert verdict.round_trip_pct < 0.06


def test_entry_is_a_subset_of_alerting():
    """No path may let the entry gate overrule a hard gate `evaluate` applied."""
    verdict = entry_gate(
        make_signal(tier=None, blocked=["1h volume $12 < $5,000"]),
        thesis_age_s=10.0,
    )
    assert not verdict.enter
    assert "1h volume $12 < $5,000" in verdict.blocked_by


def test_unknown_liquidity_blocks_rather_than_passing():
    sig = make_signal()
    sig.liquidity = LiquidityState(known=False)
    verdict = entry_gate(sig, thesis_age_s=10.0)
    assert not verdict.enter
    assert any("liquidity" in b for b in verdict.blocked_by)


def test_a_refusal_always_says_why():
    """A silent radar must be distinguishable from a broken one."""
    for sig, age in (
        (make_signal(rank=400), 60.0),
        (make_signal(), 99_999.0),
        (make_signal(liquidity_usd=1_000.0), 60.0),
        (make_signal(tier=None), 60.0),
    ):
        verdict = entry_gate(sig, thesis_age_s=age)
        assert not verdict.enter
        assert verdict.blocked_by, "a refusal with no reason is unauditable"


def test_size_tightens_the_liquidity_a_token_needs():
    """Impact is linear in size, so a bigger position demands a deeper pool."""
    sig = make_signal(liquidity_usd=60_000.0)
    small = entry_gate(sig, thesis_age_s=60.0, cfg=SignalConfig(entry_size_usd=250.0))
    large = entry_gate(sig, thesis_age_s=60.0, cfg=SignalConfig(entry_size_usd=5_000.0))
    assert small.enter
    assert not large.enter
    assert large.round_trip_pct > small.round_trip_pct


def test_enter_outranks_every_tier_so_a_token_cannot_realert_forever():
    """`best_tier_so_far` returns the delivered tier; if ENTER were absent from
    TIER_PRIORITY it would read as None and the token would alert on every
    subsequent thesis."""
    assert TIER_ENTER in TIER_PRIORITY
    assert TIER_PRIORITY[TIER_ENTER] == min(TIER_PRIORITY.values())


def test_unparseable_thesis_age_fails_closed():
    """Unknown freshness must never read as 'just happened'."""
    verdict = entry_gate(make_signal(), thesis_age_s=float("inf"))
    assert not verdict.enter
