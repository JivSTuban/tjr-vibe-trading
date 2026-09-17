"""Persistence and feature-math tests."""

from __future__ import annotations

from memecoin_radar.features import compute_flow
from memecoin_radar.models import MarketSnapshot, utcnow
from memecoin_radar.store import Store
from memecoin_radar.trend_context import TrendContext
from memecoin_radar.models import Candidate

from .conftest import fetched_metadata, make_snapshots


# ------------------------------------------------------------------ features

def test_no_snapshots_means_no_rates():
    feat = compute_flow([])
    assert feat.samples == 0
    assert feat.volume_rate_usd_per_min == 0.0
    assert feat.unique_buyer_accel is None


def test_single_snapshot_gives_levels_but_no_rates():
    snaps = make_snapshots("m", [(15, 100.0, 5, 1)])
    feat = compute_flow(snaps)
    assert feat.samples == 1
    assert feat.market_cap_usd > 0
    assert feat.volume_rate_usd_per_min == 0.0


def test_rates_computed_from_two_points():
    snaps = make_snapshots("m", [(0, 0.0, 0, 0), (60, 600.0, 30, 0)])
    feat = compute_flow(snaps)
    assert feat.volume_rate_usd_per_min == 600.0
    assert feat.buy_tx_rate_per_min == 30.0


def test_acceleration_needs_three_points():
    snaps = make_snapshots("m", [(0, 0.0, 0, 0), (60, 100.0, 10, 0), (120, 500.0, 50, 0)])
    feat = compute_flow(snaps)
    assert feat.volume_accel > 1.0


def test_unique_buyers_never_faked_from_tx_counts():
    """DexScreener gives tx counts; unique buyers must stay unmeasured."""
    snaps = make_snapshots("m", [(15, 100.0, 50, 2), (30, 900.0, 200, 5)])
    assert compute_flow(snaps).unique_buyer_accel is None


def test_buy_ratio_reflects_imbalance():
    snaps = make_snapshots("m", [(15, 10.0, 9, 1)])
    assert compute_flow(snaps).buy_ratio == 0.9


def test_liquidity_decline_is_detected():
    base = utcnow()
    snaps = [
        MarketSnapshot(mint="m", ts=base, age_seconds=30, liquidity_usd=10_000.0),
        MarketSnapshot(mint="m", ts=base, age_seconds=60, liquidity_usd=4_000.0),
    ]
    assert compute_flow(snaps).net_liquidity_change == -6_000.0


# --------------------------------------------------------------------- store

def test_store_records_every_launch_including_rejects(tmp_path, launch):
    store = Store(tmp_path / "t.sqlite3")
    store.record_launch(launch)
    assert store.counts()["tokens"] == 1
    # Re-recording the same mint must not duplicate it.
    store.record_launch(launch)
    assert store.counts()["tokens"] == 1
    store.close()


def test_deployer_history_accumulates_from_our_own_stream(tmp_path, launch):
    store = Store(tmp_path / "t.sqlite3")
    store.record_launch(launch)
    assert store.deployer_launch_count(launch.creator) == 1

    from memecoin_radar.models import LaunchEvent

    other = LaunchEvent(
        mint="another-mint", name="n", symbol="s", creator=launch.creator,
        signature="sig2", uri="", pool="pump", initial_buy=1.0, sol_amount=0.1,
        market_cap_sol=28.0, v_sol_in_curve=30.0, v_tokens_in_curve=1e9,
    )
    store.record_launch(other)
    assert store.deployer_launch_count(launch.creator) == 2
    assert store.deployer_rug_count(launch.creator) == 0
    store.close()


def test_snapshots_round_trip(tmp_path, launch):
    store = Store(tmp_path / "t.sqlite3")
    store.record_launch(launch)
    for snap in make_snapshots(launch.mint, [(15, 10.0, 1, 0), (60, 900.0, 30, 2)]):
        store.record_snapshot(snap)
    rows = store.snapshots_for(launch.mint)
    assert [r["age_seconds"] for r in rows] == [15.0, 60.0]
    store.close()


def test_smart_wallet_watchlist_starts_empty(tmp_path):
    store = Store(tmp_path / "t.sqlite3")
    assert store.smart_wallets() == {}
    store.upsert_wallet("W1", 80.0, ["early"])
    assert store.smart_wallets() == {"W1": 80.0}
    store.close()


# ------------------------------------------------------------- trend context

def test_trend_context_rejects_a_token_that_has_not_moved(candidate):
    ctx = TrendContext()
    candidate.snapshots = make_snapshots(candidate.mint, [(60, 10.0, 2, 0)])
    candidate.snapshots[-1].market_cap_usd = 500.0
    candidate.snapshots[-1].volume_usd = 20.0
    assert ctx.consider(candidate) is None
    assert len(ctx) == 0


def test_trend_context_admits_a_mover(candidate):
    ctx = TrendContext()
    candidate.metadata = fetched_metadata("a frog")
    snaps = make_snapshots(candidate.mint, [(300, 40_000.0, 400, 50)])
    snaps[-1].market_cap_usd = 120_000.0
    snaps[-1].volume_usd = 40_000.0
    candidate.snapshots = snaps
    ref = ctx.consider(candidate)
    assert ref is not None and len(ctx) == 1
    assert "frog" in ref.narrative_tokens


def test_migration_admits_regardless_of_volume_floor(candidate):
    ctx = TrendContext()
    candidate.snapshots = make_snapshots(candidate.mint, [(60, 1.0, 1, 0)])
    candidate.snapshots[-1].market_cap_usd = 100.0
    candidate.snapshots[-1].volume_usd = 1.0
    ref = ctx.consider(candidate, migrated=True)
    assert ref is not None
    assert ref.momentum_state == "accelerating"


def test_trend_context_evicts_beyond_capacity():
    ctx = TrendContext(max_references=2)
    from memecoin_radar.models import LaunchEvent

    for i in range(4):
        launch = LaunchEvent(
            mint=f"m{i}", name=f"n{i}", symbol=f"S{i}", creator="c", signature="s",
            uri="", pool="pump", initial_buy=1.0, sol_amount=0.1, market_cap_sol=28.0,
            v_sol_in_curve=30.0, v_tokens_in_curve=1e9,
        )
        cand = Candidate(launch=launch)
        snaps = make_snapshots(cand.mint, [(300, 1.0, 1, 0)])
        snaps[-1].market_cap_usd = 30_000.0 * (i + 1)
        snaps[-1].volume_usd = 10_000.0 * (i + 1)
        cand.snapshots = snaps
        ctx.consider(cand)
    assert len(ctx) == 2
    # The two strongest survive.
    assert {r.mint for r in ctx.references()} == {"m2", "m3"}
