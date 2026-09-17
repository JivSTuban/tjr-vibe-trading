"""Tests for the v3 entry-clean signal.

The load-bearing tests here are the two REGRESSIONS IN OPPOSITE DIRECTIONS,
because this signal has now failed both ways:

* `test_early_liquid_token_alerts` — v1's rule was correct and fired zero alerts
  in 17 hours. A token that is genuinely early and tradeable must alert.
* `test_cate_shaped_trophy_does_not_alert` / `test_allinu_at_rank_500_...` — v2
  fired, on tokens that had already run. A token deep in its thesis timeline
  must NOT alert, however much money is visibly in it.

A green suite that only checks arithmetic is what let both versions ship, so
these assert reachability and un-reachability against real observed numbers.
"""

from __future__ import annotations

from fomo_radar.config import SignalConfig
from fomo_radar.conviction import AuthorProfile, build_cluster
from fomo_radar.signal import (
    TIER_CONVICTION,
    TIER_HOT,
    TIER_WATCH,
    WATCH_FLOOR,
    LiquidityState,
    evaluate,
)

CFG = SignalConfig()


def author(handle="whale", theses=1, first_rank=0, total=20, usd=10_000.0,
           pnl=0.0, lb=False, text="early") -> AuthorProfile:
    return AuthorProfile(
        handle=handle, theses=theses, first_rank=first_rank,
        total_theses_on_token=total, position_usd=usd, pnl_pct=pnl,
        is_leaderboard=lb, is_dev=False,
        first_at="2026-09-17T01:00:00.000Z", last_at="2026-09-17T02:00:00.000Z",
        last_text=text, max_likes=3,
    )


def live() -> LiquidityState:
    """A token with an unambiguously real market."""
    return LiquidityState(
        known=True, liquidity_usd=250_000.0, volume_h1_usd=400_000.0,
        market_cap_usd=3_000_000.0, buys_m5=40, sells_m5=25,
    )


def sig(*, rank, profiles=None, liquidity=None, largest=10_000.0, cfg=CFG):
    profiles = profiles if profiles is not None else [author()]
    cluster = build_cluster(
        profiles, min_theses=1, min_theses_leaderboard=1,
        max_first_pct=1.0, min_position_usd=0.0,
    )
    return evaluate(
        token_address="tok", network_id=1399811149, ticker="TEST",
        thesis_rank=rank, cluster=cluster,
        liquidity=liquidity if liquidity is not None else live(),
        largest_usd=largest, cfg=cfg,
    )


class TestEarlinessIsTheGate:
    def test_first_thesis_is_top_tier(self):
        s = sig(rank=0)
        assert s.tier == TIER_CONVICTION
        assert "FIRST thesis" in " ".join(s.reasons)

    def test_score_decays_with_rank(self):
        scores = [sig(rank=r).score for r in (0, 3, 10, 19)]
        assert scores == sorted(scores, reverse=True), scores

    def test_past_the_window_never_alerts(self):
        s = sig(rank=CFG.max_thesis_rank)
        assert s.tier is None
        assert any("past the early window" in b for b in s.blocked_by)

    def test_the_window_edge_is_inclusive_below(self):
        assert sig(rank=CFG.max_thesis_rank - 1).tier is not None

    def test_rank_is_absolute_not_normalised(self):
        """v2 used first_rank/total_theses; the denominator is the token's
        EVENTUAL thesis count, which is future information. Rank 400 must be
        rejected no matter how long the token's timeline eventually gets."""
        for total in (500, 5_000):
            s = sig(rank=400, profiles=[author(first_rank=400, total=total)])
            assert s.tier is None, total


class TestLiquidityGate:
    def test_no_market_data_blocks(self):
        s = sig(rank=0, liquidity=LiquidityState(known=False))
        assert s.tier is None
        assert "no market data" in s.blocked_by

    def test_illiquid_blocks(self):
        s = sig(rank=0, liquidity=LiquidityState(
            known=True, liquidity_usd=500.0, volume_h1_usd=50_000.0, buys_m5=5))
        assert s.tier is None
        assert any("liquidity" in b for b in s.blocked_by)

    def test_no_recent_trades_blocks(self):
        s = sig(rank=0, liquidity=LiquidityState(
            known=True, liquidity_usd=500_000.0, volume_h1_usd=500_000.0,
            buys_m5=0, sells_m5=0))
        assert s.tier is None
        assert any("not being traded" in b for b in s.blocked_by)

    def test_earliness_never_overrides_a_dead_market(self):
        s = sig(rank=0, liquidity=LiquidityState(
            known=True, liquidity_usd=1_000.0, volume_h1_usd=10.0, buys_m5=0))
        assert s.tier is None

    def test_rejections_state_a_reason(self):
        s = sig(rank=0, liquidity=LiquidityState(known=False))
        assert s.blocked_by, "a rejection with no stated reason is unauditable"


