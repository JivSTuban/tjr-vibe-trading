"""Parser tests against captured wire payloads."""

from __future__ import annotations

from memecoin_radar.sources.dexscreener import parse_pair, pick_primary
from memecoin_radar.sources.metadata import extract_cid, parse_metadata
from memecoin_radar.sources.pumpportal import parse_launch, parse_trade

from .conftest import REAL_CREATE_MSG, REAL_DEX_PAIR, REAL_METADATA_DOC


def test_parse_launch_maps_every_field():
    ev = parse_launch(REAL_CREATE_MSG)
    assert ev is not None
    assert ev.mint == "Eiof3BofrqjwJq4EVB9SXMBwRazdYvakfFiFJVGkpump"
    assert ev.symbol == "Coke"
    # The creator is `traderPublicKey` on the wire, not `creator`.
    assert ev.creator == "E5TJMt7Prc5kjyhna7W67bZmjq6TzGZRm3JTdbmRnkic"
    assert ev.market_cap_sol > 0
    assert ev.v_sol_in_curve > 0
    assert ev.is_mayhem_mode is True


def test_parse_launch_ignores_non_create():
    assert parse_launch({"txType": "buy", "mint": "x"}) is None
    assert parse_launch({"message": "Successfully subscribed"}) is None


def test_creator_supply_pct_uses_fixed_supply():
    ev = parse_launch(REAL_CREATE_MSG)
    # 7,018,806 of 1B is ~0.7%.
    assert 0.6 < ev.creator_supply_pct < 0.8


def test_parse_trade():
    trade = parse_trade(
        {"txType": "buy", "mint": "m", "traderPublicKey": "w", "solAmount": 1.5,
         "tokenAmount": 100.0, "marketCapSol": 30.0, "signature": "s"}
    )
    assert trade is not None and trade.is_buy and trade.sol_amount == 1.5
    assert parse_trade({"txType": "create", "mint": "m"}) is None


def test_parse_pair_survives_missing_liquidity():
    """A pre-migration pair has no `liquidity` key at all."""
    state = parse_pair(REAL_DEX_PAIR)
    assert state.buys_m5 == 51
    assert state.sells_m5 == 50
    assert state.volume_m5_usd == 377.4
    assert state.market_cap_usd == 131.95
    assert state.liquidity_usd == 0.0  # absent, not an error
    assert state.dex_id == "pumpfun"


def test_buy_ratio_defaults_to_neutral_with_no_txns():
    state = parse_pair({"baseToken": {"address": "m"}})
    assert state.buy_ratio == 0.5


def test_pick_primary_prefers_highest_m5_volume():
    low = {"volume": {"m5": 10.0}, "dexId": "pumpfun"}
    high = {"volume": {"m5": 900.0}, "dexId": "raydium"}
    assert pick_primary([low, high])["dexId"] == "raydium"
    assert pick_primary([]) is None


def test_extract_cid_handles_both_uri_forms():
    assert extract_cid("https://ipfs.io/ipfs/QmABC123") == "QmABC123"
    assert extract_cid("ipfs://QmABC123") == "QmABC123"
    assert extract_cid("") == ""


def test_parse_metadata_marks_fetched():
    meta = parse_metadata(REAL_METADATA_DOC)
    assert meta.fetched is True
    assert meta.description.startswith("Coke")
    assert meta.twitter == ""  # absent in this document


# --------------------------------------------------- dexscreener batch rescue


class _FakeResponse:
    """Minimal stand-in for an httpx response."""

    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _TruncatingClient:
    """Reproduces the real batch endpoint's truncation.

    Verified live 2026-09-17 against 14 tracked tokens: asked individually, 11
    resolved; asked in one batch, only 8. The endpoint returns ONE flat `pairs`
    array for every requested address and caps its length, so the tail of a
    batch silently disappears. Callers read an unresolved mint as "no market
    data" and fail closed, which makes a truncated batch indistinguishable from
    a dead token.
    """

    def __init__(self, known: set[str], cap: int):
        self.known = known
        self.cap = cap
        self.requests: list[list[str]] = []

    async def get(self, url: str):
        addrs = url.rsplit("/", 1)[-1].split(",")
        self.requests.append(addrs)
        pairs = [
            {
                "baseToken": {"address": a},
                "priceUsd": "1.0",
                "liquidity": {"usd": 50_000.0},
                "volume": {"m5": 100.0, "h1": 5_000.0},
                "txns": {"m5": {"buys": 5, "sells": 2}},
                "marketCap": 250_000.0,
                "dexId": "raydium",
            }
            for a in addrs
            if a in self.known
        ]
        return _FakeResponse({"pairs": pairs[: self.cap]})


async def _states(client, mints):
    from memecoin_radar.sources.dexscreener import DexScreenerClient

    dex = DexScreenerClient(client=client)
    async with dex:
        return await dex.token_states(mints)


def test_batch_truncation_is_rescued_by_individual_retries():
    import asyncio

    mints = [f"mint{i}" for i in range(6)]
    # Every mint is real, but the endpoint only ever returns the first two.
    client = _TruncatingClient(known=set(mints), cap=2)
    got = asyncio.run(_states(client, mints))
    assert set(got) == set(mints), (
        f"truncated batch left {sorted(set(mints) - set(got))} unresolved; "
        "the rescue pass should have recovered them"
    )
    # One batch call, then one retry per missing mint — not a retry per mint.
    assert len(client.requests[0]) == 6
    assert all(len(r) == 1 for r in client.requests[1:])


def test_genuinely_absent_mints_are_reported_absent():
    """A token with no pair must stay unresolved, so callers still fail closed."""
    import asyncio

    client = _TruncatingClient(known={"mint0"}, cap=30)
    got = asyncio.run(_states(client, ["mint0", "nopair1", "nopair2"]))
    assert set(got) == {"mint0"}


def test_rescue_is_capped():
    """A batch of brand-new launches has no pairs at all; retrying all 30 every
    tick would triple request volume for no information."""
    import asyncio

    from memecoin_radar.sources.dexscreener import RESCUE_LIMIT

    mints = [f"mint{i}" for i in range(RESCUE_LIMIT + 8)]
    client = _TruncatingClient(known=set(), cap=0)
    asyncio.run(_states(client, mints))
    retries = [r for r in client.requests if len(r) == 1]
    assert len(retries) == RESCUE_LIMIT
