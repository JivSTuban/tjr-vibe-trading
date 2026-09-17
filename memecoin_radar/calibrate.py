"""Derive alert thresholds from the collected score distribution.

Why this exists: the PRD's section 5 gates (WATCH > 60, HOT > 72, ULTRA > 84)
are stated as absolute numbers, but a score only means something relative to the
distribution the scorers actually produce. Measured on the first live sample
(66 tokens, 2026-09-17), those gates fire on 15.2%, 10.6%, and 0% of launches
respectively, which at ~23 launches/min is roughly 209/hour, 146/hour, and never.
A Discord channel accepts about 30/hour of useful traffic.

So thresholds here are expressed as a TARGET ALERT RATE and converted to score
cutoffs from the real distribution. That survives changes to the sub-scorers,
which an absolute number does not.

Run it after any meaningful collection period:
    PYTHONPATH=. uv run python -m memecoin_radar.calibrate
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass

from .config import OBSERVED_LAUNCHES_PER_MIN, load_config
from .store import Store

log = logging.getLogger("calibrate")

# Alerts per hour each tier should aim for. Chosen for a channel a person will
# actually keep reading, not for maximum recall: a tier nobody opens has an
# effective precision of zero.
TARGET_RATES_PER_HOUR: dict[str, float] = {
    "WATCH": 12.0,
    "HOT": 3.0,
    "ULTRA": 0.5,
}


@dataclass
class Calibration:
    tier: str
    target_per_hour: float
    required_percentile: float
    cutoff: float
    observed_fraction: float
    implied_per_hour: float
    sample_size: int
    resolvable: bool

    def line(self) -> str:
        mark = "" if self.resolvable else "   [sample too small to resolve]"
        return (
            f"  {self.tier:<6} target {self.target_per_hour:>5.1f}/h  "
            f"cutoff {self.cutoff:>5.1f}  "
            f"(p{self.required_percentile:.2f}, implied {self.implied_per_hour:>6.1f}/h){mark}"
        )


def best_scores(store: Store, kind: str = "moon") -> list[float]:
    """Highest score each token ever reached.

    Per token, not per snapshot: a token is alerted at most once per tier, so the
    alert rate depends on how many TOKENS cross a line, not how many rows do.
    """
    rows = store.conn.execute(
        "SELECT mint, MAX(score) AS s FROM scores WHERE kind = ? GROUP BY mint", (kind,)
    ).fetchall()
    return sorted(float(r["s"]) for r in rows)


def calibrate(
    scores: list[float],
    launches_per_min: float = OBSERVED_LAUNCHES_PER_MIN,
    targets: dict[str, float] | None = None,
) -> list[Calibration]:
    """Convert per-hour alert targets into score cutoffs."""
    targets = targets or TARGET_RATES_PER_HOUR
    out: list[Calibration] = []
    n = len(scores)
    if n == 0:
        return out

    launches_per_hour = launches_per_min * 60.0
    for tier, target in targets.items():
        fraction = min(1.0, target / launches_per_hour)
        percentile = (1.0 - fraction) * 100.0
        index = min(n - 1, int(n * percentile / 100.0))
        cutoff = scores[index]
        crossing = sum(1 for s in scores if s > cutoff)
        observed_fraction = crossing / n
        # A target rarer than one-in-sample-size cannot be resolved: the cutoff
        # would be an artefact of the single highest observation.
        resolvable = fraction * n >= 3.0
        out.append(
            Calibration(
                tier=tier,
                target_per_hour=target,
                required_percentile=percentile,
                cutoff=round(cutoff, 1),
                observed_fraction=observed_fraction,
                implied_per_hour=observed_fraction * launches_per_hour,
                sample_size=n,
                resolvable=resolvable,
            )
        )
    return out


def rate_at(scores: list[float], cutoff: float, launches_per_min: float) -> float:
    """Alerts per hour implied by a given cutoff."""
    if not scores:
        return 0.0
    fraction = sum(1 for s in scores if s > cutoff) / len(scores)
    return fraction * launches_per_min * 60.0


def report(store: Store) -> str:
    scores = best_scores(store)
    lines: list[str] = []
    if len(scores) < 20:
        return (
            f"Only {len(scores)} scored tokens. Collect for longer before calibrating; "
            "anything derived from this would be noise."
        )

    n = len(scores)
    def pct(p: float) -> float:
        return scores[min(n - 1, int(n * p / 100.0))]

    lines.append(f"Moon score distribution over {n} tokens")
    lines.append(
        f"  min {scores[0]:.1f}  p50 {pct(50):.1f}  p90 {pct(90):.1f}  "
        f"p99 {pct(99):.1f}  max {scores[-1]:.1f}"
    )
    lines.append("")
    lines.append("What the PRD section 5 gates would actually cost:")
    for name, cutoff in (("WATCH > 60", 60.0), ("HOT > 72", 72.0), ("ULTRA > 84", 84.0)):
        lines.append(f"  {name:<12} {rate_at(scores, cutoff, OBSERVED_LAUNCHES_PER_MIN):>8.1f} alerts/hour")
    lines.append("")
    lines.append("Rate-targeted cutoffs from this sample:")
    for cal in calibrate(scores):
        lines.append(cal.line())
    lines.append("")
    lines.append(
        "Copy the cutoffs into Thresholds in config.py only if the sample covers "
        "enough hours to be representative. One quiet afternoon is not a distribution."
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive alert thresholds from collected data")
    parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config()
    store = Store(cfg.db_path)
    try:
        print(report(store))
    finally:
        store.close()


if __name__ == "__main__":
    main()
