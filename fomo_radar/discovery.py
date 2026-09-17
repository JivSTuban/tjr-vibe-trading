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


@dataclass(slots=True)
class Candidate:
    """A launch that has a real market and is worth checking fomo for."""

    mint: str
    ticker: str
    liquidity_usd: float
    market_cap_usd: float
    age_seconds: float


def liquid_launches(
    conn,
    *,
    min_liquidity_usd: float = MIN_LIQUIDITY_USD,
    max_age_s: float = MAX_AGE_S,
    limit: int = 40,
) -> list[Candidate]:
    """Launches from the shared DB that developed a real market recently.

    Reads the sibling radar's `tokens` and `market_snapshots` tables directly —
    they are in the same SQLite file precisely so this join is local. Uses PEAK
    liquidity, because a token is worth asking about if it was EVER tradeable;
    one thin snapshot should not disqualify a name that is filling out.
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
        (min_liquidity_usd, limit),
    ).fetchall()

    out: list[Candidate] = []
    for r in rows:
        age = float(r["age"] or 0.0)
        if age > max_age_s:
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
    return out
