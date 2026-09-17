"""Trend Echo tests, anchored on the PRD's own worked example ($BABYFROG vs $FROG)."""

from __future__ import annotations

from datetime import timedelta

from memecoin_radar.features import compute_flow
from memecoin_radar.models import Candidate, LaunchEvent, TrendReference, utcnow
from memecoin_radar.scoring.trend_echo import (
    best_match,
    jaccard,
    score_trend_relation,
    string_similarity,
    tokenize,
)

from .conftest import fetched_metadata, make_snapshots


def _launch(name: str, symbol: str, creator: str = "CREATOR1") -> LaunchEvent:
    return LaunchEvent(
        mint=f"mint-{symbol}",
        name=name,
        symbol=symbol,
        creator=creator,
        signature="sig",
        uri="",
        pool="pump",
        initial_buy=1_000_000.0,
        sol_amount=0.2,
        market_cap_sol=28.0,
        v_sol_in_curve=30.0,
        v_tokens_in_curve=1_000_000_000.0,
    )


def _trend(symbol: str = "FROG", *, state: str = "accelerating", minutes_old: int = 10):
    return TrendReference(
        mint="mint-FROG",
        name="Frog",
        symbol=symbol,
        narrative_tokens=tokenize("frog green pond amphibian"),
        keywords=tokenize("frog"),
        creator="TRENDCREATOR",
        momentum_state=state,
        trend_score=100.0,
        first_seen=utcnow() - timedelta(minutes=minutes_old),
    )


# ------------------------------------------------------------------ similarity

def test_clone_prefix_scores_high():
    """The canonical case: BABYFROG is a derivative of FROG."""
    assert string_similarity("BABYFROG", "FROG") >= 70.0


def test_identical_is_100():
    assert string_similarity("FROG", "frog") == 100.0


def test_unrelated_names_score_low():
    assert string_similarity("Quantum Ledger", "FROG") < 40.0


def test_short_substrings_do_not_trigger_containment():
    """Two-letter overlaps must not read as a clone, or everything matches."""
    assert string_similarity("XY", "XYZABCDEFGH") < 70.0


def test_empty_inputs_are_safe():
    assert string_similarity("", "FROG") == 0.0
    assert string_similarity("FROG", "") == 0.0


def test_jaccard_bounds():
    assert jaccard(set(), {"a"}) == 0.0
    assert jaccard({"a"}, {"a"}) == 1.0


def test_tokenize_drops_meme_stopwords():
    toks = tokenize("The official FROG coin on solana")
    assert "frog" in toks
    assert "coin" not in toks and "solana" not in toks and "the" not in toks


# ---------------------------------------------------------------- relation

def test_clone_of_live_trend_scores_high():
    cand = Candidate(launch=_launch("Baby Frog", "BABYFROG"))
    cand.metadata = fetched_metadata("a baby frog in the pond")
    cand.snapshots = make_snapshots(cand.mint, [(15, 100.0, 8, 0), (30, 900.0, 30, 2)])
    sb = score_trend_relation(cand, _trend(), compute_flow(cand.snapshots))
    assert sb.score >= 70.0


def test_unrelated_launch_scores_low():
    cand = Candidate(launch=_launch("Quantum Ledger", "QLED"))
    cand.metadata = fetched_metadata("institutional settlement infrastructure")
    sb = score_trend_relation(cand, _trend(), compute_flow([]))
    assert sb.score < 45.0


def test_image_similarity_is_always_missing_in_phase_1():
    cand = Candidate(launch=_launch("Baby Frog", "BABYFROG"))
    sb = score_trend_relation(cand, _trend(), compute_flow([]))
    assert "image_logo" in sb.missing
    assert sb.coverage < 1.0


def test_same_deployer_as_trend_is_flagged():
    cand = Candidate(launch=_launch("Frog Two", "FROG2", creator="TRENDCREATOR"))
    sb = score_trend_relation(cand, _trend(), compute_flow([]))
    assert sb.components["creator_relationship"] == 100.0
    assert any("same deployer" in r for r in sb.reasons)


