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

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .api import LeaderboardTrader, ThesisItem, dumps_links

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
    delivered       INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_fomo_alerts_token ON fomo_alerts(token_address);

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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_x_link(item: ThesisItem) -> bool:
    return any("x.com" in l or "twitter.com" in l for l in item.links)


class FomoStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

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

    def already_alerted(self, token_address: str, network_id: int) -> bool:
        row = self.conn.execute(
            "SELECT alerted_at FROM fomo_tokens WHERE token_address=? AND network_id=?",
            (token_address, network_id),
        ).fetchone()
        return bool(row and row["alerted_at"])

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
    ) -> None:
        self.conn.execute(
            """INSERT INTO fomo_alerts
               (ts,token_address,network_id,ticker,tier,score,thesis_rank,
                distinct_authors,leaderboard_authors,total_usd,reason,delivered)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_now(), token_address, network_id, ticker, tier, score, thesis_rank,
             distinct_authors, leaderboard_authors, total_usd, reason, int(delivered)),
        )
        self.conn.commit()

    # --------------------------------------------------------- leaderboard

    def record_leaderboard(self, window: str, traders: list[LeaderboardTrader]) -> None:
        captured = _now()
        cur = self.conn.cursor()
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
                cur.execute(
                    """INSERT INTO fomo_leaderboard_holdings
                       (window,captured_at,handle,token_address,network_id,
                        human_amount,price,value,pnl)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (window, captured, t.handle, str(h.get("tokenAddress") or ""),
                     h.get("networkId"), h.get("humanAmount"), h.get("price"),
                     h.get("value"), h.get("pnl")),
                )
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
