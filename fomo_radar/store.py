"""SQLite persistence for fomo social data.

Shares the `memecoin_radar` database file on purpose: the point of this
harvester is to feed the existing radar's smart-money and social components, and
a second database would make that join a cross-file problem.

New tables are prefixed `fomo_`. The existing `wallets` table is also populated
from the leaderboard, because PRD Phase 2 was specified against it and the radar
already reads it.

Raw thesis text is stored in full, deliberately. `social_mentions` keeps only a
`text_hash`, which is right for dedup but makes it impossible to evaluate
whether thesis *content* predicts anything. We have no evidence it does (the one
content feature tested, the X link, turned out to be a size proxy), so nothing
scores off the text today — but throwing it away would foreclose the question.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from .api import LeaderboardTrader, ThesisItem, dumps_links

if TYPE_CHECKING:  # avoids a circular import at runtime
    from .conviction import AuthorProfile

log = logging.getLogger("fomo_radar.store")


@dataclass(slots=True)
class CopyEvent:
    """A leaderboard trader's position quantity changed, so they transacted.

    This is the only free trade tape available: `value` in the holdings payload
    moves with price on every poll, but `human_amount` moves only when someone
    actually buys or sells. `delta_pct` is signed, so positive is a buy.
    """

    handle: str
    token_address: str
    network_id: int | None
    ticker: str | None
    prev_amount: float
    new_amount: float
    price_usd: float | None

    @property
    def is_buy(self) -> bool:
        return self.new_amount > self.prev_amount

    @property
    def delta_pct(self) -> float:
        if self.prev_amount <= 0:
            return 0.0
        return self.new_amount / self.prev_amount - 1.0

SCHEMA = """
PRAGMA journal_mode=WAL;

-- Every feed item we ever saw, theses and plain swaps alike. The swaps are the
-- base rate: without them a thesis hit-rate has nothing to beat.
CREATE TABLE IF NOT EXISTS fomo_feed_items (
    item_id             TEXT PRIMARY KEY,
    item_type           TEXT NOT NULL,
    trade_id            TEXT,
    created_at          TEXT NOT NULL,
    first_seen          TEXT NOT NULL,
    user_id             TEXT,
    handle              TEXT,
    display_name        TEXT,
    verified            INTEGER DEFAULT 0,
    is_dev              INTEGER DEFAULT 0,
    token_address       TEXT NOT NULL,
    network_id          INTEGER NOT NULL,
    ticker              TEXT,
    usd_value           REAL DEFAULT 0,
    unrealized_pnl_pct  REAL DEFAULT 0,
    realized_pnl_pct    REAL DEFAULT 0,
    author_equity       REAL DEFAULT 0,
    likes               INTEGER DEFAULT 0,
    text                TEXT,
    links               TEXT,
    has_x_link          INTEGER DEFAULT 0,
    thesis_rank         INTEGER
);
CREATE INDEX IF NOT EXISTS idx_fomo_feed_token ON fomo_feed_items(token_address, created_at);
CREATE INDEX IF NOT EXISTS idx_fomo_feed_handle ON fomo_feed_items(handle);
CREATE INDEX IF NOT EXISTS idx_fomo_feed_type ON fomo_feed_items(item_type, created_at);

-- One row per token we have ever seen a fomo thesis on, with the ordering facts
-- the signal is built from.
CREATE TABLE IF NOT EXISTS fomo_tokens (
    token_address       TEXT NOT NULL,
    network_id          INTEGER NOT NULL,
    ticker              TEXT,
    first_thesis_at     TEXT,
    last_thesis_at      TEXT,
    thesis_count        INTEGER DEFAULT 0,
    qualified_count     INTEGER DEFAULT 0,
    distinct_authors    INTEGER DEFAULT 0,
    leaderboard_authors INTEGER DEFAULT 0,
    max_usd             REAL DEFAULT 0,
    total_usd           REAL DEFAULT 0,
    alerted_at          TEXT,
    PRIMARY KEY (token_address, network_id)
);

-- The leaderboard snapshot. `window` keeps 24h/7d/30d/all side by side so a
-- one-day fluke is distinguishable from a durable operator.
CREATE TABLE IF NOT EXISTS fomo_leaderboard (
    window          TEXT NOT NULL,
    captured_at     TEXT NOT NULL,
    rank            INTEGER NOT NULL,
    user_id         TEXT,
    handle          TEXT,
    display_name    TEXT,
    solana_address  TEXT,
    evm_address     TEXT,
    pnl             REAL,
    num_trades      INTEGER,
    total_volume    REAL,
    followers       INTEGER,
    total_holdings  INTEGER,
    PRIMARY KEY (window, captured_at, rank)
);
CREATE INDEX IF NOT EXISTS idx_fomo_lb_handle ON fomo_leaderboard(handle);
CREATE INDEX IF NOT EXISTS idx_fomo_lb_sol ON fomo_leaderboard(solana_address);

