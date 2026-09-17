"""Regression tests for the tradeability floor on upside alerts.

Written from an audit, not from a hypothesis. On 2026-09-17 this radar had
delivered 44 upside alerts. Their PEAK liquidity distribution:

    min $2,990 · p25 $3,029 · median $3,257 · p75 $3,419 · max $271,081

That is the pump.fun bonding-curve floor: 37 of the 44 never developed a market
at all, while 7 did (the best reaching $271k liquidity and a $10.6M cap). Every
one of the 44 had passed the flow-evidence check, with a median peak buy count
of 82 — so "someone is buying" was true and useless. A $3k-liquidity token
cannot be exited at any size worth taking.

The floor sits at $15k, inside the gap between $3.4k and $5k, which keeps
exactly the 7 that became real markets.

There is deliberately no market-cap floor; see `_is_tradeable`. Moon scores
early entry, so it rewards a LOW market cap, and gating on cap would fight this
radar's own premise — a new launch is a micro-cap by construction.
"""

from __future__ import annotations

from memecoin_radar.alerts import decide, peak_liquidity
from memecoin_radar.config import Thresholds
from memecoin_radar.models import ScoreBreakdown

from .conftest import make_snapshots

TH = Thresholds()


def _upside(cand, *, liquidity: float, market_cap: float = 4_536.0):
    """A candidate that would alert on every rule EXCEPT tradeability."""
    cand.snapshots = make_snapshots(
        cand.mint, [(15, 500.0, 30, 1), (60, 9_000.0, 120, 8)],
        market_cap_usd=market_cap, liquidity_usd=liquidity,
    )
    cand.moon = ScoreBreakdown(
        score=95.0, coverage=0.50,
        components={"volume_acceleration": 95.0, "early_entry": 95.0},
        reasons=["flow accelerating"],
    )
    cand.rug = ScoreBreakdown(score=5.0, coverage=0.9, reasons=["clean"])
    return cand


class TestTheAuditedDistribution:
    def test_the_median_alert_this_radar_sent_no_longer_fires(self, candidate):
        """Peak liquidity $3,257 — the median of the 44 real upside alerts."""
        tiers = [a.alert_type for a in decide(_upside(candidate, liquidity=3_257.0), TH)]
        assert tiers == [], tiers

    def test_the_p75_alert_no_longer_fires(self, candidate):
        tiers = [a.alert_type for a in decide(_upside(candidate, liquidity=3_419.0), TH)]
        assert tiers == [], tiers

    def test_a_token_that_developed_a_real_market_still_fires(self, candidate):
        """The best of the 44: $271k peak liquidity. Must survive the floor."""
        tiers = [a.alert_type for a in decide(_upside(candidate, liquidity=271_081.0), TH)]
        assert "ULTRA" in tiers, tiers

    def test_the_floor_sits_in_the_observed_gap(self):
        """Between the p75 of the dead cohort and the first real market."""
        assert 3_419.0 < TH.min_alert_liquidity_usd <= 20_000.0


class TestGateMechanics:
    def test_unknown_liquidity_blocks_rather_than_passing(self, candidate):
        """No snapshots means we could not look, which must fail closed.

        Treating absent data as acceptable is how the original bug shipped.
        """
        candidate.snapshots = []
        candidate.moon = ScoreBreakdown(
            score=95.0, coverage=0.50,
            components={"volume_acceleration": 95.0},
        )
        candidate.rug = ScoreBreakdown(score=5.0, coverage=0.9)
        assert [a.alert_type for a in decide(candidate, TH)] == []

    def test_peak_is_used_not_latest(self, candidate):
        """A token judged on whether it EVER became tradeable.

        One stale or thin final snapshot should not veto a name that filled out.
        """
        candidate.snapshots = make_snapshots(
            candidate.mint, [(15, 500.0, 30, 1)], liquidity_usd=90_000.0
        ) + make_snapshots(
            candidate.mint, [(60, 9_000.0, 120, 8)], liquidity_usd=1_000.0
        )
        assert peak_liquidity(candidate) == 90_000.0

    def test_suppression_states_its_reason(self, candidate):
        """A filter that drops names silently is indistinguishable from a broken
        one — the standing rule in this repo."""
        cand = _upside(candidate, liquidity=3_257.0)
        decide(cand, TH)
        assert "peak liquidity" in cand.suppressed_reason

    def test_no_market_cap_floor_exists(self):
        """Pinned deliberately: Moon rewards a low cap, so a cap gate would
        fight the scorer. If someone adds one, this should make them justify it.
        """
        assert not hasattr(TH, "min_alert_mcap_usd")

    def test_a_microcap_with_real_liquidity_still_fires(self, candidate):
        """Low market cap must NOT be disqualifying on its own."""
        tiers = [a.alert_type for a in decide(
            _upside(candidate, liquidity=60_000.0, market_cap=9_000.0), TH)]
        assert "ULTRA" in tiers, tiers


class TestDangerIsStillReported:
    def test_rug_warning_fires_on_an_illiquid_token(self, candidate):
        """The tradeability floor guards UPSIDE claims only.

        A structurally dangerous token is worth flagging precisely while it is
        still tiny, before anyone can be hurt by it.
        """
        cand = _upside(candidate, liquidity=3_000.0)
        cand.rug = ScoreBreakdown(score=95.0, coverage=0.9, reasons=["mint authority live"])
        tiers = [a.alert_type for a in decide(cand, TH)]
        assert tiers == ["RUG_WARNING"], tiers
