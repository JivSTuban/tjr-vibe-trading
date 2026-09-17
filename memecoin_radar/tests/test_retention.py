"""Retention tests.

The hard invariant: pruning never removes a token row. The base rate in
`backtest.evaluate` is computed over all considered tokens, so deleting the
boring ones would quietly inflate every precision figure the radar reports.
"""

from __future__ import annotations

from datetime import timedelta

from memecoin_radar.models import Alert, LaunchEvent, MarketSnapshot, utcnow
from memecoin_radar.retention import prune, protected_mints
from memecoin_radar.store import Store


def _launch(i: int, *, hours_old: float) -> LaunchEvent:
    return LaunchEvent(
        mint=f"mint{i}",
        name=f"tok{i}",
        symbol=f"T{i}",
        creator="deployer1",
        signature=f"sig{i}",
        uri="ipfs://x",
        pool="pump",
        initial_buy=1_000.0,
        sol_amount=0.1,
        market_cap_sol=28.0,
        v_sol_in_curve=30.0,
        v_tokens_in_curve=1e9,
        seen_at=utcnow() - timedelta(hours=hours_old),
        raw={"padding": "x" * 400},
    )


def _seed(store: Store, i: int, *, hours_old: float, snapshots: int = 6) -> str:
    ev = _launch(i, hours_old=hours_old)
    store.record_launch(ev)
    for n in range(snapshots):
        store.record_snapshot(
            MarketSnapshot(
                mint=ev.mint,
                ts=utcnow(),
                age_seconds=float(15 * (n + 1)),
                market_cap_usd=1_000.0 * (n + 1),
                liquidity_usd=500.0,
                volume_usd=100.0 * n,
                buys=n,
                sells=0,
            )
        )
    return ev.mint


def test_prune_never_deletes_a_token_row(tmp_path):
    store = Store(tmp_path / "r.sqlite3")
    try:
        for i in range(10):
            _seed(store, i, hours_old=48)
        before = store.counts()["tokens"]
        prune(store)
        assert store.counts()["tokens"] == before == 10
    finally:
        store.close()


def test_prune_thins_snapshots_to_first_and_last(tmp_path):
    store = Store(tmp_path / "r.sqlite3")
    try:
        mint = _seed(store, 1, hours_old=48, snapshots=6)
        assert len(store.snapshots_for(mint)) == 6
        prune(store)
        remaining = store.snapshots_for(mint)
        assert len(remaining) == 2
        assert remaining[0]["age_seconds"] == 15.0
        assert remaining[-1]["age_seconds"] == 90.0
        # The outcome label still works: entry and peak-to-last survive.
        assert remaining[-1]["market_cap_usd"] > remaining[0]["market_cap_usd"]
    finally:
        store.close()


def test_prune_clears_the_raw_blob(tmp_path):
    store = Store(tmp_path / "r.sqlite3")
    try:
        mint = _seed(store, 1, hours_old=48)
        raw = store.conn.execute(
            "SELECT raw FROM tokens WHERE mint=?", (mint,)
        ).fetchone()["raw"]
        assert len(raw) > 100
        prune(store)
        raw = store.conn.execute(
            "SELECT raw FROM tokens WHERE mint=?", (mint,)
        ).fetchone()["raw"]
        assert raw == ""
    finally:
        store.close()


def test_alerted_tokens_keep_full_detail(tmp_path):
    store = Store(tmp_path / "r.sqlite3")
    try:
        quiet = _seed(store, 1, hours_old=48, snapshots=6)
        loud = _seed(store, 2, hours_old=48, snapshots=6)
        store.record_alert(
            Alert(mint=loud, ts=utcnow(), alert_type="HOT", moon_score=90,
                  rug_score=10, relation_score=0)
        )

        assert protected_mints(store) == {loud}
        prune(store)
        assert len(store.snapshots_for(loud)) == 6
        assert len(store.snapshots_for(quiet)) == 2
    finally:
        store.close()


def test_recent_tokens_are_untouched(tmp_path):
    store = Store(tmp_path / "r.sqlite3")
    try:
        fresh = _seed(store, 1, hours_old=1, snapshots=6)
        prune(store)
        assert len(store.snapshots_for(fresh)) == 6
    finally:
        store.close()


def test_dry_run_changes_nothing(tmp_path):
    store = Store(tmp_path / "r.sqlite3")
    try:
        mint = _seed(store, 1, hours_old=48, snapshots=6)
        stats = prune(store, dry_run=True)
        assert stats.snapshots_deleted == 4
        assert len(store.snapshots_for(mint)) == 6
    finally:
        store.close()


def test_prune_actually_shrinks_the_file(tmp_path):
    store = Store(tmp_path / "r.sqlite3")
    try:
        for i in range(120):
            _seed(store, i, hours_old=48, snapshots=8)
        stats = prune(store)
        assert stats.tokens_thinned == 120
        assert stats.bytes_after < stats.bytes_before, stats.summary()
    finally:
        store.close()
