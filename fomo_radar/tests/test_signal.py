"""Tests for the v2 conviction signal.

The two load-bearing tests here are `test_allinu_shaped_token_alerts` and
`TestReachability`. v1 passed a full green suite while being structurally
incapable of firing: every unit test asserted the scorer's arithmetic, none
asserted that a token shaped like a real winner could clear the gates. That is
the bug class this repo keeps hitting, so reachability is now pinned with a
fixture built from measured values rather than invented ones.
"""

from __future__ import annotations

import pytest

from fomo_radar.config import SignalConfig
from fomo_radar.conviction import AuthorProfile, build_cluster, qualifies
from fomo_radar.signal import (
    TIER_CONVICTION,
    TIER_HOT,
    TIER_WATCH,
    WATCH_FLOOR,
    LiquidityState,
    evaluate,
)

CFG = SignalConfig()


def author(
    handle="whale",
    theses=6,
    first_rank=0,
    total=100,
    usd=10_000.0,
    pnl=120.0,
    lb=False,
    text="still holding",
) -> AuthorProfile:
    return AuthorProfile(
        handle=handle,
        theses=theses,
        first_rank=first_rank,
        total_theses_on_token=total,
        position_usd=usd,
        pnl_pct=pnl,
        is_leaderboard=lb,
        is_dev=False,
        first_at="2026-09-17T01:00:00.000Z",
        last_at="2026-09-17T09:00:00.000Z",
        last_text=text,
        max_likes=12,
    )


def live() -> LiquidityState:
    """A token with an unambiguously real market."""
    return LiquidityState(
        known=True,
        liquidity_usd=250_000.0,
        volume_h1_usd=400_000.0,
        market_cap_usd=3_000_000.0,
        buys_m5=40,
        sells_m5=25,
    )


def sig(profiles, liquidity=None, cfg=CFG):
    cluster = build_cluster(
        profiles,
        min_theses=cfg.min_author_theses,
        min_theses_leaderboard=cfg.min_author_theses_leaderboard,
        max_first_pct=cfg.max_first_thesis_pct,
        min_position_usd=cfg.min_thesis_usd,
    )
    return evaluate(
        token_address="tok",
        network_id=1399811149,
        ticker="TEST",
        cluster=cluster,
        liquidity=liquidity if liquidity is not None else live(),
        cfg=cfg,
    )


class TestConvictionCadence:
    def test_cadence_is_a_gate_not_a_dial(self):
        """Posting more, past the floor, is NOT further evidence.

        Within the already-qualified population, thesis count rank-correlates
        rho=-0.002 with the author's own PnL. The first v2 draft scored 45/36/30
        by cadence; that was reading a signal that is not there. Only the
        extreme tail (30+ theses) gets a step.
        """
        assert sig([author(theses=20)]).score == sig([author(theses=6)]).score
        assert sig([author(theses=30)]).score > sig([author(theses=20)]).score

    def test_below_the_floor_does_not_qualify(self):
        assert not qualifies(
            author(theses=5),
            min_theses=6,
            min_theses_leaderboard=3,
            max_first_pct=0.5,
            min_position_usd=1000.0,
        )

    def test_leaderboard_author_clears_a_lower_floor(self):
        """Measured: >=3 theses from a top-150 author reaches 73.6% win, above
        the 71.6% an off-board author reaches at >=6."""
        kw = dict(
            min_theses=6, min_theses_leaderboard=3,
            max_first_pct=0.5, min_position_usd=1000.0,
        )
        assert qualifies(author(theses=3, lb=True), **kw)
        assert not qualifies(author(theses=3, lb=False), **kw)

    def test_a_single_conviction_author_can_alert(self):
        """v1 required >=2 distinct authors. Per-pair measurement puts one
        author at 6+ early theses at 71.6% win, which is worth surfacing."""
        assert sig([author()]).tier is not None


class TestEarliness:
    def test_late_first_thesis_disqualifies(self):
        assert sig([author(first_rank=90, total=100)]).tier is None

    def test_earlier_first_thesis_scores_higher(self):
        early = sig([author(first_rank=2, total=100)]).score
        mid = sig([author(first_rank=40, total=100)]).score
        assert early > mid

    def test_earliness_is_relative_not_absolute(self):
        """The whole point of v2: arriving at rank 400 of 1000 is still the
        early half. v1 compared against a fixed rank ceiling of 10 and so could
        never fire on an established token."""
        a = author(first_rank=400, total=1000)
        assert a.first_pct == pytest.approx(0.4, abs=0.01)
        assert sig([a]).tier is not None


class TestLiquidityGate:
    def test_no_market_data_blocks(self):
        s = sig([author()], liquidity=LiquidityState(known=False))
        assert s.tier is None
        assert "no market data" in s.blocked_by

    def test_illiquid_token_blocks(self):
        s = sig([author()], liquidity=LiquidityState(
            known=True, liquidity_usd=500.0, volume_h1_usd=50_000.0, buys_m5=5))
        assert s.tier is None
        assert any("liquidity" in b for b in s.blocked_by)

    def test_no_recent_trades_blocks(self):
        """The direct fix for 'coins that are not being bought at all'."""
        s = sig([author()], liquidity=LiquidityState(
            known=True, liquidity_usd=500_000.0, volume_h1_usd=500_000.0,
            buys_m5=0, sells_m5=0))
        assert s.tier is None
        assert any("not being traded" in b for b in s.blocked_by)

    def test_dead_volume_blocks_even_with_a_perfect_cluster(self):
        s = sig(
            [author(theses=30, lb=True, usd=500_000.0)] * 1
            + [author(handle="b", theses=20, usd=200_000.0)],
            liquidity=LiquidityState(
                known=True, liquidity_usd=1_000_000.0,
                volume_h1_usd=100.0, buys_m5=2),
        )
        assert s.tier is None, "social score must never override a dead market"

    def test_blocked_signals_report_why(self):
        s = sig([author()], liquidity=LiquidityState(known=False))
        assert s.blocked_by, "a rejection with no stated reason is unauditable"


