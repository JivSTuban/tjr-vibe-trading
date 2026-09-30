"""Discovery-input tests. Network-free.

These cover the defect that made the ENTER NOW gate unable to fire in
production: the candidate list was truncated to the top 40 by liquidity, and
liquidity is ANTI-correlated with being socially early. Measured on the live DB
2026-09-17: 164 mints cleared the $15k floor, 40 were checked, and three of the
four mints that actually hit the fresh+early window ranked 41st/79th/112nd and
were never asked about -- two of them at thesis rank 0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fomo_radar.discovery import liquid_launches, retired_mints
from fomo_radar.store import FomoStore


@pytest.fixture
def conn(tmp_path: Path):
    """A DB with both packages' tables, the way the live radar shares one file."""
    store = FomoStore(tmp_path / "t.sqlite3")
    store.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tokens (
            mint TEXT PRIMARY KEY, chain TEXT, name TEXT, ticker TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS market_snapshots (
            mint TEXT NOT NULL, ts TEXT NOT NULL, age_seconds REAL NOT NULL,
            liquidity_usd REAL, market_cap_usd REAL,
            PRIMARY KEY (mint, age_seconds)
        );
        """
    )
    yield store.conn
    store.close()


def add_launch(conn, mint: str, liq: float, *, age: float = 600.0) -> None:
    conn.execute(
        "INSERT INTO tokens (mint,chain,ticker,created_at) VALUES (?,?,?,?)",
        (mint, "solana", mint.upper(), "2026-09-17T00:00:00Z"),
    )
    conn.execute(
        """INSERT INTO market_snapshots (mint,ts,age_seconds,liquidity_usd,market_cap_usd)
           VALUES (?,?,?,?,?)""",
        (mint, "2026-09-17T00:10:00Z", age, liq, liq * 10),
    )
    conn.commit()


def add_theses(conn, mint: str, n: int) -> None:
    rows = [
        (f"{mint}-{i}", "thesis", "2026-09-17T01:00:00Z", "2026-09-17T01:00:01Z",
         mint, 1399811149)
        for i in range(n)
    ]
    conn.executemany(
        """INSERT INTO fomo_feed_items
           (item_id,item_type,created_at,first_seen,token_address,network_id)
           VALUES (?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()


class TestCandidateTruncation:
    def test_a_thin_but_qualifying_launch_is_not_ranked_out_by_fat_ones(self, conn):
        """The live defect: the target token is the LEAST liquid qualifier.

        Under the old `LIMIT 40` this token was 41st and never checked.
        """
        for i in range(60):
            add_launch(conn, f"fat{i:02d}", 1_000_000.0 + i)
        add_launch(conn, "target", 16_000.0)

        mints = [c.mint for c in liquid_launches(conn)]

        assert "target" in mints
        assert len(mints) == 61

    def test_still_drops_launches_under_the_liquidity_floor(self, conn):
        add_launch(conn, "thin", 14_999.0)
        add_launch(conn, "ok", 15_000.0)
        assert [c.mint for c in liquid_launches(conn)] == ["ok"]

    def test_still_drops_launches_older_than_max_age(self, conn):
        add_launch(conn, "stale", 50_000.0, age=4 * 86_400.0)
        add_launch(conn, "young", 20_000.0, age=600.0)
        assert [c.mint for c in liquid_launches(conn)] == ["young"]

    def test_limit_bounds_survivors_not_rows_scanned(self, conn):
        """Excluded mints must not eat the cap.

        They skew fat, so they sit at the head of the liquidity ordering; if the
        cap were applied before the exclusion, the live candidates below them
        would be silently truncated away again.
        """
        for i in range(10):
            add_launch(conn, f"dead{i}", 1_000_000.0 + i)
        for i in range(5):
            add_launch(conn, f"live{i}", 20_000.0 + i)

        out = liquid_launches(
            conn, limit=5, exclude={f"dead{i}" for i in range(10)}
        )

        assert len(out) == 5
        assert all(c.mint.startswith("live") for c in out)


class TestRetirement:
    def test_reports_mints_already_past_the_rank_gate(self, conn):
        add_theses(conn, "mature", 25)
        add_theses(conn, "early", 3)
        assert retired_mints(conn, 20) == {"mature"}

    def test_boundary_is_inclusive_matching_the_gate(self, conn):
        """`len(history) >= max_thesis_rank` is the gate, so 20 is already out."""
        add_theses(conn, "exactly20", 20)
        add_theses(conn, "nineteen", 19)
        assert retired_mints(conn, 20) == {"exactly20"}

    def test_retired_mints_are_excluded_from_candidates(self, conn):
        add_launch(conn, "mature", 900_000.0)
        add_launch(conn, "early", 20_000.0)
        add_theses(conn, "mature", 30)

        retired = retired_mints(conn, 20)
        mints = [c.mint for c in liquid_launches(conn, exclude=retired)]

        assert mints == ["early"]

    def test_a_launch_with_no_theses_is_never_retired(self, conn):
        """A token with no social footprint yet is the highest-value case.

        Its first thesis medians +715.6%; retiring it for silence would discard
        exactly what discovery exists to catch.
        """
        add_launch(conn, "quiet", 30_000.0)
        assert retired_mints(conn, 20) == set()
        assert [c.mint for c in liquid_launches(conn)] == ["quiet"]
