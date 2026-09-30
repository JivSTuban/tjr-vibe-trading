"""Durable ENTER NOW execution staging. Real-money submission is unavailable.

The local simulation exercises the order state machine through Playwright.
Owner policy authorization is recorded in decision 0002. Live handlers are
still unimplemented. Proposal state tracks queue lifecycle, not TJR approval.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

from .config import SOLANA_NETWORK_ID, SignalConfig
from .signal import TokenSignal, entry_gate, evaluate

STRATEGY = "fomo-enter-v3-sl20-tp10-proposed"
STOP = 0.20
TARGET = 0.10


class ExecutionBlocked(RuntimeError):
    pass


def positive(value: float) -> bool:
    return math.isfinite(value) and value > 0


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    source_id: str
    source_at: str
    token_address: str
    network_id: int
    ticker: str
    trade_usd: float
    reference_price: float
    quote_at: float
    created_at: float
    expires_at: float
    evidence: tuple[str, ...]
    strategy: str = STRATEGY
    status: str = "proposed"
    stop_pct: float = STOP
    take_profit_pct: float = TARGET


def propose(sig: TokenSignal, *, source_id: str, source_at: str,
            trade_usd: float, quote_at: float, cfg: SignalConfig,
            now: float | None = None) -> Proposal:
    """Snapshot evidence before notification; rerun the cost gate at actual size."""
    now = time.time() if now is None else now
    stamp = datetime.fromisoformat(source_at.replace("Z", "+00:00"))
    if stamp.tzinfo is None or not source_id:
        raise ExecutionBlocked("source timestamp must have timezone and source ID")
    age = now - stamp.timestamp()
    if not all(positive(x) for x in (trade_usd, sig.liquidity.price_usd,
                                    sig.liquidity.liquidity_usd, quote_at, now)):
        raise ExecutionBlocked("missing or nonfinite size/market data")
    if not 0 <= age <= cfg.entry_max_thesis_age_s:
        raise ExecutionBlocked("source is future-dated or stale")
    if not 0 <= now - quote_at <= 15:
        raise ExecutionBlocked("quote is future-dated or older than 15 seconds")
    if sig.network_id != SOLANA_NETWORK_ID or not sig.token_address or sig.blocked_by:
        raise ExecutionBlocked("unsupported instrument or blocked signal")
    if not math.isfinite(sig.score):
        raise ExecutionBlocked("nonfinite signal score")
    if not all(math.isfinite(x) for x in (
        sig.liquidity.volume_h1_usd, sig.liquidity.market_cap_usd,
        sig.liquidity.buys_m5, sig.liquidity.sells_m5, sig.total_usd,
        sig.max_usd, sig.thesis_rank,
    )) or sig.thesis_rank < 0:
        raise ExecutionBlocked("nonfinite market or signal evidence")
    # A fresh quote can invalidate the earlier signal's liquidity/activity gates.
    fresh = evaluate(token_address=sig.token_address, network_id=sig.network_id,
                     ticker=sig.ticker, thesis_rank=sig.thesis_rank, cluster=sig.cluster,
                     liquidity=sig.liquidity, largest_usd=sig.max_usd,
                     total_usd=sig.total_usd, cfg=cfg)
    if fresh.tier is None:
        raise ExecutionBlocked("; ".join(fresh.blocked_by))
    verdict = entry_gate(sig, thesis_age_s=age, cfg=replace(cfg, entry_size_usd=trade_usd))
    if not verdict.enter:
        raise ExecutionBlocked("; ".join(verdict.blocked_by))
    # One entry per token/version, even when a second thesis or a restart arrives.
    key = f"{STRATEGY}:{sig.network_id}:{sig.token_address}"
    return Proposal(
        hashlib.sha256(key.encode()).hexdigest(), source_id, source_at,
        sig.token_address, sig.network_id, sig.ticker, trade_usd,
        sig.liquidity.price_usd, quote_at, now,
        min(now + 60, stamp.timestamp() + cfg.entry_max_thesis_age_s),
        (f"fomo_feed_items:{source_id}", "research/fomo/FINDINGS.md",
         *sig.reasons, *verdict.reasons),
    )


class ExecutionStore:
    """Separate journal; signal delivery flags never act as trade authorization."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
          PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS execution_orders (
            id TEXT PRIMARY KEY, proposal TEXT NOT NULL, state TEXT NOT NULL,
            fill_price REAL, quantity REAL, stop_price REAL, target_price REAL,
            receipt TEXT, exit_price REAL, exit_reason TEXT
          );
          CREATE TABLE IF NOT EXISTS execution_events (
            id INTEGER PRIMARY KEY, ts REAL NOT NULL, order_id TEXT,
            event TEXT NOT NULL
          );
        """)

    def enqueue(self, proposal: Proposal) -> bool:
        with self.conn:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO execution_orders(id,proposal,state) VALUES (?,?,'proposed')",
                (proposal.proposal_id, json.dumps(asdict(proposal), allow_nan=False)),
            )
            if cur.rowcount:
                self.event(proposal.proposal_id, "proposed")
        return bool(cur.rowcount)

    def event(self, order_id: str, event: str) -> None:
        self.conn.execute("INSERT INTO execution_events(ts,order_id,event) VALUES (?,?,?)",
                          (time.time(), order_id, event))

    def row(self, order_id: str):
        return self.conn.execute("SELECT * FROM execution_orders WHERE id=?", (order_id,)).fetchone()

    def close(self):
        self.conn.close()


@dataclass(frozen=True)
class Quote:
    token_address: str
    price: float
    observed_at: float


@dataclass(frozen=True)
class Receipt:
    order_id: str
    token_address: str
    side: str
    quantity: float
    price: float
    reference: str


class SimulationExecutor:
    """One position, one worker, persistent uncertain states, no automatic retry.

    This is a local engineering harness, not strategy approval or a live gateway.
    The browser adapter must itself enforce an isolated simulation environment.
    """

    environment = "isolated-simulation"
    restart_states = ("submitting", "open", "closing", "uncertain")

    def __init__(self, store: ExecutionStore, browser, halt: Path):
        import fcntl
        self.store, self.browser, self.halt = store, browser, halt
        self._lock = open(str(store.path) + ".worker.lock", "a")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock.close()
            raise ExecutionBlocked("another execution worker owns this journal") from None
        placeholders = ",".join("?" for _ in self.restart_states)
        if self.store.conn.execute(
            f"SELECT 1 FROM execution_orders WHERE state IN ({placeholders})", self.restart_states
        ).fetchone():
            self.trip("unreconciled_submission")

    def close(self):
        self._lock.close()

    def trip(self, reason: str):
        self.halt.parent.mkdir(parents=True, exist_ok=True)
        # Never clear or overwrite an operator's existing halt.
        try:
            with self.halt.open("x") as handle:
                handle.write(reason)
        except FileExistsError:
            pass

    def check(self):
        if self.browser.environment != self.environment:
            self.trip("simulation_environment_mismatch")
            raise ExecutionBlocked(f"executor requires {self.environment} adapter")
        if self.halt.exists():
            raise ExecutionBlocked("HALT requires manual review")

    def quote_check(self, quote: Quote, proposal: Proposal, now: float):
        if (quote.token_address != proposal.token_address or not positive(quote.price)
                or not math.isfinite(quote.observed_at)
                or not 0 <= now - quote.observed_at <= 15):
            raise ExecutionBlocked("wrong token or stale/invalid quote")

    def uncertain(self, order_id: str, reason: str):
        self.trip(reason)
        with self.store.conn:
            self.store.conn.execute("UPDATE execution_orders SET state='uncertain' WHERE id=?", (order_id,))
            self.store.event(order_id, reason)

    def validate_buy_amount(self, receipt: Receipt, proposal: Proposal):
        if not math.isclose(receipt.quantity * receipt.price, proposal.trade_usd, rel_tol=1e-6):
            raise ExecutionBlocked("fill amount mismatch")

    async def enter(self, order_id: str, quote: Quote, *, now: float | None = None):
        now = time.time() if now is None else now
        self.check()
        row = self.store.row(order_id)
        if row is None or row["state"] != "proposed":
            raise ExecutionBlocked("unknown or already consumed proposal")
        p = Proposal(**json.loads(row["proposal"]))
        if (p.strategy != STRATEGY or p.status != "proposed" or p.stop_pct != STOP
                or p.take_profit_pct != TARGET or not p.evidence
                or p.network_id != SOLANA_NETWORK_ID or not positive(p.trade_usd)
                or not positive(p.reference_price) or not p.created_at <= now < p.expires_at):
            raise ExecutionBlocked("invalid or expired proposal")
        self.quote_check(quote, p, now)
        if abs(quote.price / p.reference_price - 1) > 0.03:
            raise ExecutionBlocked("entry price moved more than 3 percent")
        if self.store.conn.execute(
            "SELECT 1 FROM execution_orders WHERE state IN ('submitting','open','closing','uncertain')"
        ).fetchone():
            raise ExecutionBlocked("one-position simulation limit")
        with self.store.conn:
            self.store.conn.execute("UPDATE execution_orders SET state='submitting' WHERE id=?", (order_id,))
            self.store.event(order_id, "submitting")
        try:
            self.check()
            receipt = await self.browser.buy(p, quote)
            self.validate_receipt(receipt, p, "buy")
            self.validate_buy_amount(receipt, p)
            with self.store.conn:
                self.store.conn.execute(
                    """UPDATE execution_orders SET state='open',fill_price=?,quantity=?,
                       stop_price=?,target_price=?,receipt=? WHERE id=?""",
                    (receipt.price, receipt.quantity, receipt.price * (1 - STOP),
                     receipt.price * (1 + TARGET), receipt.reference, order_id),
                )
                self.store.event(order_id, "open")
        except BaseException:
            self.uncertain(order_id, "buy_requires_reconciliation")
            raise

    @staticmethod
    def validate_receipt(r: Receipt, p: Proposal, side: str):
        if (r.order_id != p.proposal_id or r.token_address != p.token_address
                or r.side != side or not r.reference or not positive(r.quantity)
                or not positive(r.price)):
            raise ExecutionBlocked("unverified fill receipt")

    async def monitor(self, order_id: str, quote: Quote, *, now: float | None = None):
        self.check()
        row = self.store.row(order_id)
        if row is None or row["state"] != "open":
            raise ExecutionBlocked("position is not confirmed open")
        p = Proposal(**json.loads(row["proposal"]))
        if not all(row[k] is not None and positive(row[k]) for k in
                   ("fill_price", "quantity", "stop_price", "target_price")):
            self.trip("missing_stop_or_position_data")
            raise ExecutionBlocked("missing protection")
        if (not math.isclose(row['stop_price'], row['fill_price'] * (1 - STOP), rel_tol=1e-9)
                or not math.isclose(row['target_price'], row['fill_price'] * (1 + TARGET), rel_tol=1e-9)):
            self.trip("protection_changed")
            raise ExecutionBlocked("protection changed since fill")
        try:
            self.quote_check(quote, p, time.time() if now is None else now)
        except ExecutionBlocked:
            self.trip("position_monitor_unavailable")
            raise
        reason = ("stop_loss" if quote.price <= row["stop_price"] else
                  "take_profit" if quote.price >= row["target_price"] else None)
        if reason is None:
            return None
        with self.store.conn:
            self.store.conn.execute("UPDATE execution_orders SET state='closing',exit_reason=? WHERE id=?",
                                    (reason, order_id))
            self.store.event(order_id, "closing_" + reason)
        try:
            self.check()
            receipt = await self.browser.sell(p, quote, row["quantity"])
            self.validate_receipt(receipt, p, "sell")
            if not math.isclose(receipt.quantity, row["quantity"], rel_tol=1e-9):
                raise ExecutionBlocked("partial exit requires reconciliation")
            with self.store.conn:
                self.store.conn.execute("UPDATE execution_orders SET state='closed',exit_price=?,receipt=? WHERE id=?",
                                        (receipt.price, receipt.reference, order_id))
                self.store.event(order_id, "closed_" + reason)
            return reason
        except BaseException:
            self.uncertain(order_id, "sell_requires_reconciliation")
            raise