class TestLookAheadFeaturesAreGone:
    def test_thesis_count_does_not_change_the_score(self):
        """v2 gated on an author's thesis count. It accumulates only because the
        token ran: at PoorGoat_'s thesis #1 you could not know he would post 435
        more. Within the qualified population it carried rho=-0.002."""
        few = sig(rank=2, profiles=[author(handle="a", theses=1)])
        many = sig(rank=2, profiles=[author(handle="a", theses=436)])
        assert few.score == many.score

    def test_author_pnl_does_not_change_the_score(self):
        """PnL is the outcome. Scoring it is circular."""
        flat = sig(rank=2, profiles=[author(handle="a", pnl=0.0)])
        moon = sig(rank=2, profiles=[author(handle="a", pnl=1735.0)])
        assert flat.score == moon.score

    def test_leaderboard_does_not_change_the_score(self):
        """rho=-0.057, and negative once earliness is controlled for: unknown
        authors in a token's first 20 theses medianed +170.2% / 81.3% win vs
        +88.8% / 78.3% for top-150 traders in the same window."""
        plain = sig(rank=2, profiles=[author(handle="a", lb=False)])
        pro = sig(rank=2, profiles=[author(handle="a", lb=True)])
        assert plain.score == pro.score

    def test_leaderboard_is_still_reported(self):
        s = sig(rank=2, profiles=[author(handle="a", lb=True)])
        assert "not scored" in " ".join(s.reasons)
        assert s.leaderboard_authors == 1


class TestTiers:
    def test_all_tiers_reachable(self):
        seen = {sig(rank=r).tier for r in (0, 3, 15)}
        assert {TIER_CONVICTION, TIER_HOT, TIER_WATCH} <= seen, seen

    def test_no_dead_band_above_the_gates(self):
        """The weakest token clearing every hard gate must still alert.

        v1 shipped a WATCH floor of 50 above a reachable minimum of 47, so a
        token could pass every gate and produce nothing — eligible but
        unalertable, indistinguishable from a quiet market from outside.
        """
        weakest = sig(
            rank=CFG.max_thesis_rank - 1,
            profiles=[author(usd=0.0)],
            largest=0.0,
        )
        assert weakest.score >= WATCH_FLOOR, (weakest.score, WATCH_FLOOR)
        assert weakest.tier is not None


class TestAgainstMeasuredReality:
    def test_early_liquid_token_alerts(self):
        """The v1 regression: this shape must fire.

        Modelled on MCOWNPRC, observed live 2026-09-17 — 6 theses, $3.4M
        liquidity, $44M cap. A real market with almost no social footprint, i.e.
        the moment the measurement says to act on.
        """
        s = sig(
            rank=5,
            profiles=[author(handle="early1", usd=40_000.0),
                      author(handle="early2", usd=12_000.0)],
            liquidity=LiquidityState(
                known=True, liquidity_usd=3_456_366.0, volume_h1_usd=120_000.0,
                market_cap_usd=44_452_037.0, buys_m5=30, sells_m5=18),
            largest=40_000.0,
        )
        assert s.tier is not None, (s.score, s.blocked_by)

    def test_cate_shaped_trophy_does_not_alert(self):
        """The v2 regression, from the alert Jiv correctly rejected.

        $CATE: 500 theses, $67M cap, lead author @PoorGoat_ up +1735% after 436
        theses over 333 hours. Enormous visible money — and the move already
        happened. Rank is what disqualifies it, and nothing about the cluster
        may rescue it.
        """
        s = sig(
            rank=436,
            profiles=[
                author(handle="PoorGoat_", theses=436, first_rank=0, total=500,
                       usd=1_926_933.0, pnl=1735.0, lb=True),
                author(handle="bluntz_capital", theses=18, first_rank=160,
                       total=500, usd=1_573_371.0, pnl=60.0, lb=True),
                author(handle="boosteryting", theses=14, first_rank=15,
                       total=500, usd=765_459.0, pnl=946.0, lb=True),
            ],
            liquidity=LiquidityState(
                known=True, liquidity_usd=2_775_886.0, volume_h1_usd=160_591.0,
                market_cap_usd=67_674_203.0, buys_m5=7, sells_m5=3),
            largest=1_926_933.0,
        )
        assert s.tier is None, (s.tier, s.score)
        assert any("past the early window" in b for b in s.blocked_by)

    def test_allinu_at_rank_500_does_not_alert(self):
        """Same shape, the other token v2 fired on. $328k at +742% is evidence
        the run happened, not evidence it is about to."""
        s = sig(
            rank=500,
            profiles=[author(handle="MoneyLord", theses=8, usd=328_447.0,
                             pnl=742.8)],
            liquidity=LiquidityState(
                known=True, liquidity_usd=581_532.0, volume_h1_usd=23_894.0,
                market_cap_usd=18_619_760.0, buys_m5=12, sells_m5=9),
            largest=328_447.0,
        )
        assert s.tier is None

    def test_dev_authorship_is_not_rewarded(self):
        """7 dev theses in 20,337, median -40.1%, zero winners."""
        plain = author(handle="x")
        dev = author(handle="x")
        dev.is_dev = True
        assert sig(rank=1, profiles=[dev]).score == sig(rank=1, profiles=[plain]).score
