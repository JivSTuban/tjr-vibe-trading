"""Regression tests for the evidence floor on upside alerts.

Written from a real failure. The first live run posted this to Discord:

    WATCH · $2LV4Ad     unnamed (2LV4Ad)
    Moon 95/100 (5% evidence)     Rug 8/100 (37% evidence)
    Age 18s    Market cap $3.0K    Liquidity unknown
    Volume unknown    0 buys / 0 sells
    Why this fired: still ~$2,990 market cap

A 95 out of 100, on a token nobody had bought, because early-entry (weight 0.05)
was the only measurable component and "market cap is small" is trivially true of
every newborn token. Renormalizing over available weights is correct in general,
but with a single trivial component it manufactures confidence, and the coverage
gate only guarded HOT and ULTRA so WATCH published it anyway.
"""

from __future__ import annotations

from memecoin_radar.alerts import decide
from memecoin_radar.config import Thresholds
from memecoin_radar.features import compute_flow
from memecoin_radar.models import ScoreBreakdown
from memecoin_radar.scoring.moon import score_moon
from memecoin_radar.scoring.rug import score_rug

from .conftest import make_snapshots

TH = Thresholds()


def test_the_exact_live_failure_no_longer_alerts(candidate):
    """Reproduce the $2LV4Ad case: one snapshot, no buyers, no volume."""
    snaps = make_snapshots(candidate.mint, [(15, 0.0, 0, 0)])
    snaps[0].market_cap_usd = 2_990.0
    snaps[0].liquidity_usd = 0.0
    candidate.snapshots = snaps

    feat = compute_flow(snaps)
    candidate.moon = score_moon(candidate, feat, smart_wallets={})
    candidate.rug = score_rug(candidate, feat, deployer_launches=1, deployer_rugs=0)

    # The score itself can still be high, since it honestly reports the only
    # thing measurable. What must not happen is it reaching the channel.
    assert candidate.moon.coverage < TH.min_coverage_alert
    assert decide(candidate, TH) == []


def test_low_coverage_blocks_even_watch(candidate):
    candidate.moon = ScoreBreakdown(score=95.0, coverage=0.05, components={"early_entry": 95.0})
    candidate.rug = ScoreBreakdown(score=8.0, coverage=0.37)
    assert decide(candidate, TH) == []


def test_no_flow_evidence_blocks_upside_alerts(candidate):
    """Coverage can be adequate while still containing no buying at all."""
    candidate.moon = ScoreBreakdown(
        score=95.0,
        coverage=0.90,
        components={"narrative": 90.0, "early_entry": 95.0, "liquidity_quality": 80.0},
    )
    candidate.rug = ScoreBreakdown(score=5.0, coverage=0.9)
    tiers = [a.alert_type for a in decide(candidate, TH)]
    assert tiers == []


def test_flow_evidence_permits_the_alert(candidate):
    candidate.moon = ScoreBreakdown(
        score=95.0,
        coverage=0.50,
        components={"volume_acceleration": 95.0, "early_entry": 95.0},
    )
    candidate.rug = ScoreBreakdown(score=5.0, coverage=0.9)
    assert "ULTRA" in [a.alert_type for a in decide(candidate, TH)]


def test_rug_warning_still_fires_without_flow_evidence(candidate):
    """Danger is not an upside claim, so the evidence floor must not mute it.

    A token that is structurally dangerous is worth saying so about even before
    anyone has bought it.
    """
    candidate.moon = ScoreBreakdown(score=95.0, coverage=0.05, components={"early_entry": 95.0})
    candidate.rug = ScoreBreakdown(score=88.0, coverage=0.7, reasons=["creator holds 100%"])
    assert [a.alert_type for a in decide(candidate, TH)] == ["RUG_WARNING"]


def test_evidence_floor_is_below_phase1_ceiling():
    """The floor must not be so high that a real launch can never clear it."""
    assert TH.min_coverage_alert < 0.50
    assert TH.min_coverage_alert <= TH.min_coverage_hot


def test_trend_echo_activity_floor_is_satisfiable_on_the_free_path(candidate):
    """TREND_ECHO must be reachable without the metered trade stream.

    Its floor previously read buy_count/sol_volume, which only the paid
    PumpPortal stream populates, making the tier unreachable on a free
    deployment. Activity now comes from the DexScreener snapshot series.
    """
    from memecoin_radar.alerts import early_activity

    snaps = make_snapshots(candidate.mint, [(15, 200.0, 4, 1), (60, 900.0, 22, 3)])
    candidate.snapshots = snaps
    # Nothing from the trade stream, exactly as on a free deployment.
    assert candidate.buy_count == 0 and candidate.sol_volume == 0.0

    buys, volume = early_activity(candidate)
    assert buys == 22 and volume == 900.0
    assert buys >= TH.trend_echo_min_buys
    assert volume >= TH.trend_echo_min_volume_usd

    candidate.moon = ScoreBreakdown(
        score=60.0, coverage=0.5, components={"volume_acceleration": 60.0}
    )
    candidate.rug = ScoreBreakdown(score=10.0, coverage=0.7)
    candidate.trend = ScoreBreakdown(score=85.0, coverage=0.7, reasons=["echoes $FROG"])
    assert "TREND_ECHO" in [a.alert_type for a in decide(candidate, TH)]


def test_trend_echo_still_blocked_with_no_activity(candidate):
    snaps = make_snapshots(candidate.mint, [(15, 0.0, 0, 0)])
    candidate.snapshots = snaps
    candidate.moon = ScoreBreakdown(score=60.0, coverage=0.5,
                                    components={"volume_acceleration": 60.0})
    candidate.rug = ScoreBreakdown(score=10.0, coverage=0.7)
    candidate.trend = ScoreBreakdown(score=95.0, coverage=0.7)
    assert "TREND_ECHO" not in [a.alert_type for a in decide(candidate, TH)]
