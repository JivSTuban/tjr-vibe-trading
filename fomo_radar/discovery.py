"""Reach tokens while they are still socially young.

The problem this solves
-----------------------
The only entry-clean edge measured on fomo data is being at the FRONT of a
token's thesis timeline (first 20 theses: +164.6% median / 81.0% win against a
+10.9% / 57.1% baseline; the literal first thesis medians +715.6%). v1 gated on
exactly that and fired zero alerts in 17 hours.

The cause was the INPUT, not the gate. `/feed/tradingActivity` is a trending
feed, not a chronological firehose, and it shows tokens deep into their social
life. Verified live at four thresholds:

    threshold=0     6 theses, arrival rank min  70, median 492, rank<=20: 0/6
    threshold=10    6 theses, arrival rank min  70, median 492, rank<=20: 0/6
    threshold=100  10 theses, arrival rank min  70, median 469, rank<=20: 0/8
    threshold=1000 15 theses, arrival rank min  70, median 243, rank<=20: 0/11

The minimum thesis size was $959 in every case, so `threshold` is not a size
filter at all, and lowering it returns FEWER theses rather than earlier ones.
There is no setting of that endpoint which surfaces an early token.

The fix
-------
Discover candidates somewhere else entirely: the sibling radar already streams
every new pump.fun creation (12-44/min), and both packages share one database.
Poll fomo's per-token thesis history for the small number of those launches that
develop a real market, and we arrive at rank 1-20 by construction.

Measured on the launches already recorded: of 20 that reached >=$15k liquidity,
17 had at least one fomo thesis and **9 were at <=20 theses** — the zone the
gate wants. One example: MCOWNPRC at 6 theses with $3.4M liquidity and a $44M
cap, i.e. a real market with almost no social footprint yet.

Cost control
------------
34k launches/day cannot each get a fomo call. The liquidity floor does the
filtering: only launches that became tradeable are worth asking about, which is
a few dozen a day. Each is asked at most once per `RECHECK_S` until it either
alerts or ages out.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger("fomo_radar.discovery")

# A launch is only worth a fomo call once it has a market someone could exit.
# Same floor the sibling radar uses for its own upside alerts, and far below the
# fomo trending universe (whose weakest member had $280k of 24h volume).
MIN_LIQUIDITY_USD = 15_000.0

# Don't ask about the same launch more often than this. Social footprint grows
# over hours, not seconds.
RECHECK_S = 900.0

# Thesis-history calls per sweep. The first live sweep asked about 60 launches
# and tripped a real Cloudflare 429 inside a minute, which costs the feed poll
# too (one backoff blocks everything). Steady state only needs to cover newly
# liquid launches, so a small batch per sweep is sufficient and the backlog
# drains over several sweeps instead of in one burst.
MAX_CHECKS_PER_SWEEP = 12

# Stop tracking a launch after this long. If nothing social has happened in
# three days the token is not going to be an early-thesis candidate.
MAX_AGE_S = 3 * 86_400.0

# Safety bound on the candidate list, NOT a selection filter. It used to be 40
# with `ORDER BY liq DESC`, which quietly made the whole discovery path unable
# to fire: liquidity is ANTI-correlated with being socially early, so the top 40
# were the fattest and most socially mature tokens on the book. Measured on the
# live DB (2026-09-17, ~4h of data): 164 mints cleared the $15k floor but only
# 40 were ever asked about, and their newest theses were 6-135 HOURS old. Of the
# four mints that actually hit the fresh+early window, THREE ranked 41st, 79th
# and 112nd by liquidity and were never checked -- including two sitting at
# thesis rank 0, the literal first thesis (+715.6% median, see the module
# docstring). The per-sweep call budget is the real cost control; this cap only
# exists so an unbounded DB cannot produce an unbounded list.
MAX_CANDIDATES = 500


@dataclass(slots=True)
class Candidate:
    """A launch that has a real market and is worth checking fomo for."""

    mint: str
    ticker: str
    liquidity_usd: float
    market_cap_usd: float
    age_seconds: float


def retired_mints(conn, max_thesis_rank: int) -> set[str]:
    """Mints already observed at or past `max_thesis_rank` theses.

    Thesis count only ever grows, so a token seen at 20+ theses can NEVER be an
    early-rank candidate again and asking fomo about it is a wasted call. That
    waste is not marginal: 15 of the 40 mints discovery was checking were
    already past rank 20 (measured 2026-09-17), so 37.5% of every sweep's budget
    was spent on provably dead candidates while the live ones went unasked.

    Read from the DB rather than kept only in memory so a restart does not start
    re-spending the budget on them from scratch.
    """
    rows = conn.execute(
        """SELECT token_address AS mint
           FROM fomo_feed_items
           WHERE item_type = 'thesis' AND token_address IS NOT NULL
           GROUP BY token_address
           HAVING COUNT(*) >= ?""",
        (max_thesis_rank,),
    ).fetchall()
    return {str(r["mint"]) for r in rows}


def liquid_launches(
    conn,
    *,
    min_liquidity_usd: float = MIN_LIQUIDITY_USD,
    max_age_s: float = MAX_AGE_S,
    limit: int = MAX_CANDIDATES,
    exclude: frozenset[str] | set[str] = frozenset(),
) -> list[Candidate]:
    """Launches from the shared DB that developed a real market recently.

    Reads the sibling radar's `tokens` and `market_snapshots` tables directly —
    they are in the same SQLite file precisely so this join is local. Uses PEAK
    liquidity, because a token is worth asking about if it was EVER tradeable;
    one thin snapshot should not disqualify a name that is filling out.

    `exclude` drops mints that are permanently ineligible (see `retired_mints`).
    The returned order is by liquidity for determinism only — the caller MUST
    rotate on last-checked time, because at this candidate count the head of the
    list would otherwise be re-checked before the tail is reached even once.
    """
    rows = conn.execute(
        """SELECT t.mint,
                  t.ticker,
                  MAX(s.liquidity_usd)  AS liq,
                  MAX(s.market_cap_usd) AS mc,
                  MAX(s.age_seconds)    AS age
           FROM tokens t
           JOIN market_snapshots s ON s.mint = t.mint
           GROUP BY t.mint
           HAVING liq >= ?
           ORDER BY liq DESC
           LIMIT ?""",
        # Retired mints are dropped below, after the LIMIT. They skew fat (the
        # most mature tokens have the most theses), so they sit at the HEAD of
        # this ordering — take enough extra rows that the cap bounds survivors
        # rather than silently re-truncating the live candidates away.
        (min_liquidity_usd, limit + len(exclude)),
    ).fetchall()

    out: list[Candidate] = []
    for r in rows:
        age = float(r["age"] or 0.0)
        if age > max_age_s:
            continue
        if str(r["mint"]) in exclude:
            continue
        out.append(
            Candidate(
                mint=str(r["mint"]),
                ticker=str(r["ticker"] or "?"),
                liquidity_usd=float(r["liq"] or 0.0),
                market_cap_usd=float(r["mc"] or 0.0),
                age_seconds=age,
            )
        )
        if len(out) >= limit:
            break
    return out