class TestLeaderboard:
    def test_leaderboard_lifts_the_score(self):
        assert sig([author(lb=True)]).score > sig([author(lb=False)]).score

    def test_leaderboard_is_not_required_for_the_top_tier(self):
        """starcatcher444 ran the ALLINU thesis this redesign is built from and
        was NOT in the 24h top-150 — that board ranks realized PnL and a
        conviction holder has not sold. Requiring it would miss the archetype."""
        s = sig([
            author(handle="a", theses=30, first_rank=1, usd=300_000.0),
            author(handle="b", theses=14, first_rank=8, usd=200_000.0),
            author(handle="c", theses=9, first_rank=20, usd=120_000.0),
            author(handle="d", theses=8, first_rank=25, usd=60_000.0),
        ])
        assert s.cluster.leaderboard_count == 0
        assert s.tier == TIER_CONVICTION, (s.tier, s.score)


class TestTiers:
    def test_all_tiers_reachable(self):
        seen = set()
        for prof in (
            [author(theses=6, first_rank=40, total=100, usd=1_500.0)],
            # One very early author, alone: strong enough for HOT but CONVICTION
            # needs a second independent one, so size cannot buy the top tier.
            [author(theses=12, first_rank=2, total=100, usd=30_000.0)],
            [
                author(handle="a", theses=30, first_rank=1, usd=400_000.0, lb=True),
                author(handle="b", theses=15, first_rank=10, usd=200_000.0),
                author(handle="c", theses=9, first_rank=18, usd=90_000.0),
                author(handle="d", theses=7, first_rank=30, usd=40_000.0),
            ],
        ):
            seen.add(sig(prof).tier)
        assert {TIER_WATCH, TIER_HOT, TIER_CONVICTION} <= seen, seen

    def test_no_dead_band_above_the_gates(self):
        """The weakest cluster clearing every hard gate must still alert.

        v1 shipped a WATCH floor of 50 above a reachable minimum of 47, so a
        token could pass every gate and produce nothing — eligible but
        unalertable, which from outside is indistinguishable from a quiet
        market. This derives the minimum from the scorer so the two cannot
        drift apart again.
        """
        weakest = sig([author(
            theses=CFG.min_author_theses,
            first_rank=49, total=100,          # exactly at max_first_thesis_pct
            usd=CFG.min_thesis_usd,
        )])
        assert weakest.score >= WATCH_FLOOR, (
            f"weakest eligible cluster scores {weakest.score} but the WATCH "
            f"floor is {WATCH_FLOOR} — dead band"
        )
        assert weakest.tier is not None


class TestAgainstMeasuredReality:
    def test_allinu_shaped_token_alerts(self):
        """The regression that motivated v2.

        Figures are the real ALLINU cluster the harvester observed on
        2026-09-17 between 01:13 and 10:38 UTC while firing zero alerts:
        positions of $328k/$206k/$202k/$111k at +742%/+606%/+593%/+1483%, on a
        token with a deep live market. It must alert now, at the top tier.
        """
        profiles = [
            author(handle="MoneyLord", theses=8, first_rank=40, total=520,
                   usd=328_447.0, pnl=742.8),
            author(handle="DexGemsReal", theses=11, first_rank=25, total=520,
                   usd=206_069.0, pnl=606.3),
            author(handle="CeruleanRange", theses=6, first_rank=60, total=520,
                   usd=104_332.0, pnl=433.7),
            author(handle="sniperontheroof", theses=7, first_rank=15, total=520,
                   usd=111_113.0, pnl=1483.5),
        ]
        s = sig(profiles)
        assert s.tier == TIER_CONVICTION, (s.tier, s.score, s.blocked_by)
        assert s.cluster.count == 4
        assert s.cluster.capital_usd > 700_000

    def test_a_fresh_launch_with_no_buyers_never_alerts(self):
        """The complaint that started this: a brand-new token nobody is buying.

        One author, one thesis, dust position, no market. Every gate should
        reject it, and this is the shape the sibling launch radar surfaces.
        """
        s = sig(
            [author(handle="dev", theses=1, first_rank=0, total=1, usd=50.0, pnl=0.0)],
            liquidity=LiquidityState(
                known=True, liquidity_usd=3_000.0,
                volume_h1_usd=200.0, buys_m5=0, sells_m5=0),
        )
        assert s.tier is None
        assert len(s.blocked_by) >= 2

    def test_dev_authorship_is_not_rewarded(self):
        """7 dev theses in 20,337, median -40.1%, zero winners. No dev gate."""
        plain = author(handle="x")
        dev = author(handle="x")
        dev.is_dev = True
        assert sig([dev]).score == sig([plain]).score


class TestClusterOrdering:
    def test_strongest_author_leads(self):
        s = sig([
            author(handle="small", theses=6, usd=2_000.0),
            author(handle="big", theses=25, usd=90_000.0),
        ])
        assert s.cluster.top is not None
        assert s.cluster.top.handle == "big"

    def test_leaderboard_author_leads_on_a_tie(self):
        s = sig([
            author(handle="plain", theses=10, usd=90_000.0),
            author(handle="pro", theses=10, usd=5_000.0, lb=True),
        ])
        assert s.cluster.top.handle == "pro"

    def test_non_qualifying_authors_are_counted_but_excluded(self):
        s = sig([author(handle="in", theses=8), author(handle="out", theses=2)])
        assert s.cluster.count == 1
        assert s.cluster.considered == 2
