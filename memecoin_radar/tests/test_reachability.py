"""Guards against silently unreachable alert tiers.

This file exists because of a bug caught during the first build: the coverage
gates were set above the coverage actually achievable in Phase 1, which made HOT
and ULTRA impossible to fire. The radar would have run, logged, recorded, and
looked healthy while never once escalating.

That failure mode is invisible in a live run, so it is pinned here instead.
"""

from __future__ import annotations

import pytest

from memecoin_radar.config import Thresholds
from memecoin_radar.features import compute_flow
from memecoin_radar.scoring.moon import WEIGHTS as MOON_WEIGHTS
from memecoin_radar.scoring.moon import score_moon
from memecoin_radar.scoring.rug import score_rug
from memecoin_radar.alerts import decide

from .conftest import fetched_metadata, make_snapshots

# Components a free Phase 1 deployment can actually measure.
PHASE1_MEASURABLE = {
    "volume_acceleration",
    "unique_buyer_acceleration",
    "liquidity_quality",
    "narrative",
    "early_entry",
}

# Adding the Phase 2 wallet leaderboard unlocks smart money.
PHASE2_MEASURABLE = PHASE1_MEASURABLE | {"smart_money"}


def _coverage_of(keys: set[str]) -> float:
    return sum(MOON_WEIGHTS[k] for k in keys)


def test_phase1_coverage_ceiling_is_what_we_think():
    assert _coverage_of(PHASE1_MEASURABLE) == pytest.approx(0.50)


def test_thresholds_are_reachable():
    """Every coverage gate must sit below the coverage Phase 1 can reach."""
    th = Thresholds()
    ceiling = _coverage_of(PHASE1_MEASURABLE)
    assert th.min_coverage_hot < ceiling, "HOT is unreachable with Phase 1 data"
    assert th.min_coverage_ultra < ceiling, "ULTRA is unreachable with Phase 1 data"


def _score_launch(candidate, series, *, mcap: float, liquidity: float):
    candidate.metadata = fetched_metadata(
        "the frog that ate the pond", twitter="https://x.com/frog"
    )
    snaps = make_snapshots(candidate.mint, series)
    for snap in snaps:
        snap.market_cap_usd = mcap
        snap.liquidity_usd = liquidity
    candidate.snapshots = snaps
    feat = compute_flow(snaps)
    candidate.moon = score_moon(candidate, feat, smart_wallets={})
    candidate.rug = score_rug(candidate, feat, deployer_launches=1, deployer_rugs=0)
    return candidate


def test_hot_fires_on_a_strong_launch(candidate):
    """A strong launch must still be able to reach HOT under the live gates."""
    _score_launch(
        candidate,
        [(15, 200.0, 12, 0), (30, 2_000.0, 90, 2), (60, 18_000.0, 400, 9)],
        mcap=18_000.0,
        liquidity=30_000.0,
    )
    tiers = [a.alert_type for a in decide(candidate, Thresholds())]
    assert candidate.moon.score > Thresholds().hot_moon, (
        f"moon only reached {candidate.moon.score}"
    )
    assert "HOT" in tiers, f"expected HOT, got {tiers}"


def test_ultra_actually_fires_on_an_exceptional_launch(candidate):
    """The urgent tier must be reachable, or it is decoration.

    This is the guard against the calibration swinging so far toward silence
    that ULTRA becomes unreachable, which is the same class of bug as the
    coverage gate that originally made HOT impossible.
    """
    _score_launch(
        candidate,
        [(15, 500.0, 30, 0), (30, 6_000.0, 220, 3), (60, 60_000.0, 1_200, 15)],
        mcap=9_000.0,
        liquidity=60_000.0,
    )
    tiers = [a.alert_type for a in decide(candidate, Thresholds())]
    assert candidate.moon.score > Thresholds().ultra_moon, (
        f"moon only reached {candidate.moon.score}"
    )
    assert "ULTRA" in tiers, f"expected ULTRA, got {tiers}"


def test_phase2_raises_the_ceiling(candidate):
    """Documents what shipping the wallet leaderboard buys: coverage 0.50 -> 0.70."""
    assert _coverage_of(PHASE2_MEASURABLE) == pytest.approx(0.70)
