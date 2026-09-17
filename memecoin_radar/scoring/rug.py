"""Rug / manipulation score, PRD section 3.2. Higher is more dangerous.

Kept completely independent of the Moon score, which is the PRD's central
product rule: a token can be genuinely exciting and genuinely dangerous at the
same time, and collapsing the two into one number destroys the only information
that matters at the moment of the alert.

One free signal deserves attention: deployer history. Because the radar streams
every creation event, repeat deployers accumulate in our own database at no
cost, so "this wallet has launched 40 tokens this week" is answerable without a
paid history API. That is a genuine advantage of recording the whole firehose.
"""

from __future__ import annotations

from ..features import FlowFeatures
from ..models import Candidate, ScoreBreakdown
from ..sources.helius import HolderConcentration, TokenAuthorities
from . import ratio_score, weighted_score

WEIGHTS: dict[str, float] = {
    "creator_concentration": 0.22,
    "top_holder_concentration": 0.18,
    "token_authorities": 0.15,
    "deployer_history": 0.15,
    "liquidity_withdrawal": 0.12,
    "creator_dumping": 0.10,
    "wash_trading": 0.08,
}

# A deployer this prolific is running a launch factory rather than a project.
DEPLOYER_SPAM_COUNT = 10


def score_rug(
    cand: Candidate,
    feat: FlowFeatures,
    *,
    deployer_launches: int,
    deployer_rugs: int,
    authorities: TokenAuthorities | None = None,
    holders: HolderConcentration | None = None,
) -> ScoreBreakdown:
    reasons: list[str] = []

    # Creator's opening block, known at second zero with no network call.
    creator_pct = cand.launch.creator_supply_pct
    creator_component = ratio_score(creator_pct, 2.0, 25.0)
    if creator_pct >= 10.0:
        reasons.append(f"creator bought {creator_pct:.1f}% of supply at launch")

    if holders is not None and holders.available:
        top_component: float | None = ratio_score(holders.top10_pct, 25.0, 80.0)
        if holders.top10_pct >= 60.0:
            reasons.append(f"top 10 holders control {holders.top10_pct:.0f}%")
    else:
        top_component = None

    if authorities is not None and authorities.available:
        auth_score = 0.0
        if authorities.mint_authority_live:
            auth_score += 70.0
            reasons.append("mint authority still live (supply can be inflated)")
        if authorities.freeze_authority_live:
            auth_score += 50.0
            reasons.append("freeze authority still live (your tokens can be frozen)")
        auth_component: float | None = min(100.0, auth_score)
    else:
        auth_component = None

    # Deployer history from our own stream record.
    hist = ratio_score(float(deployer_launches), 1.0, float(DEPLOYER_SPAM_COUNT))
    if deployer_rugs > 0:
        hist = max(hist, 60.0 + min(40.0, 20.0 * deployer_rugs))
        reasons.append(f"deployer has {deployer_rugs} prior rugged launch(es)")
    elif deployer_launches >= DEPLOYER_SPAM_COUNT:
        reasons.append(f"deployer has launched {deployer_launches} tokens we have seen")
    deployer_component = hist

    if feat.samples >= 2:
        # Liquidity going backwards on a token minutes old is the clearest
        # structural danger sign available on the free path.
        withdrawal = 0.0
        if feat.liquidity_usd > 0 and feat.net_liquidity_change < 0:
            pct = abs(feat.net_liquidity_change) / max(1.0, feat.liquidity_usd) * 100.0
            withdrawal = ratio_score(pct, 5.0, 50.0)
            if pct >= 15.0:
                reasons.append(f"liquidity fell {pct:.0f}% since last check")
        liquidity_component: float | None = withdrawal
    else:
        liquidity_component = None

    if cand.creator_sold:
        dump_component: float | None = 90.0
        reasons.append("creator already sold")
    elif cand.sell_count or cand.buy_count:
        dump_component = 0.0
    else:
        dump_component = None

    # Wash trading: a near-perfect buy/sell balance with meaningful volume is
    # the shape of a loop, not of organic discovery.
    if feat.samples >= 2 and (cand.buy_count + cand.sell_count) >= 10:
        balance = abs(feat.buy_ratio - 0.5)
        wash_component: float | None = ratio_score(0.08 - balance, 0.0, 0.08)
        if wash_component and wash_component >= 60.0:
            reasons.append("buys and sells suspiciously balanced (possible wash loop)")
    else:
        wash_component = None

    return weighted_score(
        WEIGHTS,
        {
            "creator_concentration": creator_component,
            "top_holder_concentration": top_component,
            "token_authorities": auth_component,
            "deployer_history": deployer_component,
            "liquidity_withdrawal": liquidity_component,
            "creator_dumping": dump_component,
            "wash_trading": wash_component,
        },
        reasons=reasons,
    )