-- What the leaderboard traders were holding at capture time. This is the
-- already-won trophy case, not a buy list; kept because the *transition* of a
-- token into these rows is informative even though the level is not.
CREATE TABLE IF NOT EXISTS fomo_leaderboard_holdings (
    window          TEXT NOT NULL,
    captured_at     TEXT NOT NULL,
    handle          TEXT NOT NULL,
    token_address   TEXT NOT NULL,
    network_id      INTEGER,
    human_amount    REAL,
    price           REAL,
    value           REAL,
    pnl             REAL
);
CREATE INDEX IF NOT EXISTS idx_fomo_lbh_token ON fomo_leaderboard_holdings(token_address);

CREATE TABLE IF NOT EXISTS fomo_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    token_address   TEXT NOT NULL,
    network_id      INTEGER,
    ticker          TEXT,
    tier            TEXT NOT NULL,
    score           REAL,
    thesis_rank     INTEGER,
    distinct_authors INTEGER,
    leaderboard_authors INTEGER,
    total_usd       REAL,
    reason          TEXT,
    delivered       INTEGER DEFAULT 0,
    -- Why this alert was NOT notified. NULL means it was an ENTER NOW and went
    -- out. Kept rather than dropped because the suppressed rows are the control
    -- group: without them there is no way to find out the entry gate is too
    -- strict, which is this project's most repeated failure.
    suppressed_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_fomo_alerts_token ON fomo_alerts(token_address);

-- Forward price series for tokens we alerted on. This is the missing half of
-- the whole project: every threshold in `signal.py` is a measured ORDERING on a
-- survivorship-biased sample, and none of it is a validated hit rate until
-- alerts are tracked forward and labelled.
--
-- Shaped so `memecoin_radar.backtest.label_one` can consume it unchanged: it
-- wants `mint`, `age_seconds`, `market_cap_usd` and `liquidity_usd`, and it is
-- already generic over a list of dicts. `age_seconds` here is measured from the
-- ALERT, not from the token's launch, which is the only clock that answers
-- "what would have happened if you acted on this".
CREATE TABLE IF NOT EXISTS fomo_price_snapshots (
    token_address   TEXT NOT NULL,
    network_id      INTEGER NOT NULL,
    ts              TEXT NOT NULL,
    age_seconds     REAL NOT NULL,
    price_usd       REAL,
    market_cap_usd  REAL,
    liquidity_usd   REAL,
    volume_h1_usd   REAL,
    buys_m5         INTEGER,
    sells_m5        INTEGER,
    PRIMARY KEY (token_address, network_id, age_seconds)
);
CREATE INDEX IF NOT EXISTS idx_fomo_px_token
    ON fomo_price_snapshots(token_address, age_seconds);

-- One labelled outcome per alerted token. Mirrors `outcomes` in the sibling
-- radar, kept separate because the entry clock differs: there, age is measured
-- from launch; here, from the alert.
CREATE TABLE IF NOT EXISTS fomo_outcomes (
    token_address   TEXT NOT NULL,
    network_id      INTEGER NOT NULL,
    ticker          TEXT,
    tier            TEXT,
    score           REAL,
    alerted_at      TEXT,
    labeled_at      TEXT,
    entry_mcap_usd  REAL,
    entry_liquidity_usd REAL,
    max_return_1h   REAL,
    max_return_6h   REAL,
    max_return_24h  REAL,
    max_return_7d   REAL,
    max_drawdown    REAL,
    rugged          INTEGER,
    t_2x            REAL,
    t_5x            REAL,
    t_10x           REAL,
    t_20x           REAL,
    t_50x           REAL,
    t_100x          REAL,
    PRIMARY KEY (token_address, network_id)
);

