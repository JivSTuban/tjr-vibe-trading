"""Disk retention, so a 24/7 deployment does not fill the host.

Measured growth on the live collector: ~4.5 KB per token, which at the observed
12-44 launches/min is roughly 150-280 MB/day, or 4.5-8 GB/month. That is too
much to leave unmanaged on the Mac Mini.

The constraint that makes this delicate: PRD section 8 needs EVERY considered
token retained, because the rejects are the base rate and without them no
threshold can ever be validated. So this never deletes a token row.

What it does instead, for tokens that are old, never alerted, and never became
an outcome worth studying:

  * drops the `raw` wire blob, which exists for debugging a parser change and
    is dead weight afterwards
  * thins the snapshot series to its first and last point, which preserves
    entry price, peak-to-last, and the rugged/not label
  * drops the per-age score rows, which are reconstructible from the snapshots

Alerted tokens and labelled winners keep their full detail, because those are
exactly the rows a post-mortem needs.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .config import load_config
from .store import Store

log = logging.getLogger("retention")

# Tokens younger than this are never touched: they may still be collecting.
MIN_AGE_HOURS = 24.0

# A token that reached this multiple is worth keeping in full even if it never
# alerted, because it is a miss and misses are the most informative rows here.
KEEP_IF_RETURN_ABOVE = 1.0  # 2x


@dataclass
class PruneStats:
    tokens_considered: int = 0
    tokens_thinned: int = 0
    raw_blobs_cleared: int = 0
    snapshots_deleted: int = 0
    scores_deleted: int = 0
    bytes_before: int = 0
    bytes_after: int = 0

    def summary(self) -> str:
        saved = self.bytes_before - self.bytes_after
        pct = (saved / self.bytes_before * 100.0) if self.bytes_before else 0.0
        return (
            f"considered {self.tokens_considered:,} tokens, thinned "
            f"{self.tokens_thinned:,}\n"
            f"  cleared {self.raw_blobs_cleared:,} raw blobs, deleted "
            f"{self.snapshots_deleted:,} snapshots and {self.scores_deleted:,} score rows\n"
            f"  {self.bytes_before / 1e6:.1f} MB -> {self.bytes_after / 1e6:.1f} MB "
            f"({pct:.0f}% saved)"
        )


def _db_bytes(store: Store) -> int:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        path = store.db_path.with_name(store.db_path.name + suffix)
        if path.exists():
            total += path.stat().st_size
    return total


def protected_mints(store: Store) -> set[str]:
    """Tokens that keep their full detail.

    Anything that alerted (we need to judge the alert), anything that ran
    (a miss is the most valuable row in the dataset), and anything that rugged
    after alerting.
    """
    keep: set[str] = set()
    for row in store.conn.execute("SELECT DISTINCT mint FROM alerts"):
        keep.add(row["mint"])
    for row in store.conn.execute(
        """SELECT mint FROM outcomes
           WHERE COALESCE(max_return_1h, 0) >= ?
              OR COALESCE(max_return_24h, 0) >= ?
              OR t_2x IS NOT NULL""",
        (KEEP_IF_RETURN_ABOVE, KEEP_IF_RETURN_ABOVE),
    ):
        keep.add(row["mint"])
    return keep


def prune(store: Store, *, min_age_hours: float = MIN_AGE_HOURS, dry_run: bool = False) -> PruneStats:
    stats = PruneStats(bytes_before=_db_bytes(store))
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=min_age_hours)).isoformat()
    keep = protected_mints(store)

    candidates = [
        row["mint"]
        for row in store.conn.execute(
            "SELECT mint FROM tokens WHERE created_at <= ?", (cutoff,)
        )
    ]
    stats.tokens_considered = len(candidates)
    targets = [m for m in candidates if m not in keep]

    if dry_run:
        for mint in targets:
            snaps = store.snapshots_for(mint)
            stats.snapshots_deleted += max(0, len(snaps) - 2)
        stats.tokens_thinned = len(targets)
        stats.bytes_after = stats.bytes_before
        return stats

    for mint in targets:
        snaps = store.snapshots_for(mint)
        with store.tx() as c:
            cur = c.execute(
                "UPDATE tokens SET raw='' WHERE mint=? AND raw != ''", (mint,)
            )
            stats.raw_blobs_cleared += cur.rowcount if cur.rowcount > 0 else 0

            if len(snaps) > 2:
                # Keep the extremes: first gives the entry, last gives the
                # outcome. Everything between is shape, which we no longer need
                # once the token is cold and never alerted.
                keep_ages = {snaps[0]["age_seconds"], snaps[-1]["age_seconds"]}
                placeholders = ",".join("?" for _ in keep_ages)
                cur = c.execute(
                    f"DELETE FROM market_snapshots WHERE mint=? "
                    f"AND age_seconds NOT IN ({placeholders})",
                    (mint, *keep_ages),
                )
                stats.snapshots_deleted += max(0, cur.rowcount)

            cur = c.execute("DELETE FROM scores WHERE mint=?", (mint,))
            stats.scores_deleted += max(0, cur.rowcount)
        stats.tokens_thinned += 1

    # VACUUM reclaims the freed pages, but in WAL mode the reclaimed space
    # lands in the write-ahead log, so the on-disk footprint briefly GROWS.
    # Checkpointing with TRUNCATE folds the WAL back into the database and
    # empties it, which is what actually returns the space to the filesystem.
    store.conn.commit()
    store.conn.execute("VACUUM")
    store.conn.commit()
    store.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    store.conn.commit()
    stats.bytes_after = _db_bytes(store)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Thin cold, never-alerted rows")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-age-hours", type=float, default=MIN_AGE_HOURS)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config()
    store = Store(cfg.db_path)
    try:
        stats = prune(store, min_age_hours=args.min_age_hours, dry_run=args.dry_run)
        prefix = "[dry-run] " if args.dry_run else ""
        print(prefix + stats.summary())
        print(f"  token rows kept: {store.counts()['tokens']:,} (never deleted)")
    finally:
        store.close()


if __name__ == "__main__":
    main()
