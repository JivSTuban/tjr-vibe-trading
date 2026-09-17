"""PumpPortal websocket client: the discovery backbone.

Only the two free methods are used by default. `subscribeTokenTrade` and
`subscribeAccountTrade` are metered at 0.01 SOL per 10,000 messages AND require
a PumpPortal API key linked to a wallet funded with at least 0.02 SOL, so they
are opt-in and never enabled implicitly. The radar reconstructs early flow from
DexScreener instead, which is free.

Upstream rule, quoted from the docs and enforced here by design: "PLEASE ONLY
USE ONE WEBSOCKET CONNECTION AT A TIME". Clients that open many connections get
timed out for an hour, so this class is a single long-lived connection that
multiplexes every subscription, and reconnects with backoff rather than opening
a second socket.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import websockets

from ..config import PUMPPORTAL_WS_URL
from ..models import LaunchEvent, TradeEvent, utcnow

log = logging.getLogger(__name__)

# Backoff ceiling is deliberately high: the documented penalty for hammering
# reconnects is an hour-long ban, so backing off too slowly is far more
# expensive than reconnecting a few seconds later than we could have.
_BACKOFF_START = 1.0
_BACKOFF_MAX = 60.0


def parse_launch(msg: dict[str, Any]) -> LaunchEvent | None:
    """Convert a wire `create` message into a LaunchEvent.

    Returns None for anything that is not a creation (acks, trades, migrations)
    so the caller can keep one stream handler.
    """
    if msg.get("txType") != "create":
        return None
    mint = msg.get("mint")
    if not mint:
        return None
    return LaunchEvent(
        mint=str(mint),
        name=str(msg.get("name") or ""),
        symbol=str(msg.get("symbol") or ""),
        creator=str(msg.get("traderPublicKey") or ""),
        signature=str(msg.get("signature") or ""),
        uri=str(msg.get("uri") or ""),
        pool=str(msg.get("pool") or ""),
        initial_buy=float(msg.get("initialBuy") or 0.0),
        sol_amount=float(msg.get("solAmount") or 0.0),
        market_cap_sol=float(msg.get("marketCapSol") or 0.0),
        v_sol_in_curve=float(msg.get("vSolInBondingCurve") or 0.0),
        v_tokens_in_curve=float(msg.get("vTokensInBondingCurve") or 0.0),
        is_mayhem_mode=bool(msg.get("is_mayhem_mode") or False),
        seen_at=utcnow(),
        raw=msg,
    )


def parse_trade(msg: dict[str, Any]) -> TradeEvent | None:
    """Convert a wire buy/sell message into a TradeEvent.

    Only reachable when the metered trade stream is explicitly enabled.
    """
    tx = msg.get("txType")
    if tx not in ("buy", "sell"):
        return None
    mint = msg.get("mint")
    if not mint:
        return None
    return TradeEvent(
        mint=str(mint),
        trader=str(msg.get("traderPublicKey") or ""),
        is_buy=tx == "buy",
        sol_amount=float(msg.get("solAmount") or 0.0),
        token_amount=float(msg.get("tokenAmount") or 0.0),
        market_cap_sol=float(msg.get("marketCapSol") or 0.0),
        signature=str(msg.get("signature") or ""),
        seen_at=utcnow(),
    )


class PumpPortalStream:
    """One connection, many subscriptions, automatic resubscribe on reconnect."""

    def __init__(
        self,
        api_key: str = "",
        *,
        enable_trade_stream: bool = False,
        url: str = PUMPPORTAL_WS_URL,
    ) -> None:
        self.api_key = api_key
        self.enable_trade_stream = enable_trade_stream and bool(api_key)
        self._base_url = url
        self._ws: Any = None
        self._tracked_mints: set[str] = set()
        self._connected = asyncio.Event()

    @property
    def url(self) -> str:
        return f"{self._base_url}?api-key={self.api_key}" if self.api_key else self._base_url

    async def _send(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            return
        with contextlib.suppress(Exception):
            await self._ws.send(json.dumps(payload))

    async def _resubscribe(self) -> None:
        """Re-establish every subscription after a reconnect.

        The server holds subscription state per connection, so a dropped socket
        silently stops delivering tracked-token trades unless we replay them.
        """
        await self._send({"method": "subscribeNewToken"})
        await self._send({"method": "subscribeMigration"})
        if self.enable_trade_stream and self._tracked_mints:
            await self._send(
                {"method": "subscribeTokenTrade", "keys": sorted(self._tracked_mints)}
            )

    async def track_token(self, mint: str) -> None:
        """Start receiving trades for one mint, if the metered stream is on.

        A no-op on the free path. Callers must not assume trade events arrive.
        """
        if not self.enable_trade_stream or mint in self._tracked_mints:
            return
        self._tracked_mints.add(mint)
        await self._send({"method": "subscribeTokenTrade", "keys": [mint]})

    async def untrack_token(self, mint: str) -> None:
        if mint not in self._tracked_mints:
            return
        self._tracked_mints.discard(mint)
        await self._send({"method": "unsubscribeTokenTrade", "keys": [mint]})

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Yield raw wire messages forever, reconnecting with backoff.

        Raw dicts rather than parsed objects so one loop can fan out creations,
        migrations, and trades without three separate sockets.
        """
        backoff = _BACKOFF_START
        while True:
            try:
                async with websockets.connect(
                    self.url, ping_interval=20, ping_timeout=20, max_queue=1024
                ) as ws:
                    self._ws = ws
                    self._connected.set()
                    await self._resubscribe()
                    log.info("pumpportal connected (trade_stream=%s)", self.enable_trade_stream)
                    backoff = _BACKOFF_START
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except (ValueError, TypeError):
                            continue
                        if isinstance(msg, dict):
                            yield msg
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - any socket fault means reconnect
                log.warning("pumpportal disconnected (%s); retry in %.0fs", exc, backoff)
            finally:
                self._ws = None
                self._connected.clear()
            await asyncio.sleep(backoff)
            backoff = min(_BACKOFF_MAX, backoff * 2)
