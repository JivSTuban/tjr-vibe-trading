"""Point-in-time SEC Form-4 open-market-purchase panel, sourced from openinsider's historical screener.

openinsider has already parsed EDGAR Form-4s into a queryable table; the screener serves a HISTORICAL
date-ranged panel when you pass ``fd=-1`` + ``fdr=MM/DD/YYYY - MM/DD/YYYY`` and ``xp=1`` (purchases).
Verified 2026-08-06: the ``fdr`` filter is honored (100% in-window). We page one calendar month at a
time and cache the raw transactions; clustering (>=2 distinct insiders within a window) is done here,
NOT via the site's ``grp=1`` (which returns an empty table from this env).

Network is touched ONLY by ``fetch_panel`` (run-path). ``load_panel`` reads the cache offline.
The panel is point-in-time by construction: each row's ``filing`` date is the public-disclosure date,
so an entry at t+1 after ``filing`` is genuinely tradeable (no look-ahead).
"""
from __future__ import annotations

import os
import re
import time
from collections import defaultdict

import pandas as pd
import requests

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")
_UA = {"User-Agent": "stock-scan insider-backtest research jivtuban14@gmail.com"}
_CSUITE = re.compile(r"\b(CEO|CFO|COO|Pres|Chief|COB|Chairman)\b", re.I)
_ROW = re.compile(r"<tr[^>]*>[\s\S]*?</tr>", re.I)
_TD = re.compile(r"<td[^>]*>[\s\S]*?</td>", re.I)
_HREF = re.compile(r"""href=['"]/([A-Z][A-Z.]{0,5})['"]""")
_TAG = re.compile(r"<[^>]+>")


def _num(s: str) -> float:
    try:
        return float(re.sub(r"[$,+%\s]", "", str(s)))
    except ValueError:
        return float("nan")


def parse_rows(html: str) -> list[dict]:
    """Parse openinsider screener HTML -> individual open-market P-purchase transactions.

    Anchors every field on the clean ``P - Purchase`` cell to survive the tooltip-attribute junk that
    corrupts the ticker cell; the ticker itself is read from the row ``href`` (reliable).
    """
    out = []
    for r in _ROW.findall(html):
        m = _HREF.search(r)
        if not m:
            continue
        tick = m.group(1)
        cells = [_TAG.sub(" ", c).replace("&nbsp;", " ").replace("|", " ").strip()
                 for c in _TD.findall(r)]
        cells = [re.sub(r"\s+", " ", c) for c in cells]
        tt = next((i for i, c in enumerate(cells) if re.match(r"^[A-Z] - ", c)), -1)
        if tt < 4 or not cells[tt].startswith("P - "):        # open-market PURCHASE only
            continue
        if len(cells) < tt + 6:
            continue
        out.append({
            "ticker": tick,
            "filing": cells[1][:10],
            "company": cells[tt - 3][:40],
            "insider": cells[tt - 2][:40],
            "title": cells[tt - 1][:40],
            "csuite": bool(_CSUITE.search(cells[tt - 1])),
            "price": _num(cells[tt + 1]),
            "value": _num(cells[tt + 5]),
        })
    return out


def _month_windows(start: str, end: str) -> list[tuple[str, str]]:
    """Inclusive month windows [(MM/DD/YYYY, MM/DD/YYYY), ...] spanning start..end (YYYY-MM)."""
    months = pd.period_range(start=start, end=end, freq="M")
    wins = []
    for p in months:
        a, b = p.start_time, p.end_time
        wins.append((a.strftime("%m/%d/%Y"), b.strftime("%m/%d/%Y")))
    return wins


def fetch_panel(start: str = "2024-01", end: str = "2024-12", min_value: int = 25,
                use_cache: bool = True) -> pd.DataFrame:
    """Fetch the monthly-paged P-purchase panel and cache it to one CSV. ``min_value`` in $thousands
    is openinsider's ``vl`` (drops trivially small buys). Returns the full transaction DataFrame."""
    os.makedirs(_CACHE, exist_ok=True)
    cache = os.path.join(_CACHE, f"panel_{start}_{end}.csv")
    if use_cache and os.path.exists(cache):
        return pd.read_csv(cache, dtype={"filing": str})
    rows: list[dict] = []
    for lo, hi in _month_windows(start, end):
        fdr = requests.utils.quote(f"{lo} - {hi}")
        url = (f"http://openinsider.com/screener?s=&o=&pl=1&ph=&fd=-1&fdr={fdr}"
               f"&td=0&xp=1&vl={min_value}&sic1=-1&sicl=100&sich=9999&grp=0&cnt=1000&page=1")
        for attempt in range(3):
            try:
                resp = requests.get(url, headers=_UA, timeout=60)   # big high-volume months are slow
                resp.raise_for_status()
                batch = parse_rows(resp.text)
                rows.extend(batch)
                print(f"  {lo}..{hi}: {len(batch)} P-buys")
                break
            except Exception as e:  # noqa: BLE001
                print(f"  {lo}..{hi}: retry {attempt} ({str(e)[:50]})")
                time.sleep(1.5)
        time.sleep(1.0)
    df = pd.DataFrame(rows)
    if use_cache and not df.empty:
        df.to_csv(cache, index=False)
    return df


def load_panel(start: str = "2024-01", end: str = "2024-12") -> pd.DataFrame:
    return pd.read_csv(os.path.join(_CACHE, f"panel_{start}_{end}.csv"), dtype={"filing": str})


def build_cluster_events(txns: pd.DataFrame, within_days: int = 7,
                         min_buyers: int = 2) -> list[dict]:
    """Collapse individual buys into CLUSTER events per ticker.

    A cluster = a run of buys where each is within ``within_days`` of the prior; it becomes an event
    only if it contains ``>= min_buyers`` DISTINCT insiders. The event date is the cluster's LAST
    filing date (when the cluster becomes publicly knowable — conservative for tradeability).
    Returns dicts: ticker, date (Timestamp), n_buyers, n_txns, avg_price, total_value, csuite.
    """
    events = []
    for ticker, grp in txns.groupby("ticker"):
        g = grp.copy()
        g["fdate"] = pd.to_datetime(g["filing"], errors="coerce")
        g = g.dropna(subset=["fdate"]).sort_values("fdate")
        if g.empty:
            continue
        cluster: list = []
        last = None
        for row in g.itertuples():
            if last is not None and (row.fdate - last).days > within_days:
                _emit(events, ticker, cluster, min_buyers)
                cluster = []
            cluster.append(row)
            last = row.fdate
        _emit(events, ticker, cluster, min_buyers)
    events.sort(key=lambda e: e["date"])
    return events


def _emit(events: list, ticker: str, cluster: list, min_buyers: int) -> None:
    if not cluster:
        return
    insiders = {c.insider for c in cluster}
    if len(insiders) < min_buyers:
        return
    prices = [c.price for c in cluster if c.price == c.price]        # drop NaN
    vals = [c.value for c in cluster if c.value == c.value]
    events.append({
        "ticker": ticker,
        "date": max(c.fdate for c in cluster),
        "n_buyers": len(insiders),
        "n_txns": len(cluster),
        "avg_price": (sum(prices) / len(prices)) if prices else float("nan"),
        "total_value": sum(vals),
        "csuite": any(c.csuite for c in cluster),
    })
