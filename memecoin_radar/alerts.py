"""Alert decisions: PRD section 5 levels, plus the suppression rules from section 10.

Three rules do the real work here:

1. Rug never merges into Moon. A high relation or a high Moon cannot cancel a
   high Rug; danger is reported alongside upside, never netted against it.
2. Alerts escalate, they do not repeat. A token that fired WATCH only fires
   again for a strictly louder tier, otherwise one launch would spam the channel
   at every enrichment tick.
3. Coverage gates loudness. A score assembled from a third of the intended
   evidence cannot reach HOT or ULTRA, because at that point the number is a
   guess wearing a decimal point.
"""

from __future__ import annotations

from .config import Thresholds
from .models import Alert, Candidate, utcnow

# Loudness order, used for escalation and for send priority.
TIER_RANK: dict[str, int] = {
    "WATCH": 1,
    "SMART_MONEY": 2,
    "TREND_ECHO": 2,
    "HOT": 3,
    "ULTRA": 4,
}

SEND_PRIORITY: dict[str, int] = {
    "ULTRA": 0,
    "TREND_ECHO": 1,
    "SMART_MONEY": 1,
    "HOT": 2,
    "RUG_WARNING": 3,
    "WATCH": 4,
}


def _already_louder(cand: Candidate, tier: str) -> bool:
    """True when this token already fired something at least as loud."""
    rank = TIER_RANK.get(tier, 0)
    return any(TIER_RANK.get(fired, 0) >= rank for fired in cand.alerts_fired)


# An upside claim has to rest on observed FLOW. Without one of these components
# the score is describing the token's existence, not anyone buying it.
FLOW_COMPONENTS = ("volume_acceleration", "unique_buyer_acceleration")


def early_activity(cand: Candidate) -> tuple[int, float]:
    """Observed early buying as (buy count, volume in USD).

    Prefers the snapshot series, which is populated on the free path from
    DexScreener, and falls back to the trade-stream counters that only exist
    when the metered PumpPortal stream is enabled. Reading only the counters is
    what made the TREND_ECHO activity floor unsatisfiable for a free deployment.
    """
    if cand.snapshots:
        latest = cand.snapshots[-1]
        if latest.buys or latest.volume_usd:
            return latest.buys, latest.volume_usd
    return cand.buy_count + len(cand.buyers), 0.0


def _has_flow_evidence(cand: Candidate) -> bool:
    """Whether any flow component was actually measured.

    Guards the failure seen live: a token with zero buys and no volume scored
    Moon 95 off early-entry alone. Upside needs someone buying, not merely a
    low market cap.
    """
    if cand.moon is None:
        return False
    return any(k in cand.moon.components for k in FLOW_COMPONENTS)


def peak_liquidity(cand: Candidate) -> float:
    """Best liquidity in USD observed across the snapshot series.

    The PEAK rather than the latest reading, because a token is judged on
    whether it ever became tradeable at all and one stale snapshot should not
    veto a name that is actively filling out.
    """
    if not cand.snapshots:
        return 0.0
    return max((s.liquidity_usd or 0.0) for s in cand.snapshots)


def _is_tradeable(cand: Candidate, th: Thresholds) -> tuple[bool, str]:
    """Could a human actually take and exit a position in this token?

    Added 2026-09-17 after auditing what this radar had delivered. Across its
    44 upside alerts, peak liquidity medianed **$3,257** with a p75 of $3,419 —
    the bonding-curve floor, i.e. no market. All of them passed
    `_has_flow_evidence` (median peak buy count 82), because buys are not the
    same thing as a market: at $3k liquidity there is no exit at any size worth
    taking. The distribution has a sharp gap — 37 of 44 never left ~$3.3k while
    7 developed real markets — and the floor sits inside it.

    `_has_flow_evidence` asks whether anyone traded. This asks whether the
    result is a market. Both are required.

    Liquidity only, deliberately: Moon scores early entry, so it REWARDS a low
    market cap, and gating on cap would fight this radar's own premise.
    """
    liq = peak_liquidity(cand)
    if liq < th.min_alert_liquidity_usd:
        return False, f"peak liquidity ${liq:,.0f} < ${th.min_alert_liquidity_usd:,.0f}"
    return True, ""


def decide(cand: Candidate, th: Thresholds) -> list[Alert]:
    """Return the alerts this candidate should fire right now, possibly none."""
    if cand.moon is None or cand.rug is None:
        return []

    moon, rug = cand.moon, cand.rug
    relation = cand.trend.score if cand.trend else 0.0
    out: list[Alert] = []
    now = utcnow()

    def fire(tier: str, reasons: list[str]) -> None:
        out.append(
            Alert(
                mint=cand.mint,
                ts=now,
                alert_type=tier,
                moon_score=moon.score,
                rug_score=rug.score,
                relation_score=relation,
                reasons=reasons,
            )
        )
        cand.alerts_fired.add(tier)

    # Structural danger is its own notification and is never suppressed by a
    # good-looking Moon score.
    if rug.score >= th.rug_warning and "RUG_WARNING" not in cand.alerts_fired:
        fire("RUG_WARNING", rug.reasons or ["rug score above warning threshold"])

    # Trend Echo is a discovery signal, so it needs real early activity behind
    # it. Without the activity floor, every name-alike in a 24/min firehose
    # would ping the channel.
    buys, volume_usd = early_activity(cand)
    if (
        cand.trend is not None
        and relation >= th.trend_echo_relation
        and buys >= th.trend_echo_min_buys
        and volume_usd >= th.trend_echo_min_volume_usd
        and "TREND_ECHO" not in cand.alerts_fired
    ):
        fire("TREND_ECHO", cand.trend.reasons + moon.reasons)

    if (
        len(cand.smart_wallets) >= th.smart_money_wallets
        and "SMART_MONEY" not in cand.alerts_fired
    ):
        fire("SMART_MONEY", [f"{len(cand.smart_wallets)} tracked wallets entered"])

    # Upside tiers, loudest first so one pass cannot fire both HOT and ULTRA.
    # Three preconditions apply to every tier including WATCH: enough of the
    # intended evidence was measurable, some of it was actual buying, and the
    # token is liquid enough that a position could be exited. The third was
    # missing until 2026-09-17 and is why 40 of 44 upside alerts were on tokens
    # that never passed $50k market cap.
    if moon.coverage < th.min_coverage_alert or not _has_flow_evidence(cand):
        return out
    tradeable, why = _is_tradeable(cand, th)
    if not tradeable:
        cand.suppressed_reason = why
        return out

    if (
        moon.score > th.ultra_moon
        and rug.score < th.ultra_rug_max
        and moon.coverage >= th.min_coverage_ultra
        and not _already_louder(cand, "ULTRA")
    ):
        fire("ULTRA", moon.reasons)
    elif (
        moon.score > th.hot_moon
        and rug.score < th.hot_rug_max
        and moon.coverage >= th.min_coverage_hot
        and not _already_louder(cand, "HOT")
    ):
        fire("HOT", moon.reasons)
    elif (
        moon.score > th.watch_moon
        and rug.score < th.watch_rug_max
        and not _already_louder(cand, "WATCH")
    ):
        fire("WATCH", moon.reasons)

    return out


def sort_for_send(alerts: list[Alert]) -> list[Alert]:
    """Order a batch so the loudest thing reaches a rate-limited channel first."""
    return sorted(alerts, key=lambda a: (SEND_PRIORITY.get(a.alert_type, 9), -a.moon_score))
