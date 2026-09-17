"""Moon Score: upside and momentum, PRD section 3.1.

Weights are exactly the PRD's. What differs from a naive reading is which
components can exist in Phase 1:

  measurable now   volume acceleration, liquidity quality, early-entry advantage,
                   narrative quality (once metadata lands)
  proxied          unique buyer acceleration, via buy-TRANSACTION acceleration,
                   marked as a proxy because DexScreener counts txs not wallets
  unavailable      smart-wallet activity (PRD Phase 2 leaderboard),
                   social velocity and cross-platform propagation (Phase 3),
                   holder growth (needs a paid or heavily rate-limited holder feed)

Unavailable components are excluded and the rest renormalized, so the score
always means "of the evidence we could gather, this is how strong it looks",
with coverage attached.
"""

from __future__ import annotations

from ..features import FlowFeatures
from ..models import Candidate, ScoreBreakdown
from . import ratio_score, saturating, weighted_score

WEIGHTS: dict[str, float] = {
    "volume_acceleration": 0.20,
    "smart_money": 0.20,
    "unique_buyer_acceleration": 0.15,
    "social_velocity": 0.15,
    "holder_growth": 0.10,
    "cross_platform": 0.05,
    "liquidity_quality": 0.05,
    "narrative": 0.05,
    "early_entry": 0.05,
}

# A launch is "early" below this cap, so a token already at a large valuation
# scores no early-entry advantage even if its flow looks good.
EARLY_MCAP_USD = 60_000.0

# Midpoints chosen to sit near the top of the observed distribution for a live
# but unremarkable launch, so 50 means "notable", not "exists".
VOLUME_RATE_MIDPOINT_USD_PER_MIN = 2_000.0
BUY_TX_RATE_MIDPOINT_PER_MIN = 20.0
LIQUIDITY_MIDPOINT_USD = 15_000.0


def _narrative_score(cand: Candidate) -> float | None:
    """Crude narrative quality from the metadata text.

    Deliberately shallow: real meme quality is a semantic judgement the PRD
    defers to Phase 4. What this can honestly detect is whether the launch
    bothered to have an identity at all, which separates a themed launch from
    the thousands of empty-description mints in the firehose.
    """
    meta = cand.metadata
    if not meta.fetched:
        return None
    score = 0.0
    desc = meta.description.strip()
    if desc:
        score += 40.0
        if len(desc) >= 25:
            score += 15.0
    if meta.image:
        score += 15.0
    socials = [s for s in (meta.twitter, meta.telegram, meta.website) if s]
    score += min(30.0, 10.0 * len(socials))
    return min(100.0, score)


def _social_components(cand: Candidate) -> tuple[float | None, float | None]:
    """Social velocity and cross-platform propagation.

    Both return None in Phase 1. The radar does not ingest X, Telegram, or
    Reddit yet, and the linked handles in token metadata prove only that the
    creator typed a URL, not that anyone is talking about the contract. Scoring
    a declared handle as social traction is precisely the bot-inflated signal
    PRD section 3.2 warns about, so it is left unmeasured.
    """
    del cand
    return None, None


def score_moon(cand: Candidate, feat: FlowFeatures, smart_wallets: dict[str, float]) -> ScoreBreakdown:
    reasons: list[str] = []

    if feat.samples >= 2:
        vol_component: float | None = max(
            saturating(feat.volume_rate_usd_per_min, VOLUME_RATE_MIDPOINT_USD_PER_MIN),
            ratio_score(feat.volume_accel, 0.5, 4.0),
        )
        if feat.volume_accel >= 2.0:
            reasons.append(f"volume rate {feat.volume_accel:.1f}x prior window")
    else:
        vol_component = None

    if feat.samples >= 2:
        buyer_component: float | None = max(
            saturating(feat.buy_tx_rate_per_min, BUY_TX_RATE_MIDPOINT_PER_MIN),
            ratio_score(feat.buy_tx_accel, 0.5, 4.0),
        )
        if feat.buy_tx_rate_per_min >= BUY_TX_RATE_MIDPOINT_PER_MIN:
            reasons.append(f"{feat.buy_tx_rate_per_min:.0f} buy tx/min (tx proxy, not unique wallets)")
    else:
        buyer_component = None

    # Smart money: available only once a wallet leaderboard exists. An empty
    # watchlist means unmeasured, not "no smart money present".
    if smart_wallets:
        hits = cand.smart_wallets & set(smart_wallets)
        if hits:
            quality = sum(smart_wallets[w] for w in hits) / len(hits)
            smart_component: float | None = min(100.0, 40.0 + quality / 2.0 + 15.0 * (len(hits) - 1))
            reasons.append(f"{len(hits)} tracked wallet(s) entered")
        else:
            smart_component = 0.0
    else:
        smart_component = None

    social_velocity, cross_platform = _social_components(cand)

    holder_component: float | None = (
        saturating(feat.holder_growth_per_min, 20.0)
        if feat.holder_growth_per_min is not None
        else None
    )

    liquidity_component = (
        saturating(feat.liquidity_usd, LIQUIDITY_MIDPOINT_USD)
        if feat.liquidity_usd > 0
        else None
    )

    mcap = feat.market_cap_usd or 0.0
    if mcap > 0:
        # Lower market cap is more upside for the same flow, which is the whole
        # point of hunting at second zero.
        early_component: float | None = max(0.0, 100.0 * (1.0 - min(1.0, mcap / EARLY_MCAP_USD)))
        if mcap <= 20_000:
            reasons.append(f"still ~${mcap:,.0f} market cap")
    else:
        early_component = None

    return weighted_score(
        WEIGHTS,
        {
            "volume_acceleration": vol_component,
            "smart_money": smart_component,
            "unique_buyer_acceleration": buyer_component,
            "social_velocity": social_velocity,
            "holder_growth": holder_component,
            "cross_platform": cross_platform,
            "liquidity_quality": liquidity_component,
            "narrative": _narrative_score(cand),
            "early_entry": early_component,
        },
        reasons=reasons,
    )
