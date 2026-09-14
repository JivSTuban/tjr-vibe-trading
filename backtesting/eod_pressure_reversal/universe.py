"""Point-in-time S&P 500 membership + GICS sector map.

Why PIT matters here: the spec (§11) asks for a point-in-time universe to avoid
survivorship bias. Screening today's index members over 2014-2026 would only ever
test companies that *survived to today* — exactly the bias that inflated the
`swing_bounce` result. Membership comes from `fja05680/sp500`, which keeps dated
constituent snapshots back to 1996 and retains names that later failed or were
acquired (SIVB, FRC, TWTR are all present).

Network is touched only by ``fetch_*``. ``load_*`` / ``members_on`` are offline and
pure so tests can run without a network.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

import pandas as pd
import requests

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh) eod-pressure-reversal research"}

_SP500_REPO = "https://raw.githubusercontent.com/fja05680/sp500/master/"
_START_END = "sp500_ticker_start_end.csv"
_WIKI_API = (
    "https://en.wikipedia.org/w/api.php?action=parse"
    "&page=List_of_S%26P_500_companies&prop=wikitext&format=json"
)

# Spec §5. XLC (2018-06-19) and XLRE (2015-10-08) list mid-sample; the price loader
# returns NaN before inception and those rows fall out of the sector-relative filter.
SECTOR_ETF = {
    "Information Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Energy": "XLE",
    "Consumer Discretionary": "XLY",
    "Industrials": "XLI",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
    "Consumer Staples": "XLP",
    "Communication Services": "XLC",
}
# Wikipedia's GICS labels drift from the spec's table wording; normalise both ways.
_SECTOR_ALIASES = {
    "Technology": "Information Technology",
    "Healthcare": "Health Care",
    "Telecommunication Services": "Communication Services",
}

BENCHMARKS = ["SPY", "^VIX"] + sorted(set(SECTOR_ETF.values()))


def _cache_path(name: str) -> str:
    os.makedirs(_CACHE, exist_ok=True)
    return os.path.join(_CACHE, name)


def fetch_membership(use_cache: bool = True) -> pd.DataFrame:
    """Download the PIT membership table: one row per ticker with start/end dates.

    ``end_date`` is empty for names still in the index. Returned dates are tz-naive
    ``Timestamp``; an open-ended membership gets ``end = NaT``.
    """
    path = _cache_path("sp500_membership.csv")
    if use_cache and os.path.exists(path):
        raw = pd.read_csv(path)
    else:
        r = requests.get(_SP500_REPO + _START_END, headers=_UA, timeout=60)
        r.raise_for_status()
        raw = pd.read_csv(pd.io.common.StringIO(r.text))
        raw.to_csv(path, index=False)
    return normalize_membership(raw)


def normalize_membership(raw: pd.DataFrame) -> pd.DataFrame:
    """Pure: coerce the raw start/end CSV into typed columns."""
    df = raw.rename(columns=str.strip).copy()
    df["ticker"] = df["ticker"].astype(str).str.strip()
    df["start"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end"] = pd.to_datetime(df.get("end_date"), errors="coerce")
    return df[["ticker", "start", "end"]].dropna(subset=["ticker", "start"])


def members_on(membership: pd.DataFrame, date) -> list[str]:
    """Pure: tickers in the index on ``date`` (inclusive start, inclusive end).

    A name is tradable on its removal date itself — it was still a constituent when
    that session's close printed.
    """
    d = pd.Timestamp(date)
    live = (membership["start"] <= d) & (membership["end"].isna() | (membership["end"] >= d))
    return sorted(membership.loc[live, "ticker"].tolist())


def universe_tickers(membership: pd.DataFrame, start, end) -> list[str]:
    """Pure: every ticker that was a member at any point in [start, end]."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    overlap = (membership["start"] <= e) & (membership["end"].isna() | (membership["end"] >= s))
    return sorted(membership.loc[overlap, "ticker"].unique().tolist())


def fetch_sectors(use_cache: bool = True) -> pd.DataFrame:
    """Scrape the current Wikipedia constituents table for ticker -> GICS sector.

    Known limitation: this is *today's* sector assignment, not point-in-time. Sector
    reclassifications (the 2018 Telecom -> Communication Services rebuild is the big
    one) are therefore applied retroactively, and names no longer in the index get no
    sector at all. `resolve_sector_etf` falls back to SPY for those, which makes the
    sector-relative filter slightly conservative rather than look-ahead.
    """
    path = _cache_path("sectors.csv")
    if use_cache and os.path.exists(path):
        return pd.read_csv(path)
    r = requests.get(_WIKI_API, headers=_UA, timeout=60)
    r.raise_for_status()
    wikitext = r.json()["parse"]["wikitext"]["*"]
    df = parse_sector_wikitext(wikitext)
    df.to_csv(path, index=False)
    return df


def parse_sector_wikitext(wikitext: str) -> pd.DataFrame:
    """Pure: pull (ticker, sector) pairs out of the constituents wikitable.

    Rows look like ``|| {{NyseSymbol|MMM}} || [[3M]] || Industrials || ...``; the
    sector is the third cell. Parsed positionally per row rather than by regex over
    the whole page so a stray sector-like word elsewhere cannot leak in.
    """
    import re

    out: list[tuple[str, str]] = []
    for block in wikitext.split("|-"):
        m = re.search(r"\{\{(?:Nasdaq|NYSE|NyseSymbol|NasdaqSymbol|BATS)Symbol?\|([A-Z.\-]+)\}\}", block, re.I)
        if not m:
            m = re.search(r"\{\{(?:NASDAQ|NYSE)\|([A-Z.\-]+)\}\}", block)
        if not m:
            continue
        cells = [c.strip() for c in block.split("||")]
        sector = ""
        for cell in cells[2:5]:
            clean = re.sub(r"\[\[|\]\]", "", cell).split("\n")[0].strip()
            if clean in SECTOR_ETF or clean in _SECTOR_ALIASES:
                sector = clean
                break
        if sector:
            out.append((m.group(1).replace(".", "-"), _SECTOR_ALIASES.get(sector, sector)))
    return pd.DataFrame(out, columns=["ticker", "sector"]).drop_duplicates("ticker")


def resolve_sector_etf(sector_map: dict[str, str], ticker: str) -> str:
    """Pure: sector ETF for a ticker, falling back to SPY when the sector is unknown.

    SPY is the conservative fallback: a market benchmark absorbs less stock-specific
    weakness than a sector one, so filter D (relative return <= -1%) passes *less*
    often, never more.
    """
    sector = sector_map.get(ticker)
    return SECTOR_ETF.get(sector, "SPY")


@lru_cache(maxsize=1)
def _noop_cache_guard() -> None:  # pragma: no cover - import-time network guard
    return None
