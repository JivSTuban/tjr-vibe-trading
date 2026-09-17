"""Scoring primitives shared by the Moon, Rug, and Trend Echo scorers.

The important idea here is `weighted_score`. The PRD assigns fixed weights, but
on a 30-second-old token several inputs genuinely do not exist yet: smart-money
needs the Phase 2 wallet leaderboard, social needs Phase 3, image similarity
needs an embedding model. Scoring a missing input as zero is not neutral, it is
a silent penalty, and with 40% of the Moon weight unmeasurable in Phase 1 it
would cap every token at 60 and make the PRD's own `Moon > 84` ULTRA gate
mathematically unreachable.

So a missing component is excluded and the remaining weights are renormalized,
with `coverage` recording how much of the intended evidence was actually present.
Coverage then gates the loud alert tiers, so a thin score cannot shout.
"""

from __future__ import annotations

import math

from ..models import ScoreBreakdown


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def saturating(value: float, midpoint: float, *, steepness: float = 1.0) -> float:
    """Map an unbounded positive measure onto 0-100, hitting 50 at `midpoint`.

    A logistic curve rather than a linear ramp because these inputs are
    heavy-tailed: the difference between 5 and 15 buyers in the first minute is
    meaningful, while the difference between 500 and 510 is noise, and a linear
    scale would let one outlier saturate the whole score.
    """
    if midpoint <= 0:
        return 0.0
    if value <= 0:
        return 0.0
    # log-ratio keeps the curve symmetric in multiplicative terms: 2x the
    # midpoint and half the midpoint sit equally far from 50.
    x = math.log(value / midpoint) * steepness
    return clamp(100.0 / (1.0 + math.exp(-x)))


def ratio_score(value: float, floor: float, ceiling: float) -> float:
    """Linear map of `value` from floor..ceiling onto 0..100, clamped.

    Used where the bounds are real rather than statistical, for example a buy
    share that genuinely cannot leave 0..1.
    """
    if ceiling <= floor:
        return 0.0
    return clamp((value - floor) / (ceiling - floor) * 100.0)


def inverse_score(value: float, floor: float, ceiling: float) -> float:
    """Like `ratio_score` but higher input means lower score."""
    return 100.0 - ratio_score(value, floor, ceiling)


def weighted_score(
    weights: dict[str, float],
    components: dict[str, float | None],
    *,
    reasons: list[str] | None = None,
) -> ScoreBreakdown:
    """Combine components into one 0-100 score, renormalizing over what exists.

    `components` values of None mean "not measurable right now", which is
    different from 0.0 meaning "measured, and it is bad".
    """
    available: dict[str, float] = {}
    missing: list[str] = []
    for key in weights:
        value = components.get(key)
        if value is None:
            missing.append(key)
            continue
        available[key] = clamp(float(value))

    total_weight = sum(weights.values())
    present_weight = sum(weights[k] for k in available)
    if present_weight <= 0 or total_weight <= 0:
        return ScoreBreakdown(
            score=0.0,
            components={},
            coverage=0.0,
            missing=missing,
            reasons=list(reasons or []),
        )

    score = sum(weights[k] * v for k, v in available.items()) / present_weight
    return ScoreBreakdown(
        score=round(clamp(score), 1),
        components={k: round(v, 1) for k, v in available.items()},
        coverage=round(present_weight / total_weight, 3),
        missing=missing,
        reasons=list(reasons or []),
    )
