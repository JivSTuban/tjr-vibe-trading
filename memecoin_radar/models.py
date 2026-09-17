"""Core value objects shared across ingestion, scoring, and alerting.

Plain dataclasses rather than pydantic: these cross only in-process boundaries,
and the ingest path runs on every one of ~34k daily launch events, so validation
overhead buys nothing here. Anything crossing a network boundary is validated at
the edge in `sources/`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# pump.fun mints a fixed 1B supply, so a creator's initial buy converts directly
# to a percentage of supply without an extra RPC call.
PUMP_TOTAL_SUPPLY = 1_000_000_000.0


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class LaunchEvent:
    """A `txType: "create"` event off the PumpPortal new-token stream.

    Field names mirror the wire payload observed live on 2026-09-17 so that a
    shape change upstream surfaces as a parse error rather than a silent zero.
    """

    mint: str
    name: str
    symbol: str
    creator: str  # wire field `traderPublicKey`
    signature: str
    uri: str
    pool: str
    initial_buy: float
    sol_amount: float
    market_cap_sol: float
    v_sol_in_curve: float
    v_tokens_in_curve: float
    is_mayhem_mode: bool = False
    seen_at: datetime = field(default_factory=utcnow)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def creator_supply_pct(self) -> float:
        """Share of total supply the deployer bought in the creation tx.

        The single cheapest rug signal available at second zero: it needs no
        RPC call, and a deployer holding a large opening block is the precondition
        for every dump pattern in PRD section 3.2.
        """
        if self.initial_buy <= 0:
            return 0.0
        return min(100.0, self.initial_buy / PUMP_TOTAL_SUPPLY * 100.0)


@dataclass(slots=True)
class TokenMetadata:
    """Off-chain metadata behind the launch `uri` (IPFS), fetched best-effort.

    Optional by design: IPFS gateways routinely take seconds or fail, and the
    PRD requires a sub-minute alert, so a missing description must degrade the
    narrative score rather than block the alert.
    """

    description: str = ""
    image: str = ""
    twitter: str = ""
    telegram: str = ""
    website: str = ""
    fetched: bool = False


@dataclass(slots=True)
class TradeEvent:
    """A buy or sell off the PumpPortal per-token trade stream."""

    mint: str
    trader: str
    is_buy: bool
    sol_amount: float
    token_amount: float
    market_cap_sol: float
    signature: str
    seen_at: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class MarketSnapshot:
    """Market state for one token at one age, the unit of the backtest dataset."""

    mint: str
    ts: datetime
    age_seconds: float
    price_usd: float = 0.0
    market_cap_usd: float = 0.0
    liquidity_usd: float = 0.0
    volume_usd: float = 0.0
    buys: int = 0
    sells: int = 0
    unique_buyers: int = 0
    holder_count: int = 0
    source: str = "pumpportal"


@dataclass(slots=True)
class ScoreBreakdown:
    """A 0-100 score plus the per-component detail behind it.

    `coverage` is the fraction of the PRD's weight that was actually measurable.
    It is carried all the way onto the alert because a 90 backed by 60% coverage
    and a 90 backed by 100% coverage are not the same claim, and collapsing them
    is the exact mistake the PRD warns about for Moon-versus-Rug.
    """

    score: float
    components: dict[str, float] = field(default_factory=dict)
    coverage: float = 1.0
    missing: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TrendReference:
    """A currently hot token held in the live Trend Context (PRD section 4.1)."""

    mint: str
    name: str
    symbol: str
    narrative_tokens: set[str] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)
    creator: str = ""
    market_cap_usd: float = 0.0
    liquidity_usd: float = 0.0
    volume_accel: float = 0.0
    momentum_state: str = "emerging"  # emerging | accelerating | peak | cooling
    trend_score: float = 0.0
    first_seen: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class Candidate:
    """A launch under observation, carried through the enrichment windows."""

    launch: LaunchEvent
    metadata: TokenMetadata = field(default_factory=TokenMetadata)
    snapshots: list[MarketSnapshot] = field(default_factory=list)
    buyers: set[str] = field(default_factory=set)
    sellers: set[str] = field(default_factory=set)
    buy_count: int = 0
    sell_count: int = 0
    sol_volume: float = 0.0
    creator_sold: bool = False
    smart_wallets: set[str] = field(default_factory=set)
    moon: ScoreBreakdown | None = None
    rug: ScoreBreakdown | None = None
    trend: ScoreBreakdown | None = None
    related_trend: TrendReference | None = None
    alerts_fired: set[str] = field(default_factory=set)

    @property
    def mint(self) -> str:
        return self.launch.mint

    @property
    def age_seconds(self) -> float:
        return (utcnow() - self.launch.seen_at).total_seconds()


@dataclass(slots=True)
class Alert:
    """One notification decision, persisted whether or not delivery succeeds."""

    mint: str
    ts: datetime
    alert_type: str  # WATCH | HOT | ULTRA | TREND_ECHO | SMART_MONEY | RUG_WARNING
    moon_score: float
    rug_score: float
    relation_score: float
    reasons: list[str] = field(default_factory=list)
    delivered: bool = False