def test_cooling_trend_scores_lower_than_accelerating():
    cand = Candidate(launch=_launch("Baby Frog", "BABYFROG"))
    hot = score_trend_relation(cand, _trend(state="accelerating"), compute_flow([]))
    cold = score_trend_relation(cand, _trend(state="cooling"), compute_flow([]))
    assert hot.score > cold.score


def test_old_trend_decays():
    cand = Candidate(launch=_launch("Baby Frog", "BABYFROG"))
    fresh = score_trend_relation(cand, _trend(minutes_old=5), compute_flow([]))
    stale = score_trend_relation(cand, _trend(minutes_old=300), compute_flow([]))
    assert fresh.score > stale.score


def test_best_match_picks_the_strongest_trend():
    cand = Candidate(launch=_launch("Baby Frog", "BABYFROG"))
    dog = _trend("DOG")
    dog.mint = "mint-DOG"
    dog.name = "Dog"
    ref, sb = best_match(cand, [dog, _trend("FROG")], compute_flow([]))
    assert ref is not None and ref.symbol == "FROG"
    assert sb is not None


def test_best_match_skips_self():
    cand = Candidate(launch=_launch("Frog", "FROG"))
    ref = _trend()
    ref.mint = cand.mint
    got_ref, got_sb = best_match(cand, [ref], compute_flow([]))
    assert got_ref is None and got_sb is None


def test_prd_worked_example_actually_fires():
    """The PRD's own $BABYFROG example must clear the TREND_ECHO gate.

    Guards the calibration: at the PRD's stated relation > 80 this canonical
    clone scored 78.2 and was silently rejected.
    """
    from memecoin_radar.alerts import decide
    from memecoin_radar.config import Thresholds
    from memecoin_radar.scoring.moon import score_moon
    from memecoin_radar.scoring.rug import score_rug

    cand = Candidate(launch=_launch("Baby Frog", "BABYFROG"))
    cand.metadata = fetched_metadata("a baby frog hops into the pond")
    snaps = make_snapshots(cand.mint, [(15, 500.0, 8, 0), (30, 6_000.0, 22, 3),
                                       (60, 60_000.0, 39, 5)])
    for snap in snaps:
        snap.market_cap_usd = 44_000.0
        snap.liquidity_usd = 17_200.0
    cand.snapshots = snaps
    cand.buy_count, cand.sol_volume = 31, 8.0

    feat = compute_flow(snaps)
    cand.moon = score_moon(cand, feat, {})
    cand.rug = score_rug(cand, feat, deployer_launches=1, deployer_rugs=0)
    cand.trend = score_trend_relation(cand, _trend(), feat)
    cand.related_trend = _trend()

    tiers = [a.alert_type for a in decide(cand, Thresholds())]
    assert cand.trend.score > Thresholds().trend_echo_relation, (
        f"relation only reached {cand.trend.score}"
    )
    assert "TREND_ECHO" in tiers, f"expected TREND_ECHO, got {tiers}"


def test_clone_whose_socials_point_elsewhere_does_not_fire():
    """Discrimination check: declared socials that ignore the trend are evidence against."""
    from memecoin_radar.config import Thresholds

    cand = Candidate(launch=_launch("Baby Frog", "BABYFROG"))
    cand.metadata = fetched_metadata(
        "a baby frog hops into the pond", twitter="https://x.com/someguy"
    )
    snaps = make_snapshots(cand.mint, [(15, 500.0, 8, 0), (30, 6_000.0, 22, 3),
                                       (60, 60_000.0, 39, 5)])
    cand.snapshots = snaps
    sb = score_trend_relation(cand, _trend(), compute_flow(snaps))
    assert sb.score < Thresholds().trend_echo_relation
