"""Labeller tests. Network-free.

The load-bearing assertion is that SUPPRESSED alerts get labelled too. The
ENTER NOW gate refuses far more than it delivers, so a labeller that only
covered delivered alerts would make the gate unfalsifiable: there would be no
control group to show it was discarding winners.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fomo_radar.label import label_all
from fomo_radar.store import FomoStore


@pytest.fixture
def store(tmp_path: Path) -> FomoStore:
    s = FomoStore(tmp_path / "t.sqlite3")
    yield s
    s.close()


NET = 1399811149


def add_alert(store, token, *, delivered=True, suppressed=None, ticker="TST"):
    store.record_alert(
        token_address=token, network_id=NET, ticker=ticker, tier="ENTER",
        score=80.0, thesis_rank=3, distinct_authors=2, leaderboard_authors=1,
        total_usd=5000.0, reason="test", delivered=delivered,
        suppressed_reason=suppressed,
    )
    store.conn.commit()


def add_series(store, token, points):
    """points = [(age_seconds, market_cap_usd)] — liquidity scales with mcap.

    Liquidity is kept proportional to price so the pair-flip screen sees a
    stable liq/px ratio; a fixture with constant liquidity and a rising price
    would look like a pair change and get dropped.
    """
    for age, mcap in points:
        px = mcap / 1e6
        store.record_price_snapshot(
            token_address=token, network_id=NET, age_seconds=float(age),
            price_usd=px, market_cap_usd=float(mcap),
            liquidity_usd=px * 200.0, volume_h1_usd=1000.0, buys_m5=5, sells_m5=1,
        )
    store.conn.commit()


def outcomes(store):
    return store.conn.execute(
        "SELECT token_address, max_return_1h, entry_mcap_usd FROM fomo_outcomes"
    ).fetchall()


class TestLabelling:
    def test_labels_a_delivered_alert_with_enough_history(self, store):
        add_alert(store, "tok1")
        add_series(store, "tok1", [(0, 100_000), (1800, 150_000), (3600, 200_000)])

        tally = label_all(store)

        assert tally["labelled"] == 1
        assert tally["entered"] == 1
        rows = outcomes(store)
        assert len(rows) == 1
        assert rows[0]["entry_mcap_usd"] == 100_000
        # Peak within the 1h window is 200k against a 100k entry.
        assert rows[0]["max_return_1h"] == pytest.approx(1.0)

    def test_labels_suppressed_alerts_too_as_the_control_group(self, store):
        add_alert(store, "refused", delivered=False, suppressed="stale thesis")
        add_series(store, "refused", [(0, 50_000), (1800, 90_000), (3600, 100_000)])

        tally = label_all(store)

        assert tally["labelled"] == 1
        assert tally["suppressed"] == 1
        assert [r["token_address"] for r in outcomes(store)] == ["refused"]

    def test_skips_a_token_without_enough_forward_history(self, store):
        add_alert(store, "young")
        add_series(store, "young", [(0, 100_000), (300, 120_000)])

        tally = label_all(store)

        assert tally["labelled"] == 0
        assert tally["too_thin"] == 1
        assert outcomes(store) == []

    def test_a_delivery_failure_is_not_labelled(self, store):
        """delivered=0 with no suppression reason means nothing reached anyone."""
        add_alert(store, "failed", delivered=False, suppressed=None)
        add_series(store, "failed", [(0, 100_000), (3600, 300_000)])

        assert label_all(store)["considered"] == 0
        assert outcomes(store) == []

    def test_report_mode_writes_nothing(self, store):
        add_alert(store, "tok1")
        add_series(store, "tok1", [(0, 100_000), (1800, 150_000), (3600, 200_000)])

        tally = label_all(store, dry_run=True)

        assert tally["labelled"] == 1
        assert outcomes(store) == []

    def test_drops_a_pair_flip_corrupted_series(self, store):
        """The NVDAX shape: mcap jumps 186x while the price barely moves.

        `label_one` reads `market_cap_usd`, so without this screen the labeller
        reports a fabricated +18,605% as the best outcome in the book.
        """
        add_alert(store, "nvdax")
        for age, px, mcap, liq in [
            (0.0, 217.23, 217_231.0, 132_421.0),
            (900.0, 217.13, 40_464_248.0, 27_487.0),
            (3600.0, 218.04, 40_632_728.0, 132_811.0),
        ]:
            store.record_price_snapshot(
                token_address="nvdax", network_id=NET, age_seconds=age,
                price_usd=px, market_cap_usd=mcap, liquidity_usd=liq,
                volume_h1_usd=1000.0, buys_m5=5, sells_m5=1,
            )
        store.conn.commit()

        # `max_price_usd=0` disables the wrapped-asset screen, which would
        # otherwise catch NVDAX first (it is one) and hide what this asserts.
        tally = label_all(store, max_price_usd=0)

        assert tally["pair_flip"] == 1
        assert tally["labelled"] == 0
        assert outcomes(store) == []

    def test_removes_an_outcome_whose_series_is_now_known_corrupt(self, store):
        """A row labelled before the screen existed must not survive the fix.

        `record_outcome` upserts, so skipping the token would leave the bad row
        untouched forever. This is the NVDAX row that the first labeller run
        actually wrote.
        """
        add_alert(store, "tok1")
        add_series(store, "tok1", [(0, 100_000), (1800, 150_000), (3600, 200_000)])
        label_all(store)
        assert len(outcomes(store)) == 1

        # A later poll lands on a different pair, corrupting the series.
        store.record_price_snapshot(
            token_address="tok1", network_id=NET, age_seconds=7200.0,
            price_usd=0.2, market_cap_usd=40_000_000.0, liquidity_usd=27_487.0,
            volume_h1_usd=1000.0, buys_m5=5, sells_m5=1,
        )
        store.conn.commit()

        tally = label_all(store)

        assert tally["pair_flip"] == 1
        assert tally["unlabelled"] == 1
        assert outcomes(store) == []

    def test_report_mode_does_not_remove_a_stale_bad_row(self, store):
        add_alert(store, "tok1")
        add_series(store, "tok1", [(0, 100_000), (1800, 150_000), (3600, 200_000)])
        label_all(store)
        store.record_price_snapshot(
            token_address="tok1", network_id=NET, age_seconds=7200.0,
            price_usd=0.2, market_cap_usd=40_000_000.0, liquidity_usd=27_487.0,
            volume_h1_usd=1000.0, buys_m5=5, sells_m5=1,
        )
        store.conn.commit()

        tally = label_all(store, dry_run=True)

        assert tally["pair_flip"] == 1
        assert tally["unlabelled"] == 0
        assert len(outcomes(store)) == 1

    def test_relabelling_updates_rather_than_duplicating(self, store):
        add_alert(store, "tok1")
        add_series(store, "tok1", [(0, 100_000), (1800, 150_000), (3600, 200_000)])
        label_all(store)
        add_series(store, "tok1", [(21_600, 500_000)])

        label_all(store)

        rows = store.conn.execute(
            "SELECT max_return_6h FROM fomo_outcomes WHERE token_address='tok1'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["max_return_6h"] == pytest.approx(4.0)


class TestWrappedAssetScreen:
    """8 of the first 12 rows in `fomo_outcomes` were tokenised equities.

    A median computed across those describes an equity tracker, not a meme
    coin. The alert gate (`SignalConfig.max_price_usd`) stops NEW ones arriving;
    this screen keeps them out of the outcome table and removes the ones already
    written, which gating the alert path alone would have left in place.
    """

    def wrapped(self, store, token="msftx", px=500.43):
        add_alert(store, token)
        for age in (0.0, 1800.0, 3600.0):
            store.record_price_snapshot(
                token_address=token, network_id=NET, age_seconds=age,
                price_usd=px, market_cap_usd=500_435.0, liquidity_usd=px * 200,
                volume_h1_usd=1000.0, buys_m5=5, sells_m5=1,
            )
        store.conn.commit()

    def test_a_wrapped_asset_is_not_labelled(self, store):
        self.wrapped(store)
        tally = label_all(store)
        assert tally["wrapped_asset"] == 1
        assert tally["labelled"] == 0
        assert outcomes(store) == []

    def test_a_row_written_before_the_screen_is_removed(self, store):
        self.wrapped(store)
        label_all(store, max_price_usd=0)   # labelled under the old rules
        assert len(outcomes(store)) == 1

        tally = label_all(store)            # now screened

        assert tally["unlabelled"] == 1
        assert outcomes(store) == []

    def test_a_real_meme_coin_price_still_labels(self, store):
        """SPX at $0.4716 was the priciest genuine meme coin observed."""
        self.wrapped(store, token="spx", px=0.4716)
        tally = label_all(store)
        assert tally["wrapped_asset"] == 0
        assert tally["labelled"] == 1
