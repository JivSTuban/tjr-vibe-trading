"""The social-conviction signal.

Built only from what survived measurement in `research/fomo/FINDINGS.md`:

  * EARLINESS is the edge. Median unrealized PnL falls monotonically across all
    ten deciles of thesis order on a token (+192% earliest decile -> +21% latest;
    1st thesis on a token medians +716%). Every gate below is a way of asking
    "are we near the front of this token's thesis timeline".
  * SIZE, not the X link. X-linked theses look strong raw (57.1% win vs 46.0%)
    but are 7.8x larger, and above $5k the apparent edge inverts. `has_x_link`
    is recorded and shown in the alert as context; it contributes zero score.
  * DISTINCT AUTHORS, not post count. One handle posting three times in four
    minutes was common in the sample and is not confirmation.
  * The LEADERBOARD is a lagging quality marker. It can lift a tier but can
    never create a candidate: its own top-consensus holdings are already-won
    positions, and only 19 of 153 were even trending.

Deliberately NOT modelled: thesis text semantics. There is no evidence content
predicts anything, and the one content feature tested was a size proxy. Text is
stored so this can be revisited against labelled outcomes rather than guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .config import SignalConfig

TIER_WATCH = "WATCH"
TIER_HOT = "HOT"
TIER_CONVICTION = "CONVICTION"

# Priority for the shared Discord rate budget: lower sheds last.
TIER_PRIORITY = {TIER_CONVICTION: 1, TIER_HOT: 2, TIER_WATCH: 3}

# The lowest score a token that clears every hard gate can possibly score:
# earliest-window rank (+25) + the minimum confirming authors (+12) + the
# minimum qualifying size (+10). Found by replaying 2,374 real theses: with the
# WATCH floor at 50 a token could pass every gate, score 47, and produce
# nothing — eligible but unalertable, which from outside is indistinguishable
# from a quiet market. `test_no_dead_band_above_the_gates` derives this value
# from the scorer and fails if the two ever drift apart again.
WATCH_FLOOR = 47.0


@dataclass(slots=True)
class TokenSignal:
    token_address: str
    network_id: int
    ticker: str
    thesis_rank: int
    distinct_authors: int
    leaderboard_authors: int
    qualified_count: int
    total_usd: float
    max_usd: float
    minutes_since_first: float
    has_x_link: bool
    tier: str | None
    score: float
    reasons: list[str]


def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def evaluate(
    *,
    token_address: str,
    network_id: int,
    ticker: str,
    stats: dict[str, object],
    thesis_rank: int,
    has_x_link: bool,
    cfg: SignalConfig | None = None,
    now: datetime | None = None,
) -> TokenSignal:
    """Score a token's current social state and assign a tier (or None).

    `thesis_rank` is 0-based: 0 means this is the first thesis we have on the
    token. Returning `tier=None` is the normal outcome; most tokens never
    qualify, and a quiet channel is the expected steady state.
    """
    cfg = cfg or SignalConfig()
    now = now or datetime.now(timezone.utc)

    qualified = int(stats.get("qualified_count") or 0)
    authors = int(stats.get("distinct_authors") or 0)
    lb_authors = int(stats.get("leaderboard_authors") or 0)
    total_usd = float(stats.get("total_usd") or 0.0)
    max_usd = float(stats.get("max_usd") or 0.0)

    first = _parse_iso(str(stats.get("first_thesis_at") or ""))
    minutes = (now - first).total_seconds() / 60.0 if first else 0.0

    reasons: list[str] = []
    score = 0.0

    # --- earliness, the load-bearing component ------------------------------
    # Weights follow the measured decile curve rather than a smooth function:
    # the top three rank buckets were worth 2-4x the tail in median PnL.
    if thesis_rank == 0:
        score += 45.0
        reasons.append("first thesis on this token")
    elif thesis_rank <= 2:
        score += 38.0
        reasons.append(f"thesis #{thesis_rank + 1} on this token")
    elif thesis_rank < cfg.max_thesis_rank:
        score += 25.0
        reasons.append(f"thesis #{thesis_rank + 1}, still inside the early window")
    else:
        # Past the early window the measured edge collapses to roughly the
        # sample's base rate. No score, and the gate below will reject.
        reasons.append(f"thesis #{thesis_rank + 1} — past the early window")

    # --- size ---------------------------------------------------------------
    if max_usd >= 25_000:
        score += 25.0
        reasons.append(f"largest position ${max_usd:,.0f}")
    elif max_usd >= 5_000:
        score += 18.0
        reasons.append(f"largest position ${max_usd:,.0f}")
    elif max_usd >= cfg.min_thesis_usd:
        score += 10.0
        reasons.append(f"largest position ${max_usd:,.0f}")

    # --- independent confirmation -------------------------------------------
    if authors >= 4:
        score += 20.0
        reasons.append(f"{authors} distinct authors")
    elif authors >= cfg.min_distinct_authors:
        score += 12.0
        reasons.append(f"{authors} distinct authors")

    # --- leaderboard overlay (quality, never discovery) ---------------------
    if lb_authors >= 2:
        score += 15.0
        reasons.append(f"{lb_authors} leaderboard traders in")
    elif lb_authors == 1:
        score += 8.0
        reasons.append("1 leaderboard trader in")

    tier: str | None = None
    # Gates are conjunctive on purpose. Every one of these is a condition the
    # measurement supports; a token that fails any of them sits in the part of
    # the curve where the edge was not distinguishable from the base rate.
    eligible = (
        thesis_rank < cfg.max_thesis_rank
        and authors >= cfg.min_distinct_authors
        and qualified >= cfg.min_distinct_authors
        and max_usd >= cfg.min_thesis_usd
    )
    if eligible:
        if score >= 85 or (lb_authors >= 2 and score >= 70):
            tier = TIER_CONVICTION
        elif score >= 65:
            tier = TIER_HOT
        elif score >= WATCH_FLOOR:
            tier = TIER_WATCH

    return TokenSignal(
        token_address=token_address,
        network_id=network_id,
        ticker=ticker,
        thesis_rank=thesis_rank,
        distinct_authors=authors,
        leaderboard_authors=lb_authors,
        qualified_count=qualified,
        total_usd=total_usd,
        max_usd=max_usd,
        minutes_since_first=minutes,
        has_x_link=has_x_link,
        tier=tier,
        score=round(score, 1),
        reasons=reasons,
    )
