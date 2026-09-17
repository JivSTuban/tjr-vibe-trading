"""Alert-decision and delivery tests.

These encode the product rules that keep the channel usable at 24 launches/min:
escalation instead of repetition, danger never netted against upside, and loud
alerts protected from being crowded out by quiet ones.
"""

from __future__ import annotations

import asyncio

from memecoin_radar.alerts import decide, sort_for_send
from memecoin_radar.config import Thresholds
from memecoin_radar.discord_sink import DiscordSink, build_embed
from memecoin_radar.models import Alert, Candidate, ScoreBreakdown, utcnow

from .conftest import make_snapshots


TH = Thresholds()

# Derived from the live gates, not hard-coded: recalibrating thresholds must not
# silently turn these behavioural tests into tests of nothing.
WATCH_LEVEL = TH.watch_moon + 2.0
HOT_LEVEL = TH.hot_moon + 2.0
ULTRA_LEVEL = TH.ultra_moon + 2.0


def _scored(cand: Candidate, moon: float, rug: float, relation: float = 0.0,
            coverage: float = 1.0) -> Candidate:
    """Score a candidate for TIERING tests.

    Always includes a flow component, because upside alerts now require observed
    buying. The evidence floor itself is tested in test_evidence_floor.py.
    """
    cand.moon = ScoreBreakdown(
        score=moon,
        coverage=coverage,
        components={"volume_acceleration": moon},
        reasons=["flow accelerating"],
    )
    cand.rug = ScoreBreakdown(score=rug, coverage=coverage, reasons=["creator holds a lot"])
    if relation:
        cand.trend = ScoreBreakdown(score=relation, coverage=0.85, reasons=["name echoes $FROG"])
    return cand


def test_no_alert_before_scoring(candidate):
    assert decide(candidate, TH) == []


def test_watch_fires_then_does_not_repeat(candidate):
    _scored(candidate, moon=WATCH_LEVEL, rug=20.0)
    first = decide(candidate, TH)
    assert [a.alert_type for a in first] == ["WATCH"]
    assert decide(candidate, TH) == []


def test_escalation_from_watch_to_hot(candidate):
    _scored(candidate, moon=WATCH_LEVEL, rug=20.0)
    decide(candidate, TH)
    _scored(candidate, moon=HOT_LEVEL, rug=20.0)
    assert [a.alert_type for a in decide(candidate, TH)] == ["HOT"]


def test_ultra_does_not_also_fire_hot(candidate):
    _scored(candidate, moon=ULTRA_LEVEL, rug=10.0)
    tiers = [a.alert_type for a in decide(candidate, TH)]
    assert tiers == ["ULTRA"]


def test_no_downgrade_after_ultra(candidate):
    _scored(candidate, moon=ULTRA_LEVEL, rug=10.0)
    decide(candidate, TH)
    _scored(candidate, moon=WATCH_LEVEL, rug=10.0)
    assert decide(candidate, TH) == []


def test_high_rug_blocks_the_bullish_tiers(candidate):
    _scored(candidate, moon=ULTRA_LEVEL + 4, rug=75.0)
    tiers = [a.alert_type for a in decide(candidate, TH)]
    # The danger is reported; the upside tier is not.
    assert "RUG_WARNING" in tiers
    assert "ULTRA" not in tiers and "HOT" not in tiers


def test_rug_warning_fires_independently_of_moon(candidate):
    _scored(candidate, moon=5.0, rug=88.0)
    assert "RUG_WARNING" in [a.alert_type for a in decide(candidate, TH)]


def test_low_coverage_cannot_reach_ultra(candidate):
    """A 90 built from a third of the evidence must not shout."""
    _scored(candidate, moon=ULTRA_LEVEL, rug=10.0, coverage=0.30)
    tiers = [a.alert_type for a in decide(candidate, TH)]
    assert "ULTRA" not in tiers and "HOT" not in tiers
    assert tiers == ["WATCH"]


