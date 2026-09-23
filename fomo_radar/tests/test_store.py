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


# ------------------------------------------------------------------ entry gate


def _alert(store: FomoStore, *, tier="ENTER NOW", delivered=True, suppressed=None, token="tok"):
    store.record_alert(
        token_address=token, network_id=1399811149, ticker="TST", tier=tier,
        score=60.0, thesis_rank=0, distinct_authors=1, leaderboard_authors=0,
        total_usd=1000.0, reason="r", delivered=delivered, suppressed_reason=suppressed,
    )


def test_suppressed_alerts_are_recorded_not_dropped(store: FomoStore):
    """The refused alerts are the control group; losing them makes the gate unfalsifiable."""
    _alert(store, tier="CONVICTION", delivered=False, suppressed="pool too thin")
    row = store.conn.execute("SELECT * FROM fomo_alerts").fetchone()
    assert row["delivered"] == 0
    assert row["suppressed_reason"] == "pool too thin"


def test_suppressed_alerts_are_excluded_from_entries_by_default(store: FomoStore):
    _alert(store, token="a", delivered=True)
    _alert(store, token="b", tier="WATCH", delivered=False, suppressed="stale")
    entered = {t["token_address"] for t in store.alerted_tokens()}
    assert entered == {"a"}


def test_control_group_is_reachable_and_labelled(store: FomoStore):
    """Outcome tracking must see suppressed alerts, flagged as not entered."""
    _alert(store, token="a", delivered=True)
    _alert(store, token="b", tier="WATCH", delivered=False, suppressed="stale")
    rows = {t["token_address"]: t for t in store.alerted_tokens(include_suppressed=True)}
    assert set(rows) == {"a", "b"}
    assert rows["a"]["entered"] is True
    assert rows["b"]["entered"] is False


class TestOutcomeTrackingPopulation:
    """The tracked set must include tokens the signal never liked.

    Tracking only our own alerts grades the classifier on its own selections,
    which is why the earliness term has never been scored. These pin the base
    rate into the population so it cannot quietly narrow again.
    """

    def test_includes_tokens_that_never_alerted(self, store: FomoStore):
        store.record_items([mkitem("i1", token="never-alerted")])
        store.refresh_token_stats("never-alerted", 1399811149, set())
        rows = {t["token_address"]: t for t in store.tokens_for_outcome_tracking()}
        assert "never-alerted" in rows
        assert rows["never-alerted"]["cohort"] == "thesis"

    def test_alerted_token_keeps_the_alert_clock(self, store: FomoStore):
        """Moving the clock to first_thesis_at would re-date every recorded row."""
        store.record_items([mkitem("i1", token="tok", created="2026-09-17T01:00:00Z")])
        store.refresh_token_stats("tok", 1399811149, set())
        _alert(store, token="tok")
        row = next(
            t for t in store.tokens_for_outcome_tracking() if t["token_address"] == "tok"
        )
        assert row["cohort"] == "alerted"
        assert row["first_alert"] != "2026-09-17T01:00:00Z"

    def test_cohorts_are_distinguishable(self, store: FomoStore):
        """Pooling alerted and base-rate tokens would overstate the comparison."""
        store.record_items([mkitem("i1", token="a"), mkitem("i2", token="b", handle="b")])
        for t in ("a", "b"):
            store.refresh_token_stats(t, 1399811149, set())
        _alert(store, token="a")
        cohorts = {t["token_address"]: t["cohort"] for t in store.tokens_for_outcome_tracking()}
        assert cohorts == {"a": "alerted", "b": "thesis"}

    def test_never_narrows_the_previous_population(self, store: FomoStore):
        """A COPY PROBE alerts with no thesis row and must not be dropped.

        The first version of this method selected from `fomo_tokens`, which
        silently lost 7 of 38 tracked tokens on the live DB. Widening the
        tracked set must never narrow it.
        """
        _alert(store, token="probe-only", tier="COPY PROBE",
               delivered=False, suppressed="copy-trade probe, never notified")
        assert store.conn.execute(
            "SELECT COUNT(*) FROM fomo_tokens WHERE token_address='probe-only'"
        ).fetchone()[0] == 0
        tracked = {t["token_address"] for t in store.tokens_for_outcome_tracking()}
        previous = {t["token_address"] for t in store.alerted_tokens(include_suppressed=True)}
        assert previous <= tracked
        assert "probe-only" in tracked

    def test_limit_keeps_the_newest_clocks(self, store: FomoStore):
        """The cap must drop stale tokens, not fresh ones whose marks are ahead."""
        store.record_items([
            mkitem("i1", token="old", created="2026-09-01T00:00:00Z"),
            mkitem("i2", token="new", created="2026-09-17T00:00:00Z", handle="b"),
        ])
        for t in ("old", "new"):
            store.refresh_token_stats(t, 1399811149, set())
        rows = store.tokens_for_outcome_tracking(limit=1)
        assert [t["token_address"] for t in rows] == ["new"]


