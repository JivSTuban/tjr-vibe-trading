"""SQLite persistence for the radar, implementing the PRD section 7 data model.

Why SQLite and not the PRD's Postgres/TimescaleDB: this is a single-writer
personal notifier whose dataset is append-mostly, so Postgres would add an
always-on service and no capability. The schema below is plain enough to move
over with a dump when there is a second writer or a dashboard reading live.

The non-negotiable part is PRD section 8: EVERY considered token is written, not
only the alerted ones. Without the rejects there is no base rate, and without a
base rate the thresholds in `config.py` can never be earned.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    Alert,
    Candidate,
    LaunchEvent,
    MarketSnapshot,
    ScoreBreakdown,
    TokenMetadata,
    TradeEvent,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tokens (
    mint            TEXT PRIMARY KEY,
    chain           TEXT NOT NULL DEFAULT 'solana',
    name            TEXT,
    ticker          TEXT,
    created_at      TEXT NOT NULL,
    deployer        TEXT,
    pool            TEXT,
    uri             TEXT,
    description     TEXT,
    image           TEXT,
    twitter         TEXT,
    telegram        TEXT,
    website         TEXT,
    initial_buy     REAL,
    creator_supply_pct REAL,
    market_cap_sol  REAL,
    is_mayhem_mode  INTEGER DEFAULT 0,
    signature       TEXT,
    raw             TEXT
);
CREATE INDEX IF NOT EXISTS idx_tokens_deployer ON tokens(deployer);
CREATE INDEX IF NOT EXISTS idx_tokens_created ON tokens(created_at);

CREATE TABLE IF NOT EXISTS market_snapshots (
    mint            TEXT NOT NULL,
    ts              TEXT NOT NULL,
    age_seconds     REAL NOT NULL,
    price_usd       REAL,
    market_cap_usd  REAL,
    liquidity_usd   REAL,
    volume_usd      REAL,
    buys            INTEGER,
    sells           INTEGER,
    unique_buyers   INTEGER,
    holder_count    INTEGER,
    source          TEXT,
    PRIMARY KEY (mint, age_seconds)
);

CREATE TABLE IF NOT EXISTS holder_snapshots (
    mint            TEXT NOT NULL,
    ts              TEXT NOT NULL,
    holder_count    INTEGER,
    top10_pct       REAL,
    creator_pct     REAL,
    mint_authority  TEXT,
    freeze_authority TEXT,
    PRIMARY KEY (mint, ts)
);

CREATE TABLE IF NOT EXISTS wallets (
    address         TEXT PRIMARY KEY,
    quality_score   REAL DEFAULT 0,
    realized_pnl    REAL DEFAULT 0,
    early_win_rate  REAL DEFAULT 0,
    launches_seen   INTEGER DEFAULT 0,
    tags            TEXT,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS wallet_token_events (
    wallet          TEXT NOT NULL,
    mint            TEXT NOT NULL,
    ts              TEXT NOT NULL,
    side            TEXT NOT NULL,
    sol_amount      REAL,
    token_amount    REAL,
    market_cap_sol  REAL,
    signature       TEXT
);
CREATE INDEX IF NOT EXISTS idx_wte_mint ON wallet_token_events(mint);
CREATE INDEX IF NOT EXISTS idx_wte_wallet ON wallet_token_events(wallet);

CREATE TABLE IF NOT EXISTS social_mentions (
    mint            TEXT NOT NULL,
    ts              TEXT NOT NULL,
    platform        TEXT,
    author_id       TEXT,
    text_hash       TEXT,
    engagement      REAL,
    quality         REAL
);
CREATE INDEX IF NOT EXISTS idx_social_mint ON social_mentions(mint);

CREATE TABLE IF NOT EXISTS trend_context (
    mint                TEXT PRIMARY KEY,
    name                TEXT,
    symbol              TEXT,
    keywords            TEXT,
    narrative_tokens    TEXT,
    creator             TEXT,
    market_cap_usd      REAL,
    liquidity_usd       REAL,
    volume_accel        REAL,
    momentum_state      TEXT,
    trend_score         REAL,
    first_seen          TEXT,
    updated_at          TEXT
);

CREATE TABLE IF NOT EXISTS scores (
    mint            TEXT NOT NULL,
    ts              TEXT NOT NULL,
    age_seconds     REAL,
    kind            TEXT NOT NULL,
    score           REAL,
    coverage        REAL,
    components      TEXT,
    missing         TEXT,
    PRIMARY KEY (mint, age_seconds, kind)
);

CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mint            TEXT NOT NULL,
    ts              TEXT NOT NULL,
    alert_type      TEXT NOT NULL,
    moon_score      REAL,
    rug_score       REAL,
    relation_score  REAL,
    reasons         TEXT,
    delivered       INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alerts_mint ON alerts(mint);

CREATE TABLE IF NOT EXISTS outcomes (
    mint            TEXT PRIMARY KEY,
    labeled_at      TEXT,
    entry_mcap_usd  REAL,
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
    t_100x          REAL
);
"""


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class Store:
    """Thin synchronous wrapper over SQLite.

    Synchronous on purpose: at ~24 writes/min a WAL-mode local insert costs
    microseconds, far below any threshold worth an async pool, and keeping it
    blocking removes a whole class of interleaving bug from the ingest path.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), timeout=30)
        self.conn.row_factory = sqlite3.Row
        # WAL so a reader (backtest, dashboard) never blocks the ingest writer.
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ---------------------------------------------------------------- tokens

    def record_launch(self, ev: LaunchEvent, meta: TokenMetadata | None = None) -> None:
        """Insert a launch. Called for every create event, alerted or not."""
        meta = meta or TokenMetadata()
        with self.tx() as c:
            c.execute(
                """INSERT OR IGNORE INTO tokens
                   (mint, name, ticker, created_at, deployer, pool, uri, description,
                    image, twitter, telegram, website, initial_buy, creator_supply_pct,
                    market_cap_sol, is_mayhem_mode, signature, raw)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    ev.mint, ev.name, ev.symbol, _iso(ev.seen_at), ev.creator, ev.pool,
                    ev.uri, meta.description, meta.image, meta.twitter, meta.telegram,
                    meta.website, ev.initial_buy, ev.creator_supply_pct,
                    ev.market_cap_sol, int(ev.is_mayhem_mode), ev.signature,
                    json.dumps(ev.raw, separators=(",", ":")),
                ),
            )

    def update_metadata(self, mint: str, meta: TokenMetadata) -> None:
        with self.tx() as c:
            c.execute(
                """UPDATE tokens SET description=?, image=?, twitter=?, telegram=?,
                   website=? WHERE mint=?""",
                (meta.description, meta.image, meta.twitter, meta.telegram,
                 meta.website, mint),
            )

    def deployer_launch_count(self, deployer: str) -> int:
        """How many launches this deployer has made in our own record.

        A free deployer-history signal: because the radar streams every creation,
        repeat launchers accumulate here without any paid history API.
        """
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM tokens WHERE deployer = ?", (deployer,)
        ).fetchone()
        return int(row["n"]) if row else 0

    def deployer_rug_count(self, deployer: str) -> int:
        """Prior launches by this deployer that we later labelled as rugged."""
        row = self.conn.execute(
            """SELECT COUNT(*) AS n FROM tokens t
               JOIN outcomes o ON o.mint = t.mint
               WHERE t.deployer = ? AND o.rugged = 1""",
            (deployer,),
        ).fetchone()
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------- snapshots

    def record_snapshot(self, snap: MarketSnapshot) -> None:
        with self.tx() as c:
            c.execute(
                """INSERT OR REPLACE INTO market_snapshots
                   (mint, ts, age_seconds, price_usd, market_cap_usd, liquidity_usd,
                    volume_usd, buys, sells, unique_buyers, holder_count, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    snap.mint, _iso(snap.ts), snap.age_seconds, snap.price_usd,
                    snap.market_cap_usd, snap.liquidity_usd, snap.volume_usd,
                    snap.buys, snap.sells, snap.unique_buyers, snap.holder_count,
                    snap.source,
                ),
            )

    def record_holders(
        self,
        mint: str,
        ts: datetime,
        holder_count: int,
        top10_pct: float,
        creator_pct: float,
        mint_authority: str | None,
        freeze_authority: str | None,
    ) -> None:
        with self.tx() as c:
            c.execute(
                """INSERT OR REPLACE INTO holder_snapshots
                   (mint, ts, holder_count, top10_pct, creator_pct,
                    mint_authority, freeze_authority)
                   VALUES (?,?,?,?,?,?,?)""",
                (mint, _iso(ts), holder_count, top10_pct, creator_pct,
                 mint_authority, freeze_authority),
            )

    def record_trades(self, trades: Iterable[TradeEvent]) -> None:
        rows = [
            (t.trader, t.mint, _iso(t.seen_at), "buy" if t.is_buy else "sell",
             t.sol_amount, t.token_amount, t.market_cap_sol, t.signature)
            for t in trades
        ]
        if not rows:
            return
        with self.tx() as c:
            c.executemany(
                """INSERT INTO wallet_token_events
                   (wallet, mint, ts, side, sol_amount, token_amount,
                    market_cap_sol, signature)
                   VALUES (?,?,?,?,?,?,?,?)""",
                rows,
            )

    # ---------------------------------------------------------------- scores

    def record_score(
        self, mint: str, ts: datetime, age_seconds: float, kind: str, sb: ScoreBreakdown
    ) -> None:
        with self.tx() as c:
            c.execute(
                """INSERT OR REPLACE INTO scores
                   (mint, ts, age_seconds, kind, score, coverage, components, missing)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    mint, _iso(ts), age_seconds, kind, sb.score, sb.coverage,
                    json.dumps(sb.components, separators=(",", ":")),
                    json.dumps(sb.missing, separators=(",", ":")),
                ),
            )

    def record_candidate_scores(self, cand: Candidate, age_seconds: float) -> None:
        """Persist whichever of the three scores were computed at this age."""
        now = datetime.now(timezone.utc)
        for kind, sb in (("moon", cand.moon), ("rug", cand.rug), ("trend", cand.trend)):
            if sb is not None:
                self.record_score(cand.mint, now, age_seconds, kind, sb)

    # ---------------------------------------------------------------- alerts

    def record_alert(self, alert: Alert) -> int:
        with self.tx() as c:
            cur = c.execute(
                """INSERT INTO alerts
                   (mint, ts, alert_type, moon_score, rug_score, relation_score,
                    reasons, delivered)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    alert.mint, _iso(alert.ts), alert.alert_type, alert.moon_score,
                    alert.rug_score, alert.relation_score,
                    json.dumps(alert.reasons, separators=(",", ":")),
                    int(alert.delivered),
                ),
            )
            return int(cur.lastrowid or 0)

    def mark_delivered(self, alert_id: int, delivered: bool = True) -> None:
        with self.tx() as c:
            c.execute(
                "UPDATE alerts SET delivered=? WHERE id=?", (int(delivered), alert_id)
            )

    # --------------------------------------------------------------- wallets

    def smart_wallets(self, min_quality: float = 50.0) -> dict[str, float]:
        """Watchlist of wallets good enough to count as smart money.

        Empty until the PRD's Phase 2 leaderboard is built, which is why the
        Moon scorer treats smart money as an unavailable component rather than
        scoring it zero.
        """
        rows = self.conn.execute(
            "SELECT address, quality_score FROM wallets WHERE quality_score >= ?",
            (min_quality,),
        ).fetchall()
        return {r["address"]: float(r["quality_score"]) for r in rows}

    def upsert_wallet(
        self, address: str, quality_score: float, tags: list[str] | None = None
    ) -> None:
        with self.tx() as c:
            c.execute(
                """INSERT INTO wallets (address, quality_score, tags, updated_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(address) DO UPDATE SET
                     quality_score=excluded.quality_score,
                     tags=excluded.tags,
                     updated_at=excluded.updated_at""",
                (
                    address, quality_score,
                    json.dumps(tags or [], separators=(",", ":")),
                    _iso(datetime.now(timezone.utc)),
                ),
            )

    # ---------------------------------------------------------------- counts

    def counts(self) -> dict[str, int]:
        """Row counts, used by the status line and the backtest sanity check."""
        out: dict[str, int] = {}
        for table in ("tokens", "market_snapshots", "alerts", "outcomes",
                      "wallet_token_events", "scores"):
            row = self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            out[table] = int(row["n"]) if row else 0
        return out

    def alert_counts_by_type(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT alert_type, COUNT(*) AS n FROM alerts GROUP BY alert_type"
        ).fetchall()
        return {r["alert_type"]: int(r["n"]) for r in rows}

    def snapshots_for(self, mint: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT * FROM market_snapshots WHERE mint = ?
               ORDER BY age_seconds ASC""",
            (mint,),
        ).fetchall()
        return [dict(r) for r in rows]
