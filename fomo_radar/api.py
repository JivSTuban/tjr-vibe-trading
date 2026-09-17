"""Typed wrappers over the fomo endpoints we actually use.

Endpoint behaviour documented here was observed live on 2026-09-17, not read
from any spec — fomo publishes none. See `research/fomo/FINDINGS.md`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .config import SOLANA_NETWORK_ID
from .session import FomoSession


@dataclass(slots=True)
class ThesisItem:
    """One feed entry: a trade, optionally carrying a written thesis.

    `type` is one of thesis | swap_buy | swap_sell. Only `thesis` rows carry
    author text; the swap rows are still recorded because they are the base rate
    against which thesis rows have to be judged.
    """

    item_id: str
    item_type: str
    trade_id: str
    created_at: str
    user_id: str
    handle: str
    display_name: str
    verified: bool
    is_dev: bool
    token_address: str
    network_id: int
    ticker: str
    usd_value: float
    unrealized_pnl_pct: float
    realized_pnl_pct: float
    author_equity: float
    likes: int
    text: str
    links: list[str] = field(default_factory=list)

    @property
    def is_thesis(self) -> bool:
        return self.item_type == "thesis"

    @property
    def is_solana(self) -> bool:
        return self.network_id == SOLANA_NETWORK_ID

    @property
    def conviction_weight(self) -> float:
        """Position size as a share of the author's total equity.

        Only the global feed populates `equity`; the per-token history does not,
        so this is 0.0 on backfilled rows and must never be a hard gate.
        """
        if self.author_equity <= 0:
            return 0.0
        return self.usd_value / self.author_equity


def _parse_item(raw: dict[str, Any]) -> ThesisItem:
    comment = raw.get("comment") or {}
    trade = raw.get("authorTrade") or {}
    segments = comment.get("shortCommentSegments") or []
    links = [s["link"] for s in segments if isinstance(s, dict) and s.get("link")]
    return ThesisItem(
        item_id=str(raw.get("id") or ""),
        item_type=str(raw.get("type") or ""),
        trade_id=str(raw.get("tradeId") or ""),
        created_at=str(raw.get("createdAt") or ""),
        user_id=str(raw.get("userId") or ""),
        handle=str(raw.get("userHandle") or ""),
        display_name=str(raw.get("displayName") or ""),
        verified=bool(raw.get("verified")),
        is_dev=bool(raw.get("isDev")),
        token_address=str(raw.get("tokenAddress") or ""),
        network_id=int(raw.get("networkId") or 0),
        ticker=str(raw.get("ticker") or ""),
        usd_value=float(trade.get("usdValue") or 0.0),
        unrealized_pnl_pct=float(trade.get("percentageUnrealizedPnl") or 0.0),
        realized_pnl_pct=float(trade.get("percentageRealizedPnl") or 0.0),
        author_equity=float(raw.get("equity") or 0.0),
        likes=int(comment.get("numLikes") or 0),
        text=str(comment.get("comment") or ""),
        links=links,
    )


@dataclass(slots=True)
class LeaderboardTrader:
    user_id: str
    handle: str
    display_name: str
    solana_address: str
    evm_address: str
    pnl: float
    num_trades: int
    total_volume: float
    followers: int
    total_holdings: int
    top_holdings: list[dict[str, Any]] = field(default_factory=list)


def _parse_trader(raw: dict[str, Any], window: str) -> LeaderboardTrader:
    pnl_key = {"24h": "pnl24h", "7d": "pnl7d", "30d": "pnl30d", "all": "pnlAll"}.get(
        window, "pnl24h"
    )
    pnl = raw.get(pnl_key)
    if pnl is None:  # windows do not all use the same field name
        pnl = next(
            (raw[k] for k in ("pnl24h", "pnl7d", "pnl30d", "pnlAll") if raw.get(k)), 0.0
        )
    return LeaderboardTrader(
        user_id=str(raw.get("id") or ""),
        handle=str(raw.get("userHandle") or ""),
        display_name=str(raw.get("displayName") or ""),
        solana_address=str(raw.get("address") or ""),
        evm_address=str(raw.get("evmAddress") or ""),
        pnl=float(pnl or 0.0),
        num_trades=int(raw.get("numTrades") or 0),
        total_volume=float(raw.get("totalVolume") or 0.0),
        followers=int(raw.get("followers") or 0),
        total_holdings=int(raw.get("totalHoldings") or 0),
        top_holdings=list(raw.get("topHoldings") or []),
    )


class FomoAPI:
    def __init__(self, session: FomoSession) -> None:
        self.s = session

    async def trading_activity(self, threshold: float = 1000.0) -> list[ThesisItem]:
        """The global firehose.

        Hard limits, verified: the window is **25 items and does not paginate**.
        `limit` above 25 is ignored, and `offset`/`page`/`cursor`/`beforeTime`
        all return the identical newest 25. Anything that scrolls off between
        polls is unrecoverable, which is why the caller persists every item.
        """
        ro = await self.s.get(
            "feed/tradingActivity", limit=25, threshold=int(threshold)
        )
        return [_parse_item(i) for i in (ro.get("items") or [])]

    async def token_thesis_history(
        self,
        token_address: str,
        network_id: int,
        *,
        after_ms: int,
        before_ms: int,
        limit: int = 500,
        threshold: float = 0.0,
    ) -> list[ThesisItem]:
        """Per-token thesis history. Unlike the global feed this DOES paginate
        by time and honours `limit` up to at least 500."""
        ro = await self.s.get(
            "feed/token/sortedThesis",
            tokenAddress=token_address,
            networkId=network_id,
            afterTime=after_ms,
            beforeTime=before_ms,
            limit=limit,
            threshold=int(threshold),
        )
        return [_parse_item(i) for i in (ro.get("items") or [])]

    async def leaderboard(self, window: str = "24h") -> list[LeaderboardTrader]:
        """Top 150 traders by realized PnL, with wallet addresses.

        This is the free source of smart-money wallets that PRD Phase 2 was
        blocked on. Note it is a LAGGING list: its top-consensus holdings are
        already-won positions, so use it to weight candidates, never to find
        them.
        """
        ro = await self.s.get(f"v2/leaderboard/{window}")
        return [_parse_trader(t, window) for t in (ro.get("leaderboard") or [])]

    async def trending_tokens(self) -> list[dict[str, Any]]:
        """fomo's own trending screener.

        Kept for context only: the fields (change24/holders/liquidity/marketCap/
        volume24) are ordinary and DexScreener already gives us equivalents.
        """
        ro = await self.s.post("proxy/trendingTokens", body={})
        return list(ro.get("items") or ro or [])

    async def token_warnings(self, keys: list[str]) -> Any:
        """fomo's rug checks, keyed `<address>:<networkId>`."""
        return await self.s.post("proxy/tokenWarnings", body=keys)


def dumps_links(links: list[str]) -> str:
    return json.dumps(links, separators=(",", ":"))
