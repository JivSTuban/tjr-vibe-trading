"""Guards for continuous operation.

The radar is meant to run for weeks against ~35k-63k launches/day. Anything that
accumulates per mint is a leak at that volume, and a five-minute smoke test
cannot see it. These tests simulate ageing instead.
"""

from __future__ import annotations

from datetime import timedelta

from memecoin_radar.config import RadarConfig
from memecoin_radar.models import Candidate, LaunchEvent, utcnow
from memecoin_radar.run import CANDIDATE_MAX_AGE_S, Radar


def _launch(i: int, *, age_seconds: float) -> LaunchEvent:
    return LaunchEvent(
        mint=f"mint{i}",
        name=f"n{i}",
        symbol=f"S{i}",
        creator=f"c{i}",
        signature=f"sig{i}",
        uri="",
        pool="pump",
        initial_buy=1_000.0,
        sol_amount=0.1,
        market_cap_sol=28.0,
        v_sol_in_curve=30.0,
        v_tokens_in_curve=1e9,
        seen_at=utcnow() - timedelta(seconds=age_seconds),
    )


def _radar(tmp_path) -> Radar:
    return Radar(RadarConfig(db_path=tmp_path / "longrun.sqlite3", dry_run=True))


def test_prune_clears_every_per_mint_map(tmp_path):
    radar = _radar(tmp_path)
    try:
        for i in range(50):
            mint = f"mint{i}"
            radar.candidates[mint] = Candidate(
                launch=_launch(i, age_seconds=CANDIDATE_MAX_AGE_S + 60)
            )
            radar._snapshotted[mint] = {15, 30}
            radar._helius_checked.add(mint)
            radar._metadata_attempted.add(mint)

        assert radar.working_set_size() > 0
        radar._prune()
        # Every structure keyed by mint must be empty, not just `candidates`.
        assert radar.working_set_size() == 0
    finally:
        radar.store.close()


def test_prune_keeps_live_candidates(tmp_path):
    radar = _radar(tmp_path)
    try:
        radar.candidates["young"] = Candidate(launch=_launch(1, age_seconds=30))
        radar._metadata_attempted.add("young")
        radar.candidates["old"] = Candidate(
            launch=_launch(2, age_seconds=CANDIDATE_MAX_AGE_S + 60)
        )
        radar._metadata_attempted.add("old")

        radar._prune()
        assert "young" in radar.candidates
        assert "old" not in radar.candidates
        assert radar._metadata_attempted == {"young"}
    finally:
        radar.store.close()


def test_working_set_stays_bounded_across_many_generations(tmp_path):
    """Ten generations of 200 launches must not accumulate state."""
    radar = _radar(tmp_path)
    try:
        for generation in range(10):
            for i in range(200):
                mint = f"g{generation}m{i}"
                radar.candidates[mint] = Candidate(launch=_launch(i, age_seconds=1))
                radar.candidates[mint].launch.mint = mint
                radar._snapshotted[mint] = {15}
                radar._metadata_attempted.add(mint)
            # Age the whole generation past the retention window.
            for cand in radar.candidates.values():
                cand.launch.seen_at = utcnow() - timedelta(seconds=CANDIDATE_MAX_AGE_S + 60)
            radar._prune()
            assert radar.working_set_size() == 0, (
                f"generation {generation} left {radar.working_set_size()} entries behind"
            )
    finally:
        radar.store.close()
