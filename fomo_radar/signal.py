"""The social-conviction signal, v2.

v1 is preserved in git history. It gated on *thesis earliness* — the first ~10
theses a token ever received — which is a real, monotonic effect but one we
cannot act on: the harvester joins a token's timeline at rank ~500. Over 17
hours it watched ALLINU take on positions of $328k/$206k/$202k at
+742%/+606%/+593% and alerted nothing, because every thesis was past rank 10.
An unreachable gate looks exactly like a quiet market.

v2 keeps earliness but moves it inside the author: a conviction author is one
whose FIRST thesis landed early in the token's timeline and who has kept posting
since. That is computable from the backfilled history no matter when we arrive.
See `conviction.py` for the measured table this is built from.

Two things v1 got wrong, both now reversed:

* It discounted repeated posting by one handle as "not confirmation". Per
  (author, token) pair it is the strongest at-post-time feature there is:
  1 thesis 53.5% win -> 12+ theses 67.2%, and cross-tabbed with an early first
  post, 78% win / +99% median.
* It had no concept of whether the token is actually being traded. That is why
  the sibling radar kept surfacing coins nobody was buying. `LiquidityState` is
  now a HARD gate: no live market, no alert, whatever the social score says.

Deliberately NOT modelled: thesis text semantics (no evidence content predicts
anything; the one content feature tested turned out to be a size proxy) and the
dev flag (7 dev theses in 20,337, median -40.1%, zero winners).
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

# The lowest score a token clearing every hard gate can possibly reach:
# one conviction author past the cadence floor (+24), whose first thesis is in
# the early half but no earlier (+10), at the minimum position size (+3).
# v1 shipped a floor of 50 above a reachable minimum of 47, so a token could
# pass every gate and alert nothing — a dead band found by replaying real
# theses. `test_no_dead_band_above_the_gates` derives this value from the
# scorer and fails if the two ever drift apart again.
WATCH_FLOOR = 37.0


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
    distinct_authors: int
    leaderboard_authors: int
    total_usd: float
    tier: str | None
    score: float
    reasons: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    """Hard gates this token failed. Empty when it alerted."""

    # Kept for the alerts table / backwards compatibility with the store.
    thesis_rank: int = 0
    qualified_count: int = 0
    max_usd: float = 0.0
    minutes_since_first: float = 0.0
    has_x_link: bool = False


def evaluate(
    *,
    token_address: str,
    network_id: int,
    ticker: str,
    cluster: ConvictionCluster,
    liquidity: LiquidityState,
    total_usd: float = 0.0,
    cfg: SignalConfig | None = None,
) -> TokenSignal:
    """Score a token's conviction cluster and assign a tier (or None).

    Returning `tier=None` is a normal outcome, but unlike v1 it should now be a
    *minority* outcome for tokens that reach this function, because the caller
    only calls it on tokens carrying at least one qualifying author.
    """
    cfg = cfg or SignalConfig()

    reasons: list[str] = []
    blocked: list[str] = []
    score = 0.0

    # --- hard gate 1: someone is actually trading this ----------------------
    # The direct fix for alerting on coins with no buyers. Ordered first so the
    # reason a token was rejected is the real one.
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

    # --- hard gate 2: a conviction cluster exists ---------------------------
    if cluster.count < 1:
        blocked.append("no conviction author")

    # --- conviction cadence: a GATE, not a dial -----------------------------
    # Rank-correlated against the author's own PnL *within the already-qualified
    # population*, thesis count scores rho=-0.002 — i.e. once an author has
    # cleared the cadence floor, posting more is not further evidence. The first
    # v2 draft gave 45/36/30 by cadence and was wrong to; the floor does the
    # work. A small step is kept for the extreme tail (30+ theses medians
    # +299.2% / 88.2% win, n=17) and nothing more is read into it.
    top = cluster.top
    if top is not None:
        score += 24.0
        if top.theses >= 30:
            score += 6.0
        reasons.append(f"@{top.handle} posted {top.theses} theses on this token")

        # --- earliness of that author's first commitment --------------------
        # This is the real differentiator and carries the most weight:
        # rho=-0.189 against PnL, and by bucket, earliest 10% medians +166.6%
        # (85.0% win) vs 10-30% +82.1% (71.9%) vs 30-50% +68.3% (75.5%).
        if top.first_pct <= 0.05:
            score += 34.0
            reasons.append("their first thesis was in the token's earliest 5%")
        elif top.first_pct <= 0.10:
            score += 28.0
            reasons.append("their first thesis was in the earliest 10%")
        elif top.first_pct <= 0.30:
            score += 18.0
            reasons.append("their first thesis was in the earliest 30%")
        else:
            score += 10.0
            reasons.append("their first thesis was in the early half")

        # --- size floor (evidence, not prediction) --------------------------
        # rho=+0.227, but position VALUE rises with price, so this is mostly
        # post-hoc. Deliberately the smallest component.
        if top.position_usd >= 100_000:
            score += 10.0
        elif top.position_usd >= 25_000:
            score += 7.0
        elif top.position_usd >= 5_000:
            score += 5.0
        else:
            score += 3.0
        reasons.append(f"position ${top.position_usd:,.0f} held at {top.pnl_pct:+.0f}%")

    # --- independent confirmation: more conviction authors ------------------
    # Checked specifically for the "crowding is lagging" worry that sank the
    # leaderboard-holdings idea. It does NOT apply here: per (author, token)
    # pair, cluster size rank-correlates +0.283 with the author's own PnL and
    # the 8+ bucket medians +143.4% at 85.2% win (n=203). More operators
    # committing early is real confirmation, not late crowding.
    if cluster.count >= 8:
        score += 18.0
        reasons.append(f"{cluster.count} independent conviction authors")
    elif cluster.count >= 4:
        score += 13.0
        reasons.append(f"{cluster.count} independent conviction authors")
    elif cluster.count >= 2:
        score += 8.0
        reasons.append(f"{cluster.count} independent conviction authors")

    # --- leaderboard overlay (lift, never a requirement) --------------------
    # rho=+0.225; 2+ top-150 authors in the cluster medians +120.4% at 80.9%
    # win vs +66.3% / 74.1% with none. Still never a gate: starcatcher444 ran
    # the worked example while absent from the 24h top-150, because that board
    # ranks REALIZED PnL and a conviction holder has not sold.
    if cluster.leaderboard_count >= 3:
        score += 16.0
        reasons.append(f"{cluster.leaderboard_count} top-150 traders among them")
    elif cluster.leaderboard_count >= 1:
        score += 9.0
        reasons.append(
            f"{cluster.leaderboard_count} top-150 trader"
            f"{'s' if cluster.leaderboard_count > 1 else ''} among them"
        )

    # --- combined conviction capital ---------------------------------------
    # rho=+0.281. The $2M+ bucket is the standout (98.6% win, n=73) but that is
    # plainly entangled with appreciation, so it is weighted like the size term.
    if cluster.capital_usd >= 2_000_000:
        score += 10.0
        reasons.append(f"${cluster.capital_usd:,.0f} of conviction capital")
    elif cluster.capital_usd >= 500_000:
        score += 7.0
        reasons.append(f"${cluster.capital_usd:,.0f} of conviction capital")
    elif cluster.capital_usd >= 100_000:
        score += 4.0
        reasons.append(f"${cluster.capital_usd:,.0f} of conviction capital")

    tier: str | None = None
    if not blocked:
        # TIERS RANK EVIDENCE, NOT EXPECTED RETURN. Read this before tuning.
        #
        # Replaying the 50-token harvest: the GATE separates well — tokens that
        # alerted median +71.6% on the outcome proxy against -16.2% for the
        # silent ones. But WITHIN the 29 that alerted, the score does not rank
        # the outcome at all: rho=-0.146, and the top half by score medianed
        # +51% against +121% for the bottom half. Earliness inverts at token
        # level too (+51% early-half vs +118% late-half) even though it clearly
        # works per (author, token) pair, because the token-level proxy is a
        # median over all sized positions and mature tokens carry more late
        # entrants. n=29 either way, so this is weak evidence rather than proof
        # of inversion — but it is nowhere near enough to claim a higher tier
        # earns more, and saying so would be inventing precision.
        #
        # So a tier answers "how much independent evidence is behind this call",
        # which is defensible from the components, and it drives Discord
        # priority and how much attention a line deserves. It is NOT a
        # predicted-return ordering. Settling that needs the forward log with
        # labelled outcomes; until then the alert footer says so.
        #
        # CONVICTION additionally requires an early lead author and a second
        # independent one, so the top tier cannot be bought with size alone.
        # Verified reachable with ZERO leaderboard authors (Index, score 91) —
        # the leaderboard must never gate a tier.
        early_lead = top is not None and top.first_pct <= 0.10
        if score >= 88 and early_lead and cluster.count >= 2:
            tier = TIER_CONVICTION
        elif score >= 60:
            tier = TIER_HOT
        elif score >= WATCH_FLOOR:
            tier = TIER_WATCH

    return TokenSignal(
        token_address=token_address,
        network_id=network_id,
        ticker=ticker,
        cluster=cluster,
        liquidity=liquidity,
        distinct_authors=cluster.considered,
        leaderboard_authors=cluster.leaderboard_count,
        total_usd=total_usd or cluster.capital_usd,
        tier=tier,
        score=round(score, 1),
        reasons=reasons,
        blocked_by=blocked,
        thesis_rank=top.first_rank if top else 0,
        qualified_count=cluster.count,
        max_usd=max((a.position_usd for a in cluster.authors), default=0.0),
        has_x_link=False,
    )