-- Mirrors `memecoin_radar.store`'s definition verbatim. Repeated here, not
-- imported, because either package may be the one that creates the shared
-- database file and `CREATE TABLE IF NOT EXISTS` is idempotent. If the radar's
-- definition changes, change it here too — `test_wallets_schema_matches_radar`
-- fails the build if they drift.
CREATE TABLE IF NOT EXISTS wallets (
    address         TEXT PRIMARY KEY,
    quality_score   REAL DEFAULT 0,
    realized_pnl    REAL DEFAULT 0,
    early_win_rate  REAL DEFAULT 0,
    launches_seen   INTEGER DEFAULT 0,
    tags            TEXT,
    updated_at      TEXT
);
"""


# A leaderboard position's reported quantity must move by more than this to
# count as a trade rather than rounding in the payload.
HOLDINGS_TRADE_EPS = 0.01

# Even when nobody trades, force one holdings row per position per interval so
# the table retains a coarse price series to measure outcomes against.
HOLDINGS_HEARTBEAT_S = 900.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(ts: str) -> datetime | None:
    """Tolerant ISO parse. A malformed stored timestamp must not kill a write."""
    try:
        out = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return out if out.tzinfo else out.replace(tzinfo=timezone.utc)


def _has_x_link(item: ThesisItem) -> bool:
    return any("x.com" in url or "twitter.com" in url for url in item.links)


class FomoStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add columns to tables that predate them.

        `CREATE TABLE IF NOT EXISTS` is a no-op on an existing table, so a new
        column never reaches a live database without this. Additive only: no
        drops, no rewrites, no type changes, so it is safe to run on every open
        and safe to run against a database an older build is still writing.
        """
        additions = {
            "fomo_alerts": {"suppressed_reason": "TEXT"},
        }
        for table, columns in additions.items():
            existing = {
                row["name"]
                for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if not existing:
                continue  # Table absent entirely; SCHEMA above owns creating it.
            for name, decl in columns.items():
                if name not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    def close(self) -> None:
        self.conn.close()

    # ---------------------------------------------------------------- feed

    def record_items(self, items: Iterable[ThesisItem]) -> list[ThesisItem]:
        """Insert items we have not seen. Returns only the genuinely new ones.

        Dedup is on the feed item's own id, so re-polling the same 25-item
        window is free and the caller can poll as fast as it likes.
        """
        fresh: list[ThesisItem] = []
        now = _now()
        cur = self.conn.cursor()
        for it in items:
            if not it.item_id or not it.token_address:
                continue
            cur.execute("SELECT 1 FROM fomo_feed_items WHERE item_id = ?", (it.item_id,))
            if cur.fetchone():
                continue
            rank = self._next_thesis_rank(it) if it.is_thesis else None
            cur.execute(
                """INSERT INTO fomo_feed_items
                   (item_id,item_type,trade_id,created_at,first_seen,user_id,handle,
                    display_name,verified,is_dev,token_address,network_id,ticker,
                    usd_value,unrealized_pnl_pct,realized_pnl_pct,author_equity,
                    likes,text,links,has_x_link,thesis_rank)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    it.item_id, it.item_type, it.trade_id, it.created_at, now,
                    it.user_id, it.handle, it.display_name, int(it.verified),
                    int(it.is_dev), it.token_address, it.network_id, it.ticker,
                    it.usd_value, it.unrealized_pnl_pct, it.realized_pnl_pct,
                    it.author_equity, it.likes, it.text, dumps_links(it.links),
                    int(_has_x_link(it)), rank,
                ),
            )
            fresh.append(it)
        self.conn.commit()
        return fresh

    def _next_thesis_rank(self, it: ThesisItem) -> int:
        """0-based order of this thesis among all theses on its token.

        Ordering is the whole signal, so it is computed once at write time from
        what we have actually observed. A token first seen mid-life will report
        an optimistically low rank; `backfill_token` fixes that by pulling the
        real history before any alert fires.
        """
        row = self.conn.execute(
            """SELECT COUNT(*) AS n FROM fomo_feed_items
               WHERE token_address = ? AND network_id = ? AND item_type = 'thesis'""",
            (it.token_address, it.network_id),
        ).fetchone()
        return int(row["n"])

    # -------------------------------------------------------------- tokens

    def refresh_token_stats(
        self, token_address: str, network_id: int, leaderboard_handles: set[str]
    ) -> dict[str, object]:
        """Recompute a token's ordering facts from stored rows."""
        rows = self.conn.execute(
            """SELECT handle, created_at, usd_value, ticker FROM fomo_feed_items
               WHERE token_address = ? AND network_id = ? AND item_type = 'thesis'
               ORDER BY created_at""",
            (token_address, network_id),
        ).fetchall()
        if not rows:
            return {}
        from .config import SignalConfig

        min_usd = SignalConfig().min_thesis_usd
        qualified = [r for r in rows if (r["usd_value"] or 0) >= min_usd]
        authors = {r["handle"] for r in qualified}
        lb_authors = authors & leaderboard_handles
        stats = {
            "ticker": rows[-1]["ticker"],
            "first_thesis_at": rows[0]["created_at"],
            "last_thesis_at": rows[-1]["created_at"],
            "thesis_count": len(rows),
            "qualified_count": len(qualified),
            "distinct_authors": len(authors),
            "leaderboard_authors": len(lb_authors),
            "max_usd": max((r["usd_value"] or 0) for r in rows),
            "total_usd": sum((r["usd_value"] or 0) for r in qualified),
        }
        self.conn.execute(
            """INSERT INTO fomo_tokens
               (token_address,network_id,ticker,first_thesis_at,last_thesis_at,
                thesis_count,qualified_count,distinct_authors,leaderboard_authors,
                max_usd,total_usd)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(token_address,network_id) DO UPDATE SET
                 ticker=excluded.ticker,
                 first_thesis_at=excluded.first_thesis_at,
                 last_thesis_at=excluded.last_thesis_at,
                 thesis_count=excluded.thesis_count,
                 qualified_count=excluded.qualified_count,
                 distinct_authors=excluded.distinct_authors,
                 leaderboard_authors=excluded.leaderboard_authors,
                 max_usd=excluded.max_usd,
                 total_usd=excluded.total_usd""",
            (
                token_address, network_id, stats["ticker"], stats["first_thesis_at"],
                stats["last_thesis_at"], stats["thesis_count"], stats["qualified_count"],
                stats["distinct_authors"], stats["leaderboard_authors"],
                stats["max_usd"], stats["total_usd"],
            ),
        )
        self.conn.commit()
        return stats

    def author_profiles(
        self, token_address: str, network_id: int, leaderboard_handles: set[str]
    ) -> list["AuthorProfile"]:
        """One profile per author who has ever posted a thesis on this token.

        This is the v2 signal's input. It reads the FULL backfilled history, so
        an author's conviction cadence and the earliness of their first thesis
        are both correct regardless of when the harvester started watching —
        the defect that made v1 unable to alert on any established token.

        Position size and PnL are the author's live values (fomo reports the
        same figures on every one of their historical theses), so they are taken
        from the most recent row rather than aggregated.
        """
        from .conviction import AuthorProfile

        rows = self.conn.execute(
            """SELECT handle, created_at, usd_value, unrealized_pnl_pct, likes,
                      is_dev, text
               FROM fomo_feed_items
               WHERE token_address = ? AND network_id = ? AND item_type = 'thesis'
               ORDER BY created_at""",
            (token_address, network_id),
        ).fetchall()
        if not rows:
            return []

        total = len(rows)
        order: dict[str, int] = {}
        grouped: dict[str, list] = {}
        for i, r in enumerate(rows):
            h = r["handle"] or ""
            if not h:
                continue
            order.setdefault(h, i)
            grouped.setdefault(h, []).append(r)

        out: list[AuthorProfile] = []
        for h, items in grouped.items():
            last = items[-1]
            out.append(
                AuthorProfile(
                    handle=h,
                    theses=len(items),
                    first_rank=order[h],
                    total_theses_on_token=total,
                    position_usd=float(last["usd_value"] or 0.0),
                    pnl_pct=float(last["unrealized_pnl_pct"] or 0.0),
                    is_leaderboard=h in leaderboard_handles,
                    is_dev=any(bool(r["is_dev"]) for r in items),
                    first_at=items[0]["created_at"],
                    last_at=last["created_at"],
                    last_text=str(last["text"] or ""),
                    max_likes=max(int(r["likes"] or 0) for r in items),
                )
            )
        return out

    def already_alerted(self, token_address: str, network_id: int) -> bool:
        row = self.conn.execute(
            "SELECT alerted_at FROM fomo_tokens WHERE token_address=? AND network_id=?",
            (token_address, network_id),
        ).fetchone()
        return bool(row and row["alerted_at"])

    # ------------------------------------------------- forward outcome tracking

    def alerted_tokens(self, *, include_suppressed: bool = False) -> list[dict[str, object]]:
        """Every token we have delivered an alert for, with its first alert time.

        The first delivered alert is the entry clock: that is the moment Jiv
        could have acted. Re-alerts on a tier upgrade must not move it, or the
        strategy gets credited with an entry it could not have taken.

        `include_suppressed` also returns the alerts the entry gate refused to
        notify. Forward prices MUST be tracked for those too: they are the
        control group, and without them there is no way to discover that the
        gate is throwing away winners. A gate nobody can measure is how this
        project has repeatedly shipped a signal that cannot fire.

        Rows with `delivered = 0` and no suppression reason are delivery
        FAILURES, and are excluded either way. Nothing reached anyone, so there
        is no honest entry clock for them.
        """
        where = (
            "a.delivered = 1 OR a.suppressed_reason IS NOT NULL"
            if include_suppressed
            else "a.delivered = 1"
        )
        rows = self.conn.execute(
            f"""SELECT a.token_address, a.network_id,
                      MIN(a.ts)  AS first_alert,
                      MAX(a.score) AS score,
                      MAX(a.ticker) AS ticker,
                      MAX(CASE WHEN a.delivered = 1 THEN 1 ELSE 0 END) AS entered
               FROM fomo_alerts a
               WHERE {where}
               GROUP BY a.token_address, a.network_id"""
        ).fetchall()
        out = []
        for r in rows:
            tier = self.best_tier_so_far(r["token_address"], r["network_id"])
            out.append(
                {
                    "token_address": r["token_address"],
                    "network_id": r["network_id"],
                    "first_alert": r["first_alert"],
                    "score": r["score"],
                    "ticker": r["ticker"],
                    "tier": tier,
                    "entered": bool(r["entered"]),
                }
            )
        return out

    def tokens_for_outcome_tracking(self, *, limit: int = 0) -> list[dict[str, object]]:
        """Every token worth recording forward prices for, alerted or not.

        `alerted_tokens` answers "how did our picks do". It cannot answer "were
        they better than what we passed on", because a token that never scored
        a tier never enters it, so the population it returns is exactly the
        population the signal already liked. Grading a classifier on its own
        selections is not a measurement, and it is why the earliness term that
        carries 60 of the signal's ~86 points has never been checked: on
        2026-09-18 the feed held 16,713 ranked theses across 205 tokens while
        forward prices existed for 33, every one of them alerted or suppressed.

        So the tracked set widens to every token that has received a thesis.
        The ones that never alerted are the base rate, and without a base rate
        "rank 1 beats rank 50" cannot be told apart from "tokens people talk
        about go up".

        The clock differs by cohort and `cohort` says which:

        - `alerted` — clock is the first delivered/suppressed alert, unchanged
          from `alerted_tokens`, because that is the moment Jiv could have
          acted and existing `fomo_price_snapshots` rows are already keyed off
          it. Moving it would silently re-date every row already recorded.
        - `thesis` — clock is `first_thesis_at`, when the token entered the
          social universe at all.

        Those are near but not identical events, so the cohorts are comparable
        only up to that difference. Any analysis pooling them without saying so
        overstates its own precision; `cohort` exists so the split is always
        available.

        `limit` caps the set (newest clock first) to bound DexScreener usage.
        0 means no cap.
        """
        # A UNION, not a scan of `fomo_tokens`. A COPY PROBE alerts on a
        # leaderboard position change and never has a thesis row, so selecting
        # from `fomo_tokens` alone would silently drop tokens this method is
        # replacing `alerted_tokens` for -- measured on the live DB: 31 alerted
        # tokens survived the token-table join against 38 from
        # `alerted_tokens`. Widening the population must never narrow it.
        out: list[dict[str, object]] = []
        seen: set[tuple[str, int]] = set()

        for r in self.alerted_tokens(include_suppressed=True):
            key = (str(r["token_address"]), int(r["network_id"]))  # type: ignore[arg-type]
            seen.add(key)
            out.append({**r, "cohort": "alerted"})

        for r in self.conn.execute(
            """SELECT token_address, network_id, ticker, first_thesis_at
                 FROM fomo_tokens
                WHERE first_thesis_at IS NOT NULL"""
        ).fetchall():
            key = (str(r["token_address"]), int(r["network_id"]))
            if key in seen:
                continue
            out.append(
                {
                    "token_address": r["token_address"],
                    "network_id": r["network_id"],
                    "ticker": r["ticker"],
                    "first_alert": r["first_thesis_at"],
                    "cohort": "thesis",
                    "tier": None,
                    "entered": False,
                }
            )

        # Newest clock first. A token whose clock just started still has every
        # age mark ahead of it; one from last week has already missed the early
        # marks that matter most, and those can never be backfilled.
        out.sort(key=lambda d: str(d["first_alert"]), reverse=True)
        return out[:limit] if limit > 0 else out

    def record_price_snapshot(
        self,
        *,
        token_address: str,
        network_id: int,
        age_seconds: float,
        price_usd: float,
        market_cap_usd: float,
        liquidity_usd: float,
        volume_h1_usd: float,
        buys_m5: int,
        sells_m5: int,
    ) -> None:
        """Store one forward price reading. Idempotent per (token, age)."""
        self.conn.execute(
            """INSERT OR IGNORE INTO fomo_price_snapshots
               (token_address,network_id,ts,age_seconds,price_usd,market_cap_usd,
                liquidity_usd,volume_h1_usd,buys_m5,sells_m5)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (token_address, network_id, _now(), age_seconds, price_usd,
             market_cap_usd, liquidity_usd, volume_h1_usd, buys_m5, sells_m5),
        )
        self.conn.commit()

    def price_series(self, token_address: str, network_id: int) -> list[dict[str, object]]:
        """The forward series, shaped for `memecoin_radar.backtest.label_one`.

        That function is already generic over a list of dicts, so the only work
        here is naming the keys it reads (`mint`, `age_seconds`,
        `market_cap_usd`, `liquidity_usd`) rather than reimplementing labelling.
        """
        rows = self.conn.execute(
            """SELECT age_seconds, price_usd, market_cap_usd, liquidity_usd
               FROM fomo_price_snapshots
               WHERE token_address = ? AND network_id = ?
               ORDER BY age_seconds""",
            (token_address, network_id),
        ).fetchall()
        return [
            {
                "mint": token_address,
                "age_seconds": r["age_seconds"],
                "price_usd": r["price_usd"],
                "market_cap_usd": r["market_cap_usd"],
                "liquidity_usd": r["liquidity_usd"],
            }
            for r in rows
        ]

    def recorded_ages(self, token_address: str, network_id: int) -> set[float]:
        rows = self.conn.execute(
            """SELECT age_seconds FROM fomo_price_snapshots
               WHERE token_address = ? AND network_id = ?""",
            (token_address, network_id),
        ).fetchall()
        return {float(r["age_seconds"]) for r in rows}

    def delete_outcome(self, token_address: str, network_id: int) -> int:
        """Remove a labelled outcome. Returns the number of rows deleted.

        Needed because labelling is a re-runnable projection of the price rows,
        and a row written before a data defect was detectable must not survive
        the fix. The concrete case: `fomo_outcomes` was first populated before
        the pair-flip screen existed, so it held a fabricated +18,605% for NVDAX
        that `record_outcome`'s upsert would never have cleared on its own —
        the labeller now SKIPS that token, which would have left the bad row in
        place permanently.
        """
        cur = self.conn.execute(
            "DELETE FROM fomo_outcomes WHERE token_address = ? AND network_id = ?",
            (token_address, network_id),
        )
        return cur.rowcount

    def record_outcome(
        self,
        *,
        token_address: str,
        network_id: int,
        ticker: str,
        tier: str | None,
        score: float,
        alerted_at: str,
        entry_mcap_usd: float,
        entry_liquidity_usd: float,
        returns: dict[str, float | None],
        max_drawdown: float,
        rugged: bool,
        times: dict[str, float | None],
    ) -> None:
        self.conn.execute(
            """INSERT INTO fomo_outcomes
               (token_address,network_id,ticker,tier,score,alerted_at,labeled_at,
                entry_mcap_usd,entry_liquidity_usd,
                max_return_1h,max_return_6h,max_return_24h,max_return_7d,
                max_drawdown,rugged,t_2x,t_5x,t_10x,t_20x,t_50x,t_100x)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(token_address,network_id) DO UPDATE SET
                 labeled_at=excluded.labeled_at,
                 tier=excluded.tier,
                 score=excluded.score,
                 entry_mcap_usd=excluded.entry_mcap_usd,
                 entry_liquidity_usd=excluded.entry_liquidity_usd,
                 max_return_1h=excluded.max_return_1h,
                 max_return_6h=excluded.max_return_6h,
                 max_return_24h=excluded.max_return_24h,
                 max_return_7d=excluded.max_return_7d,
                 max_drawdown=excluded.max_drawdown,
                 rugged=excluded.rugged,
                 t_2x=excluded.t_2x, t_5x=excluded.t_5x, t_10x=excluded.t_10x,
                 t_20x=excluded.t_20x, t_50x=excluded.t_50x, t_100x=excluded.t_100x""",
            (
                token_address, network_id, ticker, tier, score, alerted_at, _now(),
                entry_mcap_usd, entry_liquidity_usd,
                returns.get("max_return_1h"), returns.get("max_return_6h"),
                returns.get("max_return_24h"), returns.get("max_return_7d"),
                max_drawdown, int(rugged),
                times.get("t_2x"), times.get("t_5x"), times.get("t_10x"),
                times.get("t_20x"), times.get("t_50x"), times.get("t_100x"),
            ),
        )
        self.conn.commit()

    def ticker_for(self, token_address: str) -> str | None:
        """Best-known ticker for a mint, from whichever table has seen it.

        The leaderboard holdings payload carries no symbol, so a copy probe
        would otherwise record its outcome against a "?" ticker and be unreadable
        in `fomo_outcomes` months later. Checks the fomo side first because its
        tickers come from the feed, then the sibling radar's launch table.
        """
        for sql in (
            "SELECT ticker FROM fomo_tokens WHERE token_address=? AND ticker<>''",
            "SELECT ticker FROM fomo_feed_items WHERE token_address=? AND ticker<>''"
            " ORDER BY first_seen DESC LIMIT 1",
            "SELECT ticker FROM tokens WHERE mint=? AND ticker<>''",
        ):
            try:
                row = self.conn.execute(sql, (token_address,)).fetchone()
            except sqlite3.OperationalError:
                continue  # sibling table absent in a fomo-only test DB
            if row and row[0]:
                return str(row[0])
        return None

    def best_tier_so_far(self, token_address: str, network_id: int) -> str | None:
        """The strongest tier already delivered for this token, if any.

        Supports re-alerting on a genuine upgrade. v1 marked a token alerted
        once and never spoke about it again, which meant the strongest version
        of a signal — the cluster after it had doubled — was the one guaranteed
        to be suppressed.
        """
        from .signal import TIER_PRIORITY

        rows = self.conn.execute(
            """SELECT tier FROM fomo_alerts
               WHERE token_address=? AND network_id=? AND delivered=1""",
            (token_address, network_id),
        ).fetchall()
        tiers = [r["tier"] for r in rows if r["tier"] in TIER_PRIORITY]
        if not tiers:
            return None
        return min(tiers, key=lambda t: TIER_PRIORITY[t])

    def mark_alerted(self, token_address: str, network_id: int) -> None:
        self.conn.execute(
            "UPDATE fomo_tokens SET alerted_at=? WHERE token_address=? AND network_id=?",
            (_now(), token_address, network_id),
        )
        self.conn.commit()

    def record_alert(
        self, *, token_address: str, network_id: int, ticker: str, tier: str,
        score: float, thesis_rank: int, distinct_authors: int,
        leaderboard_authors: int, total_usd: float, reason: str, delivered: bool,
        suppressed_reason: str | None = None,
    ) -> None:
        """Record an alert, delivered or not.

        `suppressed_reason` is set when the entry gate refused to notify. It is
        what separates "we chose not to post this" from "posting broke", which
        `delivered=0` alone cannot express.
        """
        self.conn.execute(
            """INSERT INTO fomo_alerts
               (ts,token_address,network_id,ticker,tier,score,thesis_rank,
                distinct_authors,leaderboard_authors,total_usd,reason,delivered,
                suppressed_reason)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_now(), token_address, network_id, ticker, tier, score, thesis_rank,
             distinct_authors, leaderboard_authors, total_usd, reason, int(delivered),
             suppressed_reason),
        )
        self.conn.commit()

    # --------------------------------------------------------- leaderboard

    def _holding_changed(
        self, prev: float, now: float, handle: str, token: str
    ) -> bool:
        """True when this position must be written: a trade, or a due heartbeat.

        `HOLDINGS_TRADE_EPS` keeps reported-quantity rounding from registering as
        a trade. The heartbeat exists so a position that nobody touches still
        leaves a price trail; without it the table records only trade instants
        and there is no forward series to measure an outcome against.
        """
        if prev <= 0:
            return True
        if abs(now / prev - 1.0) > HOLDINGS_TRADE_EPS:
            return True
        row = self.conn.execute(
            """SELECT captured_at FROM fomo_leaderboard_holdings
               WHERE handle = ? AND token_address = ?
               ORDER BY captured_at DESC LIMIT 1""",
            (handle, token),
        ).fetchone()
        if row is None or not row[0]:
            return True
        last = _parse_ts(str(row[0]))
        if last is None:
            return True
        age = (datetime.now(timezone.utc) - last).total_seconds()
        return age >= HOLDINGS_HEARTBEAT_S

    def _last_holding_amount(self, handle: str, token: str) -> float | None:
        row = self.conn.execute(
            """SELECT human_amount FROM fomo_leaderboard_holdings
               WHERE handle = ? AND token_address = ?
               ORDER BY captured_at DESC LIMIT 1""",
            (handle, token),
        ).fetchone()
        return None if row is None or row[0] is None else float(row[0])

    def record_leaderboard(
        self, window: str, traders: list[LeaderboardTrader],
        *, dedupe_holdings: bool = True,
    ) -> list[CopyEvent]:
        """Persist one leaderboard capture.

        Holdings rows are written only when a trader's token QUANTITY changed,
        because that is the only thing in this payload that means a trade
        happened: `value` moves with price on every poll even when nobody did
        anything. Without the dedupe, polling often enough to be useful as a
        trade tape costs 264 MB/day (1,320 rows a round at 139 bytes, measured
        2026-09-17), and 83% of those rows say "no trade".

        `HOLDINGS_HEARTBEAT_S` still forces a row through periodically so the
        table keeps a coarse price series per position rather than only
        recording the instants someone traded.
        """
        captured = _now()
        cur = self.conn.cursor()
        kept = skipped = 0
        events: list[CopyEvent] = []
        for rank, t in enumerate(traders, start=1):
            cur.execute(
                """INSERT OR REPLACE INTO fomo_leaderboard
                   (window,captured_at,rank,user_id,handle,display_name,
                    solana_address,evm_address,pnl,num_trades,total_volume,
                    followers,total_holdings)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (window, captured, rank, t.user_id, t.handle, t.display_name,
                 t.solana_address, t.evm_address, t.pnl, t.num_trades,
                 t.total_volume, t.followers, t.total_holdings),
            )
            for h in t.top_holdings:
                token = str(h.get("tokenAddress") or "")
                amount = h.get("humanAmount")
                if token and amount is not None:
                    prev = self._last_holding_amount(t.handle, token)
                    if prev is not None and prev > 0 and abs(
                        float(amount) / prev - 1.0
                    ) > HOLDINGS_TRADE_EPS:
                        events.append(CopyEvent(
                            handle=t.handle, token_address=token,
                            network_id=h.get("networkId"),
                            ticker=str(h.get("symbol") or h.get("ticker") or "") or None,
                            prev_amount=prev, new_amount=float(amount),
                            price_usd=h.get("price"),
                        ))
                    if dedupe_holdings and prev is not None and not self._holding_changed(
                        prev, float(amount), t.handle, token
                    ):
                        skipped += 1
                        continue
                cur.execute(
                    """INSERT INTO fomo_leaderboard_holdings
                       (window,captured_at,handle,token_address,network_id,
                        human_amount,price,value,pnl)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (window, captured, t.handle, token,
                     h.get("networkId"), h.get("humanAmount"), h.get("price"),
                     h.get("value"), h.get("pnl")),
                )
                kept += 1
            # Feed the radar's existing smart-money table. This is the PRD
            # Phase 2 unblock: a free, PnL-ranked set of Solana addresses.
            if t.solana_address:
                cur.execute(
                    """INSERT INTO wallets (address,realized_pnl,tags,updated_at)
                       VALUES (?,?,?,?)
                       ON CONFLICT(address) DO UPDATE SET
                         realized_pnl=excluded.realized_pnl,
                         tags=excluded.tags,
                         updated_at=excluded.updated_at""",
                    (t.solana_address, t.pnl, f"fomo:{window}:{t.handle}", captured),
                )
        self.conn.commit()
        if skipped:
            # Reported so the dedupe is auditable. If `kept` ever collapses to 0
            # the tape has gone silent, which must not look like a quiet market.
            log.info(
                "leaderboard %s holdings: %d written, %d unchanged",
                window, kept, skipped,
            )
        return events

    def leaderboard_handles(self) -> set[str]:
        """Handles from the most recent capture of every window."""
        rows = self.conn.execute(
            """SELECT handle FROM fomo_leaderboard
               WHERE (window, captured_at) IN (
                 SELECT window, MAX(captured_at) FROM fomo_leaderboard GROUP BY window
               )"""
        ).fetchall()
        return {r["handle"] for r in rows if r["handle"]}

    def stats(self) -> dict[str, int]:
        q = lambda sql: int(self.conn.execute(sql).fetchone()[0])  # noqa: E731
        return {
            "feed_items": q("SELECT COUNT(*) FROM fomo_feed_items"),
            "theses": q("SELECT COUNT(*) FROM fomo_feed_items WHERE item_type='thesis'"),
            "tokens": q("SELECT COUNT(*) FROM fomo_tokens"),
            "alerts": q("SELECT COUNT(*) FROM fomo_alerts"),
            "leaderboard_wallets": q(
                "SELECT COUNT(DISTINCT solana_address) FROM fomo_leaderboard"
            ),
        }
