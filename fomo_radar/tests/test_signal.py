"""Signal tests.

These pin the conclusions from `research/fomo/FINDINGS.md` so a later "let's
make it fire more" tune cannot silently undo a measured result. Network-free.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from fomo_radar.config import SignalConfig
from fomo_radar.signal import TIER_CONVICTION, TIER_HOT, WATCH_FLOOR, evaluate

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def mkstats(**over):
    base = {
        "ticker": "TEST",
        "first_thesis_at": (NOW - timedelta(minutes=10)).isoformat(),
        "last_thesis_at": NOW.isoformat(),
        "thesis_count": 3,
        "qualified_count": 3,
        "distinct_authors": 3,
        "leaderboard_authors": 0,
        "max_usd": 6000.0,
        "total_usd": 12000.0,
    }
    base.update(over)
    return base


def ev(rank=0, has_x=False, **over):
    return evaluate(
        token_address="tok", network_id=1399811149, ticker="TEST",
        stats=mkstats(**over), thesis_rank=rank, has_x_link=has_x, now=NOW,
    )


class TestEarliness:
    """Earliness is the one component the data actually supports."""

    def test_first_thesis_scores_highest(self):
        assert ev(rank=0).score > ev(rank=2).score > ev(rank=5).score

    def test_score_is_monotonically_non_increasing_in_rank(self):
        scores = [ev(rank=r).score for r in range(0, 10)]
        assert scores == sorted(scores, reverse=True)

    def test_past_the_early_window_never_alerts(self):
        """Beyond max_thesis_rank the measured edge collapsed to the base rate."""
        cfg = SignalConfig()
        sig = ev(rank=cfg.max_thesis_rank)
        assert sig.tier is None

    def test_rank_gate_is_conjunctive_not_scored_away(self):
        """A late thesis cannot buy its way in with size and authors."""
        sig = ev(rank=50, max_usd=500_000.0, distinct_authors=20, leaderboard_authors=5)
        assert sig.tier is None


class TestXLinkIsNotScored:
    """The X link is a size proxy that inverts above $5k — context, not signal."""

    def test_x_link_does_not_change_score(self):
        assert ev(has_x=True).score == ev(has_x=False).score

    def test_x_link_does_not_change_tier(self):
        assert ev(has_x=True).tier == ev(has_x=False).tier

    def test_x_link_is_still_reported(self):
        assert ev(has_x=True).has_x_link is True


class TestConfirmation:
    def test_single_author_never_alerts(self):
        """One handle posting repeatedly is not confirmation; observed 3x/4min."""
        assert ev(distinct_authors=1, qualified_count=1).tier is None

    def test_more_distinct_authors_scores_higher(self):
        assert ev(distinct_authors=4).score > ev(distinct_authors=2).score

    def test_below_min_size_never_alerts(self):
        cfg = SignalConfig()
        assert ev(max_usd=cfg.min_thesis_usd - 1).tier is None


class TestLeaderboardIsQualityNotDiscovery:
    def test_leaderboard_lifts_tier(self):
        plain = ev(rank=1, leaderboard_authors=0)
        lifted = ev(rank=1, leaderboard_authors=2)
        assert lifted.score > plain.score

    def test_leaderboard_cannot_create_a_candidate_on_its_own(self):
        """Leaderboard presence must not rescue a token failing the real gates."""
        sig = ev(rank=99, leaderboard_authors=5, distinct_authors=1, qualified_count=1)
        assert sig.tier is None


class TestTiers:
    def test_strong_early_multi_author_is_top_tier(self):
        sig = ev(rank=0, distinct_authors=5, max_usd=40_000.0, leaderboard_authors=2)
        assert sig.tier == TIER_CONVICTION

    def test_marginal_case_is_not_top_tier(self):
        sig = ev(rank=5, distinct_authors=2, max_usd=1500.0)
        assert sig.tier in (None, "WATCH")

    @pytest.mark.parametrize("rank", [0, 1, 2])
    def test_early_and_confirmed_always_alerts(self, rank):
        sig = ev(rank=rank, distinct_authors=4, max_usd=30_000.0)
        assert sig.tier in (TIER_CONVICTION, TIER_HOT)


class TestReachability:
    """Every tier must be reachable with plausible inputs.

    Four alert tiers in memecoin_radar shipped silently unreachable, and a tier
    that cannot fire looks exactly like a quiet market. This is that guard.
    """

    def test_all_tiers_reachable(self):
        seen = set()
        for rank in range(0, 10):
            for authors in (2, 3, 5):
                for usd in (1500.0, 8000.0, 50_000.0):
                    for lb in (0, 1, 2):
                        s = ev(rank=rank, distinct_authors=authors,
                               qualified_count=authors, max_usd=usd,
                               leaderboard_authors=lb)
                        if s.tier:
                            seen.add(s.tier)
        assert seen == {"WATCH", "HOT", "CONVICTION"}, f"unreachable tiers: {seen}"

    def test_most_tokens_do_not_alert(self):
        """A quiet channel is the expected steady state, not a malfunction."""
        assert ev(rank=12, distinct_authors=1, qualified_count=1, max_usd=200.0).tier is None

    def test_no_dead_band_above_the_gates(self):
        """Anything that clears every hard gate must reach at least WATCH.

        Regression guard for a real defect: the weakest eligible combination
        scores 47, and with the WATCH floor at 50 such a token passed every gate
        and then silently produced nothing. Found by replaying 2,374 harvested
        theses, not by inspection. The floor is derived here rather than
        hard-coded so tuning a weight cannot re-open the gap.
        """
        cfg = SignalConfig()
        weakest = evaluate(
            token_address="tok", network_id=1399811149, ticker="TEST",
            stats=mkstats(
                distinct_authors=cfg.min_distinct_authors,
                qualified_count=cfg.min_distinct_authors,
                max_usd=cfg.min_thesis_usd,
                leaderboard_authors=0,
            ),
            thesis_rank=cfg.max_thesis_rank - 1,
            has_x_link=False,
            now=NOW,
        )
        assert weakest.tier is not None, (
            f"eligible token scores {weakest.score} but falls below every tier — "
            "dead band between the gates and WATCH"
        )
        assert weakest.score >= WATCH_FLOOR
