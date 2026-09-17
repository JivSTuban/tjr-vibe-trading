"""DexScreener client: free market state, and the free substitute for trade flow.

Verified live on 2026-09-17 against three mints seconds old: DexScreener indexes
pump.fun bonding-curve pairs immediately as `dexId: "pumpfun"` and returns
`txns.m5` buy/sell counts, `volume.m5` in USD, `marketCap`, and `priceUsd`.
`liquidity` is null before migration, so curve liquidity is derived from the
launch event's `vSolInBondingCurve` instead.

Two limits shape this client:
  * 300 requests/min for token and pair endpoints (no auth, no paid tier).
  * Up to 30 comma-separated addresses per request.
Batching is what makes snapshotting the entire ~34k/day firehose affordable:
24 launches/min across 8 snapshot ages is ~7 requests/min, not ~192.

Note on terms: DexScreener's API terms forbid building a product that competes
with DexScreener. A private notifier is fine; publishing this as a rival screener
would not be.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import DEXSCREENER_BASE

log = logging.getLogger(__name__)

WSOL_MINT = "So11111111111111111111111111111111111111112"
MAX_BATCH = 30
# Leave headroom under the documented 300/min so a burst of enrichment never
# trips a 429 that would delay a sub-minute alert.
REQUESTS_PER_MIN = 240


@dataclass(slots=True)
class PairState:
    """The subset of a DexScreener pair the radar actually scores."""

    mint: str
    price_usd: float = 0.0
    market_cap_usd: float = 0.0
    liquidity_usd: float = 0.0
    volume_m5_usd: float = 0.0
    volume_h1_usd: float = 0.0
    buys_m5: int = 0
    sells_m5: int = 0
    pair_created_at_ms: int = 0
    dex_id: str = ""
    boosted: bool = False

    @property
    def txns_m5(self) -> int:
        return self.buys_m5 + self.sells_m5

    @property
    def buy_ratio(self) -> float:
        """Share of 5-minute transactions that were buys, 0.5 when flat."""
        total = self.txns_m5
        return self.buys_m5 / total if total else 0.5


class RateLimiter:
    """Sliding-window limiter. Sized per provider, not shared."""

    def __init__(self, max_calls: int, per_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._calls: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                cutoff = now - self.per_seconds
                self._calls = [t for t in self._calls if t > cutoff]
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                await asyncio.sleep(max(0.05, self._calls[0] - cutoff))


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_pair(pair: dict[str, Any]) -> PairState:
    """Map one wire pair object onto PairState.

    Defensive about missing keys: a pair seconds after creation legitimately has
    no `liquidity` and no `priceChange`, and treating that as an error would
    discard exactly the earliest candidates the radar exists to find.
    """
    txns = pair.get("txns") or {}
    m5 = txns.get("m5") or {}
    volume = pair.get("volume") or {}
    liq = pair.get("liquidity") or {}
    base = pair.get("baseToken") or {}
    return PairState(
        mint=str(base.get("address") or ""),
        price_usd=_f(pair.get("priceUsd")),
        market_cap_usd=_f(pair.get("marketCap") or pair.get("fdv")),
        liquidity_usd=_f(liq.get("usd")),
        volume_m5_usd=_f(volume.get("m5")),
        volume_h1_usd=_f(volume.get("h1")),
        buys_m5=int(_f(m5.get("buys"))),
        sells_m5=int(_f(m5.get("sells"))),
        pair_created_at_ms=int(_f(pair.get("pairCreatedAt"))),
        dex_id=str(pair.get("dexId") or ""),
    )


def pick_primary(pairs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Choose the pair that represents the token.

    Highest 5-minute volume wins, because a migrated token briefly has both a
    bonding-curve pair and an AMM pair, and the active one carries the flow the
    acceleration features need.
    """
    if not pairs:
        return None
    return max(pairs, key=lambda p: _f((p.get("volume") or {}).get("m5")))


class DexScreenerClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None
        self._limiter = RateLimiter(REQUESTS_PER_MIN)
        self._sol_price = 0.0
        self._sol_price_at = 0.0

    async def __aenter__(self) -> DexScreenerClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                headers={"accept": "application/json"},
            )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str) -> Any:
        assert self._client is not None, "use DexScreenerClient as an async context manager"
        await self._limiter.acquire()
        try:
            resp = await self._client.get(f"{DEXSCREENER_BASE}{path}")
        except httpx.HTTPError as exc:
            log.debug("dexscreener request failed %s: %s", path, exc)
            return None
        if resp.status_code == 429:
            # Back off politely; the caller retries on the next enrichment tick
            # rather than blocking the ingest loop here.
            log.warning("dexscreener 429 on %s", path)
            return None
        if resp.status_code != 200:
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    async def token_states(self, mints: list[str]) -> dict[str, PairState]:
        """Fetch state for up to 30 mints per request, batched automatically."""
        out: dict[str, PairState] = {}
        unique = [m for m in dict.fromkeys(mints) if m]
        for i in range(0, len(unique), MAX_BATCH):
            chunk = unique[i : i + MAX_BATCH]
            data = await self._get("/latest/dex/tokens/" + ",".join(chunk))
            pairs = (data or {}).get("pairs") or []
            by_mint: dict[str, list[dict[str, Any]]] = {}
            for p in pairs:
                addr = str(((p.get("baseToken") or {}).get("address")) or "")
                if addr:
                    by_mint.setdefault(addr, []).append(p)
            for mint in chunk:
                primary = pick_primary(by_mint.get(mint, []))
                if primary is not None:
                    state = parse_pair(primary)
                    state.mint = mint
                    out[mint] = state
        return out

    async def sol_price_usd(self, max_age_s: float = 120.0) -> float:
        """SOL/USD, cached.

        Needed because PumpPortal reports market cap and curve liquidity in SOL
        while every threshold and alert is expressed in dollars.
        """
        now = time.monotonic()
        if self._sol_price and now - self._sol_price_at < max_age_s:
            return self._sol_price
        data = await self._get(f"/latest/dex/tokens/{WSOL_MINT}")
        pairs = (data or {}).get("pairs") or []
        stables = {"USDC", "USDT"}
        prices = [
            _f(p.get("priceUsd"))
            for p in pairs
            if str(((p.get("quoteToken") or {}).get("symbol")) or "").upper() in stables
            and _f(p.get("priceUsd")) > 0
        ]
        if not prices:
            # Observed live: the stablecoin filter can come back empty on a
            # single request, and returning 0 silently rendered every derived
            # dollar figure as "unknown" in the alert. Any priced WSOL pair is a
            # far better estimate than no price at all.
            prices = [_f(p.get("priceUsd")) for p in pairs if _f(p.get("priceUsd")) > 0]
        if prices:
            prices.sort()
            # Median, so one thin or stale pair cannot move the conversion rate
            # that every dollar figure in the alert depends on.
            self._sol_price = prices[len(prices) // 2]
            self._sol_price_at = now
        # On total failure the last known good price is kept rather than zeroed:
        # a slightly stale rate beats reporting a live token as having no value.
        return self._sol_price
