"""The live Trend Context: which tokens and narratives are hot right now.

PRD section 4.1 asks for a rolling hot set refreshed every 15-30 seconds. The
question is where "hot" comes from without a paid trending feed.

Deliberately NOT DexScreener's boosts endpoint: boosts are paid promotion, and
PRD section 10 requires paid placement to be shown as paid rather than treated as
organic traction. Seeding the trend set from boosts would bake advertising into
the thing the radar calls a narrative.

Instead the trend set is built from the radar's own stream. Because every launch
is recorded and snapshotted, the tokens that actually gained volume and market
cap in the last few hours are already known locally, for free, with no survivor
filtering by a third party. Migration events (a token graduating off the bonding
curve) are folded in as the strongest evidence of a real move.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from .models import Candidate, TrendReference, utcnow
from .scoring.trend_echo import tokenize

log = logging.getLogger(__name__)

# How long a token stays eligible to be a trend reference. Meme narratives turn
# over in hours, and an all-day window would keep matching clones against dead
# trends, which is the failure mode that makes an echo radar useless.
TREND_TTL = timedelta(hours=6)

MAX_REFERENCES = 40

# Floors for a token to count as a reference at all, in USD.
MIN_TREND_MCAP = 25_000.0
MIN_TREND_VOLUME = 5_000.0


class TrendContext:
    """Rolling set of hot reference tokens, updated as candidates mature."""

    def __init__(self, max_references: int = MAX_REFERENCES) -> None:
        self._refs: dict[str, TrendReference] = {}
        self.max_references = max_references

    def __len__(self) -> int:
        return len(self._refs)

    def references(self) -> list[TrendReference]:
        """Live references, freshest and strongest first."""
        self.prune()
        return sorted(self._refs.values(), key=lambda r: r.trend_score, reverse=True)

    def prune(self) -> None:
        cutoff = utcnow() - TREND_TTL
        stale = [m for m, r in self._refs.items() if r.updated_at < cutoff]
        for mint in stale:
            del self._refs[mint]

    def consider(self, cand: Candidate, *, migrated: bool = False) -> TrendReference | None:
        """Promote a candidate into the trend set if it has actually moved.

        Called as candidates mature through enrichment, so today's clone target
        is simply yesterday's launch that worked. A migrated token is admitted
        regardless of the volume floor, since graduating off the curve is
        stronger evidence than any snapshot threshold.
        """
        snaps = cand.snapshots
        if not snaps:
            return None
        latest = snaps[-1]
        if not migrated and (
            latest.market_cap_usd < MIN_TREND_MCAP or latest.volume_usd < MIN_TREND_VOLUME
        ):
            return None

        keywords = tokenize(f"{cand.launch.name} {cand.launch.symbol}")
        narrative = keywords | tokenize(cand.metadata.description)
        # Trend strength blends size with flow so a large but dead token does not
        # outrank a smaller one that is actively running.
        trend_score = latest.market_cap_usd / 1000.0 + latest.volume_usd / 500.0
        if migrated:
            trend_score *= 1.5

        existing = self._refs.get(cand.mint)
        if existing is not None:
            existing.market_cap_usd = latest.market_cap_usd
            existing.liquidity_usd = latest.liquidity_usd
            existing.volume_accel = latest.volume_usd
            existing.trend_score = trend_score
            existing.momentum_state = self._momentum_state(cand, migrated=migrated)
            existing.narrative_tokens = narrative
            existing.keywords = keywords
            existing.updated_at = utcnow()
            return existing

        ref = TrendReference(
            mint=cand.mint,
            name=cand.launch.name,
            symbol=cand.launch.symbol,
            narrative_tokens=narrative,
            keywords=keywords,
            creator=cand.launch.creator,
            market_cap_usd=latest.market_cap_usd,
            liquidity_usd=latest.liquidity_usd,
            volume_accel=latest.volume_usd,
            momentum_state=self._momentum_state(cand, migrated=migrated),
            trend_score=trend_score,
            first_seen=cand.launch.seen_at,
            updated_at=utcnow(),
        )
        self._refs[cand.mint] = ref
        self._evict()
        log.info("trend context += $%s (%d refs)", ref.symbol, len(self._refs))
        return ref

    @staticmethod
    def _momentum_state(cand: Candidate, *, migrated: bool) -> str:
        """Classify where the reference sits in its own arc (PRD section 4.1)."""
        if migrated:
            return "accelerating"
        snaps = cand.snapshots
        if len(snaps) < 3:
            return "emerging"
        recent = snaps[-1].volume_usd - snaps[-2].volume_usd
        prior = snaps[-2].volume_usd - snaps[-3].volume_usd
        if prior <= 0:
            return "accelerating" if recent > 0 else "cooling"
        ratio = recent / prior
        if ratio >= 1.2:
            return "accelerating"
        if ratio >= 0.6:
            return "peak"
        return "cooling"

    def _evict(self) -> None:
        if len(self._refs) <= self.max_references:
            return
        ranked = sorted(self._refs.values(), key=lambda r: r.trend_score, reverse=True)
        for ref in ranked[self.max_references :]:
            self._refs.pop(ref.mint, None)
