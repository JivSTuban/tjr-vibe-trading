"""Shared fixtures built from payloads captured live on 2026-09-17.

Using real captured wire messages rather than invented ones is the point: a
hand-written fixture would have validated the parser against my assumptions
instead of against what PumpPortal and DexScreener actually send.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from memecoin_radar.models import Candidate, MarketSnapshot, TokenMetadata, utcnow
from memecoin_radar.sources.pumpportal import parse_launch

# Captured verbatim from wss://pumpportal.fun/api/data on 2026-09-17.
REAL_CREATE_MSG = {
    "signature": "472WSu6XfNiMq7YapGEyuRg4KdmTDVKeGyTFtuThNsd1xbTrVm1BMyYrT6q2D5tQ5Qf7RvcetF8WHUqHxDcF32nY",
    "mint": "Eiof3BofrqjwJq4EVB9SXMBwRazdYvakfFiFJVGkpump",
    "traderPublicKey": "E5TJMt7Prc5kjyhna7W67bZmjq6TzGZRm3JTdbmRnkic",
    "txType": "create",
    "initialBuy": 7018806.171954,
    "solAmount": 0.197530863,
    "bondingCurveKey": "9UGmbiB4koXPkso4HkCs7rCFaauBqEVkMepRU6sNrfK",
    "vTokensInBondingCurve": 1065981193.828046,
    "vSolInBondingCurve": 30.197530862999997,
    "marketCapSol": 28.32838987952275,
    "name": "Coke coin",
    "symbol": "Coke",
    "uri": "https://ipfs.io/ipfs/bafkreiaoim7hiq54iisbb42wyqk3x33nzjk5agubn4u374mtzomonhaely",
    "is_mayhem_mode": True,
    "pool": "pump",
}

# Captured verbatim from api.dexscreener.com for the same mint, seconds old.
REAL_DEX_PAIR = {
    "chainId": "solana",
    "dexId": "pumpfun",
    "pairAddress": "9UGmbiB4koXPkso4HkCs7rCFaauBqEVkMepRU6sNrfK",
    "baseToken": {"address": "Eiof3BofrqjwJq4EVB9SXMBwRazdYvakfFiFJVGkpump", "symbol": "Coke"},
    "quoteToken": {"address": "So11111111111111111111111111111111111111112", "symbol": "SOL"},
    "priceUsd": "0.0001319",
    "txns": {
        "m5": {"buys": 51, "sells": 50},
        "h1": {"buys": 51, "sells": 50},
        "h6": {"buys": 51, "sells": 50},
        "h24": {"buys": 51, "sells": 50},
    },
    "volume": {"m5": 377.4, "h1": 377.4, "h6": 377.4, "h24": 377.4},
    "marketCap": 131.95,
    "fdv": 131.95,
    "pairCreatedAt": 1789613518000,
    # Note: no "liquidity" key at all before migration, which is exactly the
    # shape the parser has to survive.
}

# Real pump.fun IPFS metadata document.
REAL_METADATA_DOC = {
    "name": "Coke coin",
    "symbol": "Coke",
    "description": "Coke \U0001fa99 ",
    "image": "https://ipfs.io/ipfs/bafybeicddwao6a7yhfzm72jspbkeumbkukfjnukuazgu2kzi64u4qqa27e",
    "showName": True,
    "createdOn": "https://pump.fun",
}


@pytest.fixture
def launch():
    ev = parse_launch(REAL_CREATE_MSG)
    assert ev is not None
    return ev


@pytest.fixture
def candidate(launch):
    return Candidate(launch=launch)


def make_snapshots(
    mint: str,
    series: list[tuple[int, float, int, int]],
    *,
    market_cap_usd: float = 120_000.0,
    liquidity_usd: float = 40_000.0,
) -> list[MarketSnapshot]:
    """Build a snapshot series from (age_s, volume_usd, buys, sells) tuples.

    Defaults describe a token with a REAL market, because since 2026-09-17 the
    upside tiers require one (`alerts._is_tradeable`). The previous defaults of
    $15k cap / $12k liquidity sat below that floor, which would have made every
    tier-reachability test fail for a reason unrelated to what it tests. Pass
    the kwargs explicitly to exercise the tradeability gate itself.
    """
    base = utcnow()
    return [
        MarketSnapshot(
            mint=mint,
            ts=base + timedelta(seconds=age),
            age_seconds=float(age),
            volume_usd=vol,
            buys=buys,
            sells=sells,
            market_cap_usd=market_cap_usd,
            liquidity_usd=liquidity_usd,
        )
        for age, vol, buys, sells in series
    ]


def fetched_metadata(description: str = "a frog on solana", **kw) -> TokenMetadata:
    return TokenMetadata(description=description, image="ipfs://x", fetched=True, **kw)
