"""Helius RPC client for the structural rug checks, optional by design.

Free tier is 1M credits and 10 RPS, which is not enough to stream anything but
is plenty to ask a few questions about the handful of candidates that survive
the cheap gates. So this client is called on demand, never on the firehose.

What it answers, all from PRD section 3.2:
  * Is mint or freeze authority still live (can supply be inflated, can your
    tokens be frozen)?
  * How concentrated are the top holders?

Without a key the radar still runs; the rug scorer marks these components
unavailable and reports reduced coverage rather than pretending the checks passed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from .dexscreener import RateLimiter

log = logging.getLogger(__name__)

# Free tier is 10 RPS; 6 leaves room for the DAS endpoints' tighter 2 req/s.
REQUESTS_PER_SEC = 6


@dataclass(slots=True)
class TokenAuthorities:
    mint_authority: str | None = None
    freeze_authority: str | None = None
    supply: float = 0.0
    decimals: int = 0
    available: bool = False

    @property
    def mint_authority_live(self) -> bool:
        return bool(self.mint_authority)

    @property
    def freeze_authority_live(self) -> bool:
        return bool(self.freeze_authority)


@dataclass(slots=True)
class HolderConcentration:
    top10_pct: float = 0.0
    largest_pct: float = 0.0
    holder_count: int = 0
    available: bool = False


class HeliusClient:
    def __init__(self, rpc_url: str, client: httpx.AsyncClient | None = None) -> None:
        self.rpc_url = rpc_url
        self._client = client
        self._owns_client = client is None
        self._limiter = RateLimiter(REQUESTS_PER_SEC, per_seconds=1.0)

    async def __aenter__(self) -> HeliusClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0))
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _rpc(self, method: str, params: list[Any]) -> Any:
        assert self._client is not None, "use HeliusClient as an async context manager"
        await self._limiter.acquire()
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        try:
            resp = await self._client.post(self.rpc_url, json=payload)
        except httpx.HTTPError as exc:
            log.debug("helius %s failed: %s", method, exc)
            return None
        if resp.status_code != 200:
            log.debug("helius %s http %s", method, resp.status_code)
            return None
        try:
            body = resp.json()
        except ValueError:
            return None
        if isinstance(body, dict) and body.get("error"):
            log.debug("helius %s error: %s", method, body["error"])
            return None
        return (body or {}).get("result")

    async def authorities(self, mint: str) -> TokenAuthorities:
        """Read mint/freeze authority and supply via getAccountInfo jsonParsed."""
        result = await self._rpc(
            "getAccountInfo", [mint, {"encoding": "jsonParsed", "commitment": "confirmed"}]
        )
        info = (((result or {}).get("value") or {}).get("data") or {}).get("parsed") or {}
        fields = (info.get("info") or {}) if isinstance(info, dict) else {}
        if not fields:
            return TokenAuthorities()
        try:
            supply = float(fields.get("supply") or 0.0)
            decimals = int(fields.get("decimals") or 0)
        except (TypeError, ValueError):
            supply, decimals = 0.0, 0
        return TokenAuthorities(
            mint_authority=fields.get("mintAuthority") or None,
            freeze_authority=fields.get("freezeAuthority") or None,
            supply=supply / (10**decimals) if decimals else supply,
            decimals=decimals,
            available=True,
        )

    async def holder_concentration(self, mint: str) -> HolderConcentration:
        """Top-holder concentration from getTokenLargestAccounts.

        Returns the top-20 accounts only, so `holder_count` is not a true holder
        count and is left at zero rather than reported as one. The percentages
        are what the rug score needs, and they are exact.
        """
        result = await self._rpc("getTokenLargestAccounts", [mint, {"commitment": "confirmed"}])
        accounts = (result or {}).get("value") or []
        if not accounts:
            return HolderConcentration()
        amounts: list[float] = []
        for acct in accounts:
            try:
                amounts.append(float((acct or {}).get("uiAmount") or 0.0))
            except (TypeError, ValueError):
                continue
        if not amounts:
            return HolderConcentration()

        supply_info = await self._rpc("getTokenSupply", [mint, {"commitment": "confirmed"}])
        try:
            total = float(((supply_info or {}).get("value") or {}).get("uiAmount") or 0.0)
        except (TypeError, ValueError):
            total = 0.0
        if total <= 0:
            return HolderConcentration()

        amounts.sort(reverse=True)
        top10 = sum(amounts[:10]) / total * 100.0
        return HolderConcentration(
            top10_pct=min(100.0, top10),
            largest_pct=min(100.0, amounts[0] / total * 100.0),
            holder_count=0,
            available=True,
        )
