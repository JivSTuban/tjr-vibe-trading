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
