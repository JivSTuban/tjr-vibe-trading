"""Scoring tests, with the renormalization rule pinned hardest.

The coverage behaviour is the single most load-bearing decision in the package:
if missing components scored zero instead of being excluded, the PRD's own ULTRA
gate could never fire in Phase 1. These tests exist so that cannot regress
silently.
"""

from __future__ import annotations

import pytest

from memecoin_radar.features import compute_flow
from memecoin_radar.scoring import saturating, weighted_score
from memecoin_radar.scoring.moon import WEIGHTS as MOON_WEIGHTS
from memecoin_radar.scoring.moon import score_moon
from memecoin_radar.scoring.rug import score_rug
from memecoin_radar.sources.helius import HolderConcentration, TokenAuthorities

from .conftest import fetched_metadata, make_snapshots


# ------------------------------------------------------------------ primitives

def test_weighted_score_excludes_missing_and_renormalizes():
    weights = {"a": 0.5, "b": 0.5}
    sb = weighted_score(weights, {"a": 80.0, "b": None})
    # 80 alone, not 40: the missing half is excluded, not scored zero.
    assert sb.score == 80.0
    assert sb.coverage == 0.5
    assert sb.missing == ["b"]


def test_weighted_score_distinguishes_missing_from_zero():
    weights = {"a": 0.5, "b": 0.5}
    missing = weighted_score(weights, {"a": 80.0, "b": None})
    measured_zero = weighted_score(weights, {"a": 80.0, "b": 0.0})
    assert missing.score == 80.0
    assert measured_zero.score == 40.0
    # Excluding a component lowers coverage; scoring it zero does not.
    assert missing.coverage < measured_zero.coverage


def test_weighted_score_all_missing_is_zero_with_zero_coverage():
    sb = weighted_score({"a": 1.0}, {"a": None})
    assert sb.score == 0.0 and sb.coverage == 0.0


def test_saturating_is_monotonic_and_hits_50_at_midpoint():
    assert saturating(100.0, 100.0) == pytest.approx(50.0, abs=0.01)
    assert saturating(10.0, 100.0) < saturating(50.0, 100.0) < saturating(500.0, 100.0)
    assert saturating(0.0, 100.0) == 0.0
    assert 0.0 <= saturating(10**9, 100.0) <= 100.0


def test_moon_weights_match_the_prd():
    assert MOON_WEIGHTS["volume_acceleration"] == 0.20
    assert MOON_WEIGHTS["smart_money"] == 0.20
    assert sum(MOON_WEIGHTS.values()) == pytest.approx(1.0)


# ----------------------------------------------------------------------- moon

def test_moon_reports_low_coverage_on_a_fresh_launch(candidate):
    """At second zero almost nothing is measurable, and the score must say so."""
    feat = compute_flow([])
    sb = score_moon(candidate, feat, smart_wallets={})
    assert sb.coverage < 0.5
    assert "smart_money" in sb.missing
    assert "social_velocity" in sb.missing


def test_moon_coverage_rises_once_flow_exists(candidate):
    at_zero = score_moon(candidate, compute_flow([]), smart_wallets={})

    candidate.metadata = fetched_metadata()
    candidate.snapshots = make_snapshots(
        candidate.mint, [(15, 100.0, 5, 1), (30, 400.0, 20, 3), (60, 1600.0, 60, 8)]
    )
    feat = compute_flow(candidate.snapshots)
    sb = score_moon(candidate, feat, smart_wallets={})

    assert sb.coverage > at_zero.coverage
    assert sb.coverage >= 0.5
    assert sb.score > 0
    assert "volume_acceleration" in sb.components


def test_moon_coverage_ceiling_in_phase_1(candidate):
    """Documents the hard ceiling: 40% of Moon weight is unmeasurable in Phase 1.

    smart_money (20%), social_velocity (15%), and cross_platform (5%) all need
    later PRD phases, so full coverage is unreachable today. This is why the
    ULTRA gate checks coverage separately instead of trusting the score alone.
    """
    candidate.metadata = fetched_metadata()
    candidate.snapshots = make_snapshots(
        candidate.mint, [(15, 100.0, 5, 1), (30, 400.0, 20, 3), (60, 1600.0, 60, 8)]
    )
    sb = score_moon(candidate, compute_flow(candidate.snapshots), smart_wallets={})
    assert sb.coverage <= 0.60
    assert set(sb.missing) >= {"smart_money", "social_velocity", "cross_platform"}