def test_delivery_failures_are_excluded_from_both(store: FomoStore):
    """delivered=0 with no suppression reason is a BROKEN post, not a decision.

    Nothing reached anyone, so there is no honest entry clock for it.
    """
    _alert(store, token="c", delivered=False, suppressed=None)
    assert store.alerted_tokens() == []
    assert store.alerted_tokens(include_suppressed=True) == []


def test_suppressed_alert_does_not_block_a_later_real_entry(store: FomoStore):
    """The unreachable-signal trap: a recorded refusal must not poison the token.

    `best_tier_so_far` drives the re-alert suppression, so if it counted
    suppressed rows a token blocked once on thin liquidity could never alert
    again after its pool deepened.
    """
    _alert(store, token="d", tier="CONVICTION", delivered=False, suppressed="pool too thin")
    assert store.best_tier_so_far("d", 1399811149) is None


def test_migration_adds_the_column_to_a_preexisting_database(tmp_path: Path):
    """CREATE TABLE IF NOT EXISTS is a no-op on an existing table.

    Without the additive migration the live database on the Mini keeps its old
    `fomo_alerts` and every insert fails on the unknown column.
    """
    import sqlite3

    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """CREATE TABLE fomo_alerts (
             id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
             token_address TEXT NOT NULL, network_id INTEGER, ticker TEXT,
             tier TEXT NOT NULL, score REAL, thesis_rank INTEGER,
             distinct_authors INTEGER, leaderboard_authors INTEGER,
             total_usd REAL, reason TEXT, delivered INTEGER DEFAULT 0);"""
    )
    conn.execute(
        "INSERT INTO fomo_alerts (ts,token_address,tier) VALUES ('t','legacy','HOT')"
    )
    conn.commit()
    conn.close()

    store = FomoStore(path)
    try:
        cols = {r["name"] for r in store.conn.execute("PRAGMA table_info(fomo_alerts)")}
        assert "suppressed_reason" in cols
        # The pre-existing row survives, with the new column null.
        legacy = store.conn.execute(
            "SELECT * FROM fomo_alerts WHERE token_address='legacy'"
        ).fetchone()
        assert legacy["suppressed_reason"] is None
        # And writes work against the migrated table.
        _alert(store, token="new", delivered=False, suppressed="stale")
    finally:
        store.close()


def test_migration_is_idempotent(tmp_path: Path):
    path = tmp_path / "t.sqlite3"
    FomoStore(path).close()
    store = FomoStore(path)  # second open must not fail on a duplicate column
    try:
        cols = {r["name"] for r in store.conn.execute("PRAGMA table_info(fomo_alerts)")}
        assert "suppressed_reason" in cols
    finally:
        store.close()


class TestLeaderboardHoldingsDedupe:
    """The holdings payload is our only free trade tape.

    `value` moves with price on every poll, so writing every row would cost
    264 MB/day at a useful poll rate (measured 2026-09-17) while 83% of the rows
    say "no trade". Only a QUANTITY change means a trade happened.
    """

    def trader(self, handle="whale", amount=1000.0, price=1.0):
        return LeaderboardTrader(
            user_id="u1", handle=handle, display_name=handle,
            solana_address="So1111", evm_address="", pnl=5000.0,
            num_trades=10, total_volume=100_000.0, followers=10,
            total_holdings=1,
            top_holdings=[{
                "tokenAddress": "tokA", "networkId": 1399811149,
                "humanAmount": amount, "price": price,
                "value": amount * price, "pnl": 1.0,
            }],
        )

    def holdings(self, store):
        return store.conn.execute(
            "SELECT human_amount, price FROM fomo_leaderboard_holdings"
            " ORDER BY captured_at"
        ).fetchall()

    def test_writes_the_first_capture(self, store):
        store.record_leaderboard("24h", [self.trader()])
        assert len(self.holdings(store)) == 1

    def test_skips_a_repeat_with_the_same_quantity(self, store):
        store.record_leaderboard("24h", [self.trader(amount=1000.0)])
        store.record_leaderboard("24h", [self.trader(amount=1000.0)])
        assert len(self.holdings(store)) == 1

    def test_a_price_move_alone_is_not_a_trade(self, store):
        """The exact false signal: value doubled, but nobody bought anything."""
        store.record_leaderboard("24h", [self.trader(amount=1000.0, price=1.0)])
        store.record_leaderboard("24h", [self.trader(amount=1000.0, price=2.0)])
        assert len(self.holdings(store)) == 1

    def test_records_a_quantity_increase_as_a_buy(self, store):
        store.record_leaderboard("24h", [self.trader(amount=1000.0)])
        store.record_leaderboard("24h", [self.trader(amount=1500.0)])
        assert [r["human_amount"] for r in self.holdings(store)] == [1000.0, 1500.0]

    def test_records_a_quantity_decrease_as_a_sell(self, store):
        store.record_leaderboard("24h", [self.trader(amount=1000.0)])
        store.record_leaderboard("24h", [self.trader(amount=400.0)])
        assert [r["human_amount"] for r in self.holdings(store)] == [1000.0, 400.0]

    def test_rounding_noise_is_not_a_trade(self, store):
        store.record_leaderboard("24h", [self.trader(amount=1000.0)])
        store.record_leaderboard("24h", [self.trader(amount=1000.5)])
        assert len(self.holdings(store)) == 1

    def test_dedupe_can_be_turned_off(self, store):
        store.record_leaderboard("24h", [self.trader()], dedupe_holdings=False)
        store.record_leaderboard("24h", [self.trader()], dedupe_holdings=False)
        assert len(self.holdings(store)) == 2


