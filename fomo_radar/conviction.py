"""Author-level conviction profiles — the measured core of the v2 signal.

Why this module exists
----------------------
v1 alerted on *thesis earliness*: the first ~10 theses a token ever received.
That decays monotonically and is real (see FINDINGS.md), but it is operationally
unreachable. We join a token's social timeline at rank ~500, so on 2026-09-17
the harvester watched ALLINU accumulate positions of $328k/$206k/$202k at
+742%/+606%/+593% and fired **zero alerts**, because every one of those theses
was past rank 10. A gate that cannot fire is indistinguishable from a quiet
market — the failure mode this repo keeps hitting.

What replaced it
----------------
The same 20,337-thesis harvest, re-cut with one row per (author, token) pair
rather than per thesis. That de-duplication matters: fomo attaches the author's
*current* position and PnL to every one of their historical theses, so a handle
with 34 theses contributed 34 identical outcomes and inflated n by ~3.4x.

Per-pair, restricted to features knowable when the thesis is posted:

    gate                              n     median    win     p25    >+100%
    baseline (all pairs)           2361     +10.9%  57.1%  -23.7%    28.0%
    conviction >=3                  797     +30.8%  63.0%  -18.5%    35.6%
    conviction >=3, early half      622     +52.6%  67.4%  -16.0%    41.0%
    conviction >=6, early half      299     +68.3%  71.6%   -9.0%    45.2%
    conviction >=12, early half     112     +79.4%  73.2%   -8.4%    46.4%
    conviction >=6, early, on LB     45     +57.6%  75.6%   -1.9%    40.0%

Cross-tabbed, the strongest cell is 12+ theses whose first post landed in the
token's early deciles: **+99% median, 78% win, n=91**. That is the pattern in
starcatcher444/ALLINU — one operator posting the same thesis a dozen times
while adding through drawdown.

Two findings that cut against the obvious design:

* **Leaderboard membership helps but cannot be required.** On-leaderboard
  authors median +53.6% / 73.0% win vs +9.4% / 56.2% off it — a real lift, so it
  raises a tier. But starcatcher444 was NOT in the 24h top-150: that board ranks
  *realized* PnL and a conviction holder has not sold. Requiring it would have
  missed the worked example.
* **"Dev-backed" has no support.** Seven dev theses exist in 20,337 (three
  author-token pairs), median -40.1%, zero winners. Not modelled.

Known limits, stated because they bound how much to trust this
--------------------------------------------------------------
* **Survivorship.** All 50 harvested tokens were trending, i.e. already winners.
  The baseline itself is +10.9% median / 57% win, which no random token pool
  reaches. These numbers rank features against each other; they are NOT a hit
  rate to expect in the wild.
* **Reverse causality is live.** People post more when a position is winning, so
  a high thesis count is partly an *effect* of the run. Requiring the author's
  FIRST thesis to be early constrains this (they committed before the crowd) but
  does not eliminate it. Only the forward log settles it.
* `usd`, `unrealized_pnl_pct` and `likes` are all read at observation time and
  therefore post-hoc. They are shown in alerts as evidence and used as a size
  floor, never as predictive score.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AuthorProfile:
    """One author's full observed relationship with one token."""

    handle: str
    theses: int
    first_rank: int
    """0-based position of their first thesis in the token's global timeline."""
    total_theses_on_token: int
    position_usd: float
    pnl_pct: float
    is_leaderboard: bool
    is_dev: bool
    first_at: str
    last_at: str
    last_text: str
    max_likes: int

    @property
    def first_pct(self) -> float:
        """Where their first thesis fell in the timeline, 0.0 = first ever.

        Normalised so tokens with 500 theses and 20 theses are comparable; the
        measured decay is on this scale, not on absolute rank.
        """
        denom = max(self.total_theses_on_token - 1, 1)
        return min(self.first_rank / denom, 1.0)

    @property
    def span_hours(self) -> float:
        from datetime import datetime

        try:
            a = datetime.fromisoformat(self.first_at.replace("Z", "+00:00"))
            b = datetime.fromisoformat(self.last_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return 0.0
        return max((b - a).total_seconds() / 3600.0, 0.0)


@dataclass(slots=True)
class ConvictionCluster:
    """The token-level view: which authors qualify, and how strong they are."""

    authors: list[AuthorProfile] = field(default_factory=list)
    """Qualifying conviction authors, strongest first."""

    considered: int = 0
    """How many distinct authors were examined, qualifying or not."""

    @property
    def count(self) -> int:
        return len(self.authors)

    @property
    def leaderboard_count(self) -> int:
        return sum(1 for a in self.authors if a.is_leaderboard)

    @property
    def capital_usd(self) -> float:
        """Combined live position value of the conviction authors."""
        return sum(a.position_usd for a in self.authors)

    @property
    def max_theses(self) -> int:
        return max((a.theses for a in self.authors), default=0)

    @property
    def top(self) -> AuthorProfile | None:
        return self.authors[0] if self.authors else None


def qualifies(
    a: AuthorProfile,
    *,
    min_theses: int,
    min_theses_leaderboard: int,
    max_first_pct: float,
    min_position_usd: float,
) -> bool:
    """Is this author a conviction holder by the measured definition?

    Leaderboard authors clear on a lower thesis count because their per-pair
    win rate at >=3 theses (73.6%) already exceeds what a non-leaderboard author
    reaches at >=6 (71.6%) — the lift is priced in rather than stacked on top.
    """
    if a.position_usd < min_position_usd:
        return False
    if a.first_pct > max_first_pct:
        return False
    floor = min_theses_leaderboard if a.is_leaderboard else min_theses
    return a.theses >= floor


def _author_strength(a: AuthorProfile) -> tuple:
    """Sort key: the ordering the measurement supports, strongest first.

    Leaderboard first, then thesis count, then earliness, then size. Size is
    last on purpose: it is post-hoc (a 10x winner's position is 10x bigger by
    definition) so it breaks ties rather than setting the order.
    """
    return (not a.is_leaderboard, -a.theses, a.first_pct, -a.position_usd)


def build_cluster(
    profiles: list[AuthorProfile],
    *,
    min_theses: int = 6,
    min_theses_leaderboard: int = 3,
    max_first_pct: float = 0.5,
    min_position_usd: float = 1000.0,
) -> ConvictionCluster:
    """Select and rank the conviction authors on a token."""
    keep = [
        a
        for a in profiles
        if qualifies(
            a,
            min_theses=min_theses,
            min_theses_leaderboard=min_theses_leaderboard,
            max_first_pct=max_first_pct,
            min_position_usd=min_position_usd,
        )
    ]
    keep.sort(key=_author_strength)
    return ConvictionCluster(authors=keep, considered=len(profiles))
