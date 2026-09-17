"""The social signal, v3 — entry-clean earliness.

Read the history before changing anything here, because two previous versions
failed in opposite directions.

v1 gated on absolute thesis rank (a token inside its first ~10 theses ever).
**That rule was correct** and it fired zero alerts anyway, because the global
activity feed only ever shows us tokens at rank 70-500. A right gate starved of
the right input.

v2 replaced it with "conviction cadence": an author with >=6 theses on a token
whose first landed in its early half. It fired, and the alerts were trophies.
Jiv caught it from a single $CATE alert — @PoorGoat_ up +1735% on a $67M token
after 436 theses over 333 hours. The signal was describing a winner, not finding
one, and the reason is that **both v2 features need information from the
future**:

  * thesis COUNT accumulates after entry. At PoorGoat_'s thesis #1 you could not
    know he would post 435 more. By the time a cluster reaches 6, the run is
    often over.
  * `first_pct` = first_rank / total_theses, and the denominator is the token's
    EVENTUAL thesis count. Unknowable when the thesis is posted.

Stripping every look-ahead feature made the measurement BETTER, not worse
(per author-token pair, outcome = that author's eventual PnL):

    gate                                   clean?        n   median    win   >100%
    baseline                                    -     2361   +10.9%  57.1%   28.0%
    v2 shipped gate                    LOOK-AHEAD      319   +68.3%  72.4%   45.5%
    entry-only: first 20 theses             clean      189  +164.6%  81.0%   56.1%
    entry-only: anyone in first 5           clean       53  +194.3%  81.1%   60.4%
    entry-only: literally first             clean       11  +715.6%  90.9%       -

Absolute `first_rank` is the strongest clean feature (rho=-0.223). The
look-ahead features are POSITIVELY correlated with outcome (thesis count +0.082,
eventual total +0.171) — they are outcome proxies, which is exactly why they
looked so good.

**Leaderboard membership is worth nothing here** (rho=-0.057). Controlling for
earliness it is if anything negative: unknown authors arriving in a token's
first 20 theses median +170.2% / 81.3% win, against +88.8% / 78.3% for top-150
traders arriving in the same window. It is displayed as context and scores zero.
Consistent with the follower-count result (200k+ follower authors: -8.0% median,
45.0% win) — fame is not edge, and a famous account's followers are the exit
liquidity.

So v3 = v1's rule, plus the two things v1 lacked: a liquidity gate, and a
discovery path that can actually reach an early token (see `discovery.py`, which
joins the sibling radar's pump.fun launch stream against fomo thesis history).

Deliberately NOT modelled: thesis text semantics, the dev flag (7 dev theses in
20,337, median -40.1%, zero winners), and author fame.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import SignalConfig
from .conviction import ConvictionCluster

TIER_WATCH = "WATCH"
TIER_HOT = "HOT"
TIER_CONVICTION = "CONVICTION"

# Priority for the shared Discord rate budget: higher number sheds first.
TIER_PRIORITY = {TIER_CONVICTION: 1, TIER_HOT: 2, TIER_WATCH: 3}

# The lowest score a token clearing every hard gate can possibly reach: arriving
# at the very edge of the early window (+20) with the minimum qualifying
# position (+3). v1 shipped a WATCH floor of 50 above a reachable minimum of 47,
# so a token could pass every gate and alert nothing — a dead band found by
# replaying real theses. `test_no_dead_band_above_the_gates` derives this value
# from the scorer and fails if the two ever drift apart.
WATCH_FLOOR = 23.0


@dataclass(slots=True)
class LiquidityState:
    """Is there a real market in this token right now?

    Sourced from DexScreener (the same client the sibling radar uses). Absent
    data is NOT treated as zero — `known=False` means we could not look, which
    fails the gate rather than silently scoring a token as dead.
    """

    known: bool = False
    liquidity_usd: float = 0.0
    volume_h1_usd: float = 0.0
    market_cap_usd: float = 0.0
    buys_m5: int = 0
    sells_m5: int = 0

    @property
    def txns_m5(self) -> int:
        return self.buys_m5 + self.sells_m5


@dataclass(slots=True)
class TokenSignal:
    token_address: str
    network_id: int
    ticker: str
    cluster: ConvictionCluster
    liquidity: LiquidityState
    thesis_rank: int
    """Theses that existed on this token before the one that triggered us.

    The load-bearing number, and the only strong feature knowable at post time.
    """
    distinct_authors: int
    leaderboard_authors: int
    total_usd: float
    tier: str | None
    score: float
    reasons: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    """Hard gates this token failed. Empty when it alerted."""

    qualified_count: int = 0
    max_usd: float = 0.0
    minutes_since_first: float = 0.0
    has_x_link: bool = False


def evaluate(
    *,
    token_address: str,
    network_id: int,
    ticker: str,
    thesis_rank: int,
    cluster: ConvictionCluster,
    liquidity: LiquidityState,
    largest_usd: float = 0.0,
    total_usd: float = 0.0,
    cfg: SignalConfig | None = None,
) -> TokenSignal:
    """Score a token on entry-clean features only, and assign a tier (or None).

    `thesis_rank` is 0-based and ABSOLUTE: the number of theses that already
    existed on this token. No normalisation by the eventual total, because that
    total is future information.

    `cluster` is passed through for display — who is in, and how big — but
    contributes nothing to the score. Everything about it (author cadence,
    position PnL) is measured after the fact.
    """
    cfg = cfg or SignalConfig()

    reasons: list[str] = []
    blocked: list[str] = []
    score = 0.0

    # --- hard gate 1: someone is actually trading this ----------------------
    if not liquidity.known:
        blocked.append("no market data")
    else:
        if liquidity.liquidity_usd < cfg.min_liquidity_usd:
            blocked.append(
                f"liquidity ${liquidity.liquidity_usd:,.0f} < ${cfg.min_liquidity_usd:,.0f}"
            )
        if liquidity.volume_h1_usd < cfg.min_volume_h1_usd:
            blocked.append(
                f"1h volume ${liquidity.volume_h1_usd:,.0f} < ${cfg.min_volume_h1_usd:,.0f}"
            )
        if liquidity.txns_m5 < cfg.min_txns_m5:
            blocked.append(f"{liquidity.txns_m5} txns in 5m — not being traded")

    # --- hard gate 2: we are EARLY in the social timeline -------------------
    # The whole signal. Past this window the measured edge decays to the base
    # rate: ranks 100-299 median +7.3% and 300+ median +0.1%, against a +10.9%
    # baseline. An alert on a token at rank 400 is a report, not a signal —
    # which is precisely what the $CATE alert was.
    if thesis_rank >= cfg.max_thesis_rank:
        blocked.append(
            f"thesis #{thesis_rank + 1} — past the early window "
            f"(max {cfg.max_thesis_rank})"
        )

    # --- earliness, the only strongly-scored component ----------------------
    # Weights follow the measured decay by absolute rank.
    if thesis_rank == 0:
        score += 60.0
        reasons.append("FIRST thesis on this token")
    elif thesis_rank < 5:
        score += 45.0
        reasons.append(f"thesis #{thesis_rank + 1} — inside the first 5")
    elif thesis_rank < 20:
        score += 30.0
        reasons.append(f"thesis #{thesis_rank + 1} — inside the first 20")
    else:
        score += 20.0
        reasons.append(f"thesis #{thesis_rank + 1}")

    # --- size of the largest position behind it ----------------------------
    # Small weight. Position VALUE rises with price, so it is partly post-hoc;
    # it earns its place as evidence that real money is here, not as prediction.
    largest = largest_usd or (cluster.max_theses and 0.0) or 0.0
    if cluster.authors:
        largest = max(largest, max(a.position_usd for a in cluster.authors))
    if largest >= 100_000:
        score += 12.0
    elif largest >= 25_000:
        score += 9.0
    elif largest >= 5_000:
        score += 6.0
    else:
        score += 3.0
    if largest:
        reasons.append(f"largest position ${largest:,.0f}")

    # --- independent authors, at this early stage ---------------------------
    # Distinct authors arriving while the token is still socially young is
    # confirmation. Note this is NOT v2's conviction cadence: it counts PEOPLE
    # present now, not how many times anyone has posted, so it carries no
    # information from the future.
    if cluster.considered >= 5:
        score += 14.0
        reasons.append(f"{cluster.considered} authors already in")
    elif cluster.considered >= 2:
        score += 8.0
        reasons.append(f"{cluster.considered} authors already in")

    # --- leaderboard: displayed, deliberately unscored ----------------------
    # rho=-0.057, and negative once earliness is controlled for. Kept visible
    # because Jiv asked for it and it is useful colour, but it must never move
    # the score or a tier. See the module docstring.
    if cluster.leaderboard_count:
        reasons.append(
            f"{cluster.leaderboard_count} top-150 trader"
            f"{'s' if cluster.leaderboard_count > 1 else ''} in (not scored)"
        )

    tier: str | None = None
    if not blocked:
        # Tiers are set by EARLINESS, the one feature with measured support, so
        # a higher tier means "we are further to the front" rather than a claim
        # about return. Nothing here is validated: zero labelled outcomes.
        if thesis_rank == 0:
            tier = TIER_CONVICTION
        elif thesis_rank < 5:
            tier = TIER_HOT
        elif score >= WATCH_FLOOR:
            tier = TIER_WATCH

    return TokenSignal(
        token_address=token_address,
        network_id=network_id,
        ticker=ticker,
        cluster=cluster,
        liquidity=liquidity,
        thesis_rank=thesis_rank,
        distinct_authors=cluster.considered,
        leaderboard_authors=cluster.leaderboard_count,
        total_usd=total_usd or cluster.capital_usd,
        tier=tier,
        score=round(score, 1),
        reasons=reasons,
        blocked_by=blocked,
        qualified_count=cluster.count,
        max_usd=largest,
        has_x_link=False,
    )