class TestCopyEventDetection:
    """Amount deltas are the only free trade tape; price moves are not trades."""

    def trader(self, amount, price=1.0, handle="whale"):
        return LeaderboardTrader(
            user_id="u1", handle=handle, display_name=handle,
            solana_address="So1111", evm_address="", pnl=5000.0,
            num_trades=10, total_volume=100_000.0, followers=10,
            total_holdings=1,
            top_holdings=[{
                "tokenAddress": "tokA", "networkId": 1399811149,
                "humanAmount": amount, "price": price,
                "value": amount * price, "pnl": 1.0,
            }],
        )

    def test_first_capture_emits_no_event(self, store):
        """With no prior amount, a buy is indistinguishable from appreciation."""
        assert store.record_leaderboard("24h", [self.trader(1000.0)]) == []

    def test_quantity_increase_is_a_buy(self, store):
        store.record_leaderboard("24h", [self.trader(1000.0)])
        events = store.record_leaderboard("24h", [self.trader(1500.0)])
        assert len(events) == 1
        assert events[0].is_buy
        assert events[0].delta_pct == pytest.approx(0.5)

    def test_quantity_decrease_is_a_sell(self, store):
        store.record_leaderboard("24h", [self.trader(1000.0)])
        events = store.record_leaderboard("24h", [self.trader(250.0)])
        assert len(events) == 1
        assert not events[0].is_buy
        assert events[0].delta_pct == pytest.approx(-0.75)

    def test_a_price_double_emits_no_event(self, store):
        """The exact look-ahead trap: value doubled, nobody transacted."""
        store.record_leaderboard("24h", [self.trader(1000.0, price=1.0)])
        assert store.record_leaderboard("24h", [self.trader(1000.0, price=2.0)]) == []

    def test_rounding_noise_emits_no_event(self, store):
        store.record_leaderboard("24h", [self.trader(1000.0)])
        assert store.record_leaderboard("24h", [self.trader(1000.5)]) == []

    def test_events_are_emitted_even_when_the_row_is_deduped_away(self, store):
        """Detection must not depend on whether the row was written.

        A trade is always written (the amount changed), but the two concerns are
        separate and a future change to the dedupe must not silently stop the
        tape.
        """
        store.record_leaderboard("24h", [self.trader(1000.0)])
        events = store.record_leaderboard(
            "24h", [self.trader(2000.0)], dedupe_holdings=False
        )
        assert len(events) == 1


class TestCopyProbesStayOutOfTheDeliveredPath:
    def test_a_copy_probe_never_becomes_a_prior_tier(self, store):
        """`TIER_PRIORITY` has no COPY entry, so a leak here is a KeyError.

        `best_tier_so_far` must ignore probes both because they are undelivered
        and because their tier is not a real tier.
        """
        store.record_alert(
            token_address="tokA", network_id=1399811149, ticker="A",
            tier="COPY PROBE", score=0.0, thesis_rank=-1, distinct_authors=1,
            leaderboard_authors=1, total_usd=0.0, reason="copy probe",
            delivered=False, suppressed_reason="copy-trade probe, never notified",
        )
        assert store.best_tier_so_far("tokA", 1399811149) is None

    def test_a_copy_probe_is_still_tracked_forward(self, store):
        """The probe exists to accumulate a forward sample, so it must be
        returned by the outcome tracker's query."""
        store.record_alert(
            token_address="tokA", network_id=1399811149, ticker="A",
            tier="COPY PROBE", score=0.0, thesis_rank=-1, distinct_authors=1,
            leaderboard_authors=1, total_usd=0.0, reason="copy probe",
            delivered=False, suppressed_reason="copy-trade probe, never notified",
        )
        assert store.alerted_tokens(include_suppressed=True) != []
        assert store.alerted_tokens() == []


class TestTickerLookup:
    def test_falls_back_to_the_fomo_token_table(self, store):
        store.record_items([mkitem("i1", token="tokA")])
        assert store.ticker_for("tokA") == "TST"

    def test_returns_none_for_an_unknown_mint(self, store):
        """Must not raise when the sibling radar's table is absent."""
        assert store.ticker_for("nope") is None