def test_trend_echo_needs_real_early_activity(candidate):
    """Relation alone must not ping; activity comes from the snapshot series."""
    _scored(candidate, moon=50.0, rug=20.0, relation=92.0)
    candidate.snapshots = make_snapshots(candidate.mint, [(15, 0.0, 0, 0)])
    assert "TREND_ECHO" not in [a.alert_type for a in decide(candidate, TH)]

    candidate.alerts_fired.clear()
    candidate.snapshots = make_snapshots(candidate.mint, [(15, 120.0, 3, 0),
                                                          (60, 1_400.0, 18, 2)])
    assert "TREND_ECHO" in [a.alert_type for a in decide(candidate, TH)]


def test_smart_money_escalates(candidate):
    _scored(candidate, moon=30.0, rug=10.0)
    candidate.smart_wallets = {"W1", "W2"}
    assert "SMART_MONEY" in [a.alert_type for a in decide(candidate, TH)]


def test_send_order_puts_ultra_first():
    now = utcnow()
    alerts = [
        Alert(mint="a", ts=now, alert_type="WATCH", moon_score=61, rug_score=1, relation_score=0),
        Alert(mint="b", ts=now, alert_type="ULTRA", moon_score=90, rug_score=1, relation_score=0),
        Alert(mint="c", ts=now, alert_type="HOT", moon_score=75, rug_score=1, relation_score=0),
    ]
    assert [a.alert_type for a in sort_for_send(alerts)] == ["ULTRA", "HOT", "WATCH"]


# ------------------------------------------------------------------ delivery

def test_embed_shows_contract_scores_and_disclaimer(candidate):
    _scored(candidate, moon=HOT_LEVEL, rug=25.0)
    candidate.snapshots = make_snapshots(candidate.mint, [(60, 5000.0, 40, 3)])
    alert = decide(candidate, TH)[0]
    embed = build_embed(alert, candidate)

    text = str(embed)
    assert candidate.mint in text  # contract address shown in full
    assert "Moon" in text and "Rug" in text
    assert "guarantee" not in text.lower()
    assert "Extreme-risk microcap" in embed["footer"]["text"]
    # Coverage travels with the score so a thin number cannot pose as a thick one.
    assert "evidence" in text


def test_embed_reports_coverage_percentage(candidate):
    _scored(candidate, moon=WATCH_LEVEL, rug=10.0, coverage=0.5)
    alert = decide(candidate, TH)[0]
    embed = build_embed(alert, candidate)
    assert "50%" in str(embed)


def test_sink_sheds_quiet_alerts_when_the_minute_budget_is_nearly_spent(candidate):
    sink = DiscordSink("", max_per_min=4, dry_run=True)
    now = 1000.0

    # Simulate 3 of 4 sends already used this minute.
    import time as _time
    monotonic = _time.monotonic()
    sink._sent_times = [monotonic, monotonic, monotonic]

    quiet = Alert(mint="a", ts=utcnow(), alert_type="WATCH", moon_score=61,
                  rug_score=1, relation_score=0)
    loud = Alert(mint="b", ts=utcnow(), alert_type="ULTRA", moon_score=90,
                 rug_score=1, relation_score=0)
    assert sink._may_send(quiet) is False
    assert sink._may_send(loud) is True
    del now


def test_sink_refuses_everything_once_the_hour_budget_is_gone():
    sink = DiscordSink("", max_per_min=10, max_per_hour=2, dry_run=True)
    import time as _time
    sink._sent_times = [_time.monotonic(), _time.monotonic()]
    loud = Alert(mint="b", ts=utcnow(), alert_type="ULTRA", moon_score=90,
                 rug_score=1, relation_score=0)
    assert sink._may_send(loud) is False


def test_dry_run_send_succeeds_without_network(candidate):
    _scored(candidate, moon=HOT_LEVEL, rug=10.0)
    alert = decide(candidate, TH)[0]

    async def go():
        async with DiscordSink("", dry_run=True) as sink:
            return await sink.send(alert, candidate)

    assert asyncio.run(go()) is True


def test_embed_falls_back_when_the_launch_has_no_name(candidate):
    """Live stream carries launches with an empty name and ticker."""
    candidate.launch.name = ""
    candidate.launch.symbol = ""
    _scored(candidate, moon=HOT_LEVEL, rug=10.0)
    embed = build_embed(decide(candidate, TH)[0], candidate)
    assert "$ " not in embed["title"] and not embed["title"].endswith("$")
    assert candidate.mint[:6] in embed["title"]
    assert candidate.mint[:6] in embed["description"]
