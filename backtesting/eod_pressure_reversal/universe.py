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


# ---------------------------------------------------------------------------
# Extended universe — the spec's ACTUAL screen, not just the index
# ---------------------------------------------------------------------------
#
# The spec (§2) asks for NYSE/NASDAQ common stocks with price >= $10, market cap
# >= $2B and ADV20 >= $50M. The S&P 500 is a convenient stand-in but a strictly
# smaller set, and it excludes most of the 2023-2026 AI supply chain by
# construction: MP, UEC, LEU, CCJ, OKLO, BWXT, TLN, NBIS, CRDO and ALAB all clear
# the spec's bar and none of them are index members. Testing only the index means
# never seeing those trades.
#
# THE BIAS THIS INTRODUCES, STATED PLAINLY. Index membership is point-in-time
# (start/end dates per ticker, delisted names retained). The extended list is NOT:
# it is *today's* listed companies above $2B, so it contains only survivors and it
# knows which small companies later became large. Two things keep that honest:
#   1. Eligibility on any given date still requires price >= $10 AND ADV20 >= $50M,
#      both computed from that date's trailing bars. A company can only trade on
#      days it was genuinely liquid, which is most of what "was it big yet" means.
#   2. Every candidate carries a `segment` label, so results are reported split
#      SP500_PIT vs EXTENDED rather than blended. If the extended slice looks much
#      better, suspect the bias rather than the strategy.

_NASDAQ_SCREENER = "https://api.nasdaq.com/api/screener/stocks"
_SCREENER_UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


def _screener_num(value) -> float:
    """Pure: '$1,234.56' -> 1234.56, junk -> 0.0."""
    if not value:
        return 0.0
    try:
        return float(str(value).replace("$", "").replace(",", "").replace("%", ""))
    except ValueError:
        return 0.0


def parse_screener(rows: list[dict], min_cap: float = 2e9,
                   min_price: float = 10.0) -> pd.DataFrame:
    """Pure: Nasdaq screener rows -> tickers clearing the spec's size/price bar."""
    import re

    out = []
    for r in rows:
        sym = str(r.get("symbol", "")).strip().upper()
        # Common shares only (spec §2). A dot suffix is a share class (BRK.B) and is
        # kept as a dash for Yahoo; anything longer is a warrant/unit/right (ABC.WS,
        # ABC.U), and single-letter W/U/R/P suffixes are those same instruments.
        m = re.fullmatch(r"([A-Z]{1,5})(?:[.\-]([A-Z]))?", sym)
        if not m or (m.group(2) and m.group(2) in {"W", "U", "R", "P"}):
            continue
        cap, px = _screener_num(r.get("marketCap")), _screener_num(r.get("lastsale"))
        if cap >= min_cap and px >= min_price:
            out.append({"ticker": sym.replace(".", "-"), "market_cap": cap, "price": px})
    return pd.DataFrame(out).drop_duplicates("ticker")


def fetch_extended(use_cache: bool = True) -> pd.DataFrame:
    """Currently-listed NYSE/NASDAQ/AMEX names above the spec's size and price bar."""
    path = _cache_path("extended_universe.csv")
    if use_cache and os.path.exists(path):
        return pd.read_csv(path)
    rows: list[dict] = []
    for ex in ("NASDAQ", "NYSE", "AMEX"):
        try:
            r = requests.get(_NASDAQ_SCREENER, params={"tableonly": "true", "limit": 10000,
                                                       "exchange": ex},
                             headers=_SCREENER_UA, timeout=60)
            data = r.json().get("data", {})
            rows += (data.get("table", {}) or {}).get("rows", []) or data.get("rows", []) or []
        except Exception:
            continue
    df = parse_screener(rows)
    df.to_csv(path, index=False)
    return df


def build_universe(membership: pd.DataFrame, extended: Optional[pd.DataFrame],
                   start: str, end: str) -> pd.DataFrame:
    """Pure: one table of [ticker, segment, start, end] for the whole study.

    S&P 500 names keep their true membership window. Extended names get an open
    window (NaT/NaT) because their eligibility is decided per-date by the liquidity
    screen instead — see the bias note above.
    """
    sp = membership[
        (membership["start"] <= pd.Timestamp(end))
        & (membership["end"].isna() | (membership["end"] >= pd.Timestamp(start)))
    ][["ticker", "start", "end"]].copy()
    sp["segment"] = "SP500_PIT"

    if extended is None or extended.empty:
        return sp.reset_index(drop=True)

    extra = extended.loc[~extended["ticker"].isin(set(sp["ticker"])), ["ticker"]].copy()
    extra["start"] = pd.NaT
    extra["end"] = pd.NaT
    extra["segment"] = "EXTENDED"
    return pd.concat([sp, extra], ignore_index=True)
