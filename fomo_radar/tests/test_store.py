"""Store tests. Network-free; every fixture is shaped like a real payload."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fomo_radar.api import LeaderboardTrader, ThesisItem
from fomo_radar.store import SCHEMA, FomoStore


@pytest.fixture
def store(tmp_path: Path) -> FomoStore:
    s = FomoStore(tmp_path / "t.sqlite3")
    yield s
    s.close()


def mkitem(item_id="i1", token="tok", handle="a", usd=5000.0, created="2026-09-17T01:00:00Z",
           item_type="thesis", links=None, network=1399811149):
    return ThesisItem(
        item_id=item_id, item_type=item_type, trade_id="t", created_at=created,
        user_id="u", handle=handle, display_name=handle, verified=False, is_dev=False,
        token_address=token, network_id=network, ticker="TST", usd_value=usd,
        unrealized_pnl_pct=0.0, realized_pnl_pct=0.0, author_equity=0.0, likes=0,
        text="hello", links=links or [],
    )


class TestFeedPersistence:
    def test_records_new_items(self, store):
        fresh = store.record_items([mkitem("i1"), mkitem("i2", handle="b")])
        assert len(fresh) == 2

    def test_dedupes_by_item_id(self, store):
        store.record_items([mkitem("i1")])
        assert store.record_items([mkitem("i1")]) == []

    def test_repolling_the_same_window_is_free(self, store):
        """The global feed is a fixed 25-item window we poll every 20s."""
        window = [mkitem(f"i{n}", handle=f"h{n}") for n in range(25)]
        assert len(store.record_items(window)) == 25
        assert store.record_items(window) == []

    def test_swaps_are_kept_as_the_base_rate(self, store):
        store.record_items([mkitem("s1", item_type="swap_buy")])
        assert store.stats()["feed_items"] == 1
        assert store.stats()["theses"] == 0

    def test_x_link_is_flagged_but_separate_from_score(self, store):
        store.record_items([mkitem("i1", links=["https://x.com/foo/status/1"])])
        row = store.conn.execute(
            "SELECT has_x_link FROM fomo_feed_items WHERE item_id='i1'"
        ).fetchone()
        assert row["has_x_link"] == 1

    def test_items_without_a_token_are_skipped(self, store):
        assert store.record_items([mkitem("i1", token="")]) == []


class TestTokenStats:
    def test_counts_distinct_authors_not_posts(self, store):
        """One handle posting three times is not three authors."""
        store.record_items([
            mkitem("i1", handle="a", created="2026-09-17T01:00:00Z"),
            mkitem("i2", handle="a", created="2026-09-17T01:01:00Z"),
            mkitem("i3", handle="a", created="2026-09-17T01:02:00Z"),
        ])
        stats = store.refresh_token_stats("tok", 1399811149, set())
        assert stats["thesis_count"] == 3
        assert stats["distinct_authors"] == 1

    def test_sub_threshold_theses_do_not_count_as_qualified(self, store):
        store.record_items([
            mkitem("i1", handle="a", usd=50.0),
            mkitem("i2", handle="b", usd=9000.0),
        ])
        stats = store.refresh_token_stats("tok", 1399811149, set())
        assert stats["thesis_count"] == 2
        assert stats["qualified_count"] == 1

    def test_leaderboard_authors_counted(self, store):
        store.record_items([mkitem("i1", handle="whale"), mkitem("i2", handle="b")])
        stats = store.refresh_token_stats("tok", 1399811149, {"whale"})
        assert stats["leaderboard_authors"] == 1

    def test_first_thesis_is_the_earliest_not_the_first_seen(self, store):
        """Backfill inserts older rows after newer ones; ordering must hold."""
        store.record_items([mkitem("i2", handle="b", created="2026-09-17T05:00:00Z")])
        store.record_items([mkitem("i1", handle="a", created="2026-09-17T01:00:00Z")])
        stats = store.refresh_token_stats("tok", 1399811149, set())
        assert stats["first_thesis_at"].startswith("2026-09-17T01")


class TestAlertOnce:
    def test_not_alerted_initially(self, store):
        store.record_items([mkitem("i1")])
        store.refresh_token_stats("tok", 1399811149, set())
        assert store.already_alerted("tok", 1399811149) is False

    def test_mark_alerted_sticks(self, store):
        store.record_items([mkitem("i1")])
        store.refresh_token_stats("tok", 1399811149, set())
        store.mark_alerted("tok", 1399811149)
        assert store.already_alerted("tok", 1399811149) is True


class TestLeaderboard:
    def trader(self, handle="w", addr="SoL111"):
        return LeaderboardTrader(
            user_id="u", handle=handle, display_name=handle, solana_address=addr,
            evm_address="0x1", pnl=1000.0, num_trades=10, total_volume=5000.0,
            followers=100, total_holdings=3,
            top_holdings=[{"tokenAddress": "tok", "networkId": 1399811149,
                           "humanAmount": 1.0, "price": 2.0, "value": 2.0, "pnl": 1.0}],
        )

    def test_populates_shared_wallets_table(self, store):
        """This is the PRD Phase 2 unblock: free smart-money wallet addresses."""
        store.record_leaderboard("24h", [self.trader()])
        row = store.conn.execute(
            "SELECT address, realized_pnl, tags FROM wallets"
        ).fetchone()
        assert row["address"] == "SoL111"
        assert row["realized_pnl"] == 1000.0
        assert "fomo:24h" in row["tags"]

    def test_holdings_are_recorded(self, store):
        store.record_leaderboard("24h", [self.trader()])
        n = store.conn.execute(
            "SELECT COUNT(*) FROM fomo_leaderboard_holdings"
        ).fetchone()[0]
        assert n == 1

    def test_handles_returns_latest_capture(self, store):
        store.record_leaderboard("24h", [self.trader("alpha")])
        assert "alpha" in store.leaderboard_handles()

    def test_wallets_schema_matches_radar(self):
        """Guard against the duplicated DDL drifting from memecoin_radar's."""
        from memecoin_radar import store as radar_store

        def wallets_ddl(sql: str) -> str:
            m = re.search(
                r"CREATE TABLE IF NOT EXISTS wallets \((.*?)\);", sql, re.S
            )
            assert m, "wallets DDL not found"
            return re.sub(r"\s+", " ", m.group(1)).strip()

        assert wallets_ddl(SCHEMA) == wallets_ddl(radar_store.SCHEMA)
