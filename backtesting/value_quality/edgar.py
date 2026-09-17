"""SEC EDGAR companyfacts — point-in-time fundamentals for the value+quality backtest.

Network is touched ONLY by fetch_* (run-path). pit_finyears is pure and is the
tested surface. Each XBRL fact carries its `filed` date, so a decision at `asof`
uses only facts with `filed <= asof` — genuinely point-in-time. SEC requires a
descriptive User-Agent ("name email"); keep requests <= 10/s.
"""
from __future__ import annotations
import json, os, time
from typing import Optional
import pandas as pd
import requests

from backtesting.value_quality.fundamentals import FinYear

_CACHE = os.path.join(os.path.dirname(__file__), ".cache")
_UA = {"User-Agent": "vibe-trading research jivtuban14@gmail.com"}

# tag -> list of acceptable XBRL tags in priority order
_TAGS = {
    "net_income": ["NetIncomeLoss"],
    "total_assets": ["Assets"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "SalesRevenueNet"],
    "gross_profit": ["GrossProfit"],
    "cur_assets": ["AssetsCurrent"],
    "cur_liab": ["LiabilitiesCurrent"],
    "lt_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "shares": ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"],
    "book_equity": ["StockholdersEquity"],
    "_op_income": ["OperatingIncomeLoss"],
    "_dda": ["DepreciationDepletionAndAmortization",
             "DepreciationAmortizationAndAccretionNet"],
    "_debt_cur": ["DebtCurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalents"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}


def fetch_company_facts(cik: str, use_cache: bool = True) -> Optional[dict]:
    os.makedirs(os.path.join(_CACHE, "facts"), exist_ok=True)
    p = os.path.join(_CACHE, "facts", f"CIK{int(cik):010d}.json")
    if use_cache and os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
    for i in range(4):
        try:
            r = requests.get(url, headers=_UA, timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
            with open(p, "w") as f:
                json.dump(data, f)
            time.sleep(0.15)
            return data
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def load_ticker_cik_map() -> pd.DataFrame:
    p = os.path.join(_CACHE, "company_tickers.json")
    with open(p) as f:
        d = json.load(f)
    rows = [(v["ticker"], int(v["cik_str"]), v["title"]) for v in d.values()]
    return pd.DataFrame(rows, columns=["ticker", "cik", "title"])


def _annual_points(gaap: dict, tag_list, asof):
    """Return {fiscal_end: val} using the latest filed<=asof 10-K/FY point per end."""
    out = {}
    for tag in tag_list:
        node = gaap.get(tag)
        if not node:
            continue
        for unit_pts in node.get("units", {}).values():
            for pt in unit_pts:
                if pt.get("form") not in ("10-K", "10-K/A"):
                    continue
                if pt.get("fp") not in (None, "FY"):
                    continue
                filed = pd.Timestamp(pt["filed"], tz="UTC")
                if filed > asof:
                    continue
                end = pt["end"]
                prev = out.get(end)
                if prev is None or filed >= prev[1]:
                    out[end] = (float(pt["val"]), filed)
        if out:
            break  # first tag in priority order that yields data wins
    return out


def pit_finyears(facts: dict, asof: pd.Timestamp):
    gaap = facts.get("facts", {}).get("us-gaap", {})
    dei = facts.get("facts", {}).get("dei", {})
    fields = {}
    ends_by_field = {}
    for field, tags in _TAGS.items():
        pts = _annual_points(gaap, tags, asof) or _annual_points(dei, tags, asof)
        fields[field] = pts
        ends_by_field[field] = set(pts)
    # fiscal-year ends where we at least have net income + assets
    common = sorted(set(fields["net_income"]) & set(fields["total_assets"]))
    if len(common) < 2:
        return None
    e_cur, e_prev = common[-1], common[-2]

    def build(end):
        g = lambda k: fields[k].get(end, (float("nan"), None))[0]
        filed = max((fields[k][end][1] for k in fields if end in fields[k]),
                    default=asof)
        ebitda = (g("_op_income") + g("_dda"))
        total_debt = (0.0 if pd.isna(g("_debt_cur")) else g("_debt_cur")) + \
                     (0.0 if pd.isna(g("lt_debt")) else g("lt_debt"))
        return FinYear(net_income=g("net_income"), total_assets=g("total_assets"),
                       cfo=g("cfo"), revenue=g("revenue"), gross_profit=g("gross_profit"),
                       cur_assets=g("cur_assets"), cur_liab=g("cur_liab"),
                       lt_debt=g("lt_debt"), shares=g("shares"),
                       book_equity=g("book_equity"), ebitda=ebitda,
                       total_debt=total_debt, cash=g("cash"), capex=g("capex"),
                       filed=filed)
    return build(e_cur), build(e_prev)