def test_moon_rewards_acceleration_over_size(candidate):
    """Same total volume, different shape: accelerating must score higher."""
    accelerating = make_snapshots(
        candidate.mint, [(15, 100.0, 2, 0), (30, 300.0, 10, 1), (60, 1500.0, 60, 4)]
    )
    decelerating = make_snapshots(
        candidate.mint, [(15, 1100.0, 50, 2), (30, 1400.0, 58, 4), (60, 1500.0, 60, 6)]
    )
    fast = score_moon(candidate, compute_flow(accelerating), {})
    slow = score_moon(candidate, compute_flow(decelerating), {})
    assert fast.score > slow.score


def test_moon_smart_money_is_missing_without_a_watchlist(candidate):
    feat = compute_flow(make_snapshots(candidate.mint, [(15, 10.0, 1, 0), (30, 90.0, 6, 0)]))
    no_list = score_moon(candidate, feat, smart_wallets={})
    assert "smart_money" in no_list.missing

    candidate.smart_wallets = {"W1", "W2"}
    with_list = score_moon(candidate, feat, smart_wallets={"W1": 80.0, "W2": 70.0})
    assert "smart_money" not in with_list.missing
    assert with_list.score > no_list.score


def test_moon_narrative_missing_until_metadata_lands(candidate):
    feat = compute_flow([])
    assert "narrative" in score_moon(candidate, feat, {}).missing
    candidate.metadata = fetched_metadata()
    assert "narrative" not in score_moon(candidate, feat, {}).missing


# ------------------------------------------------------------------------ rug

def test_rug_flags_live_mint_authority(candidate):
    feat = compute_flow([])
    safe = score_rug(
        candidate, feat, deployer_launches=1, deployer_rugs=0,
        authorities=TokenAuthorities(available=True),
    )
    unsafe = score_rug(
        candidate, feat, deployer_launches=1, deployer_rugs=0,
        authorities=TokenAuthorities(mint_authority="ABC", available=True),
    )
    assert unsafe.score > safe.score
    assert any("mint authority" in r for r in unsafe.reasons)


def test_rug_penalizes_serial_deployers(candidate):
    feat = compute_flow([])
    once = score_rug(candidate, feat, deployer_launches=1, deployer_rugs=0)
    factory = score_rug(candidate, feat, deployer_launches=40, deployer_rugs=0)
    assert factory.score > once.score


def test_rug_prior_rugs_dominate(candidate):
    feat = compute_flow([])
    sb = score_rug(candidate, feat, deployer_launches=3, deployer_rugs=2)
    assert sb.components["deployer_history"] >= 60.0
    assert any("rugged" in r for r in sb.reasons)


def test_rug_flags_holder_concentration(candidate):
    feat = compute_flow([])
    sb = score_rug(
        candidate, feat, deployer_launches=1, deployer_rugs=0,
        holders=HolderConcentration(top10_pct=85.0, available=True),
    )
    assert sb.components["top_holder_concentration"] > 80.0


def test_rug_marks_structural_checks_missing_without_helius(candidate):
    sb = score_rug(candidate, compute_flow([]), deployer_launches=1, deployer_rugs=0)
    assert "token_authorities" in sb.missing
    assert "top_holder_concentration" in sb.missing
    assert sb.coverage < 1.0


def test_rug_and_moon_are_independent(candidate):
    """A dangerous token can still have a strong Moon score, by design."""
    candidate.metadata = fetched_metadata()
    # Creator took a fifth of supply at launch, the classic dump setup.
    candidate.launch.initial_buy = 200_000_000.0
    candidate.snapshots = make_snapshots(
        candidate.mint, [(15, 100.0, 5, 0), (30, 900.0, 40, 2), (60, 5000.0, 150, 5)]
    )
    feat = compute_flow(candidate.snapshots)
    moon = score_moon(candidate, feat, {})
    rug = score_rug(
        candidate, feat, deployer_launches=50, deployer_rugs=3,
        authorities=TokenAuthorities(mint_authority="X", freeze_authority="Y", available=True),
        holders=HolderConcentration(top10_pct=92.0, available=True),
    )
    assert moon.score > 40.0
    assert rug.score > 70.0
