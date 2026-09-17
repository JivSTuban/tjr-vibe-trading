"""'Financially alive' falling-knife filter — the anti-bankruptcy gate for bounce candidates.

Validated in the stock-scan swing skill; profit + positive operating cash flow + solvency.
"""
from __future__ import annotations

from backtesting.value_quality.fundamentals import FinYear


def financially_alive(cur: FinYear) -> bool:
    da = (cur.lt_debt / cur.total_assets) if cur.total_assets and cur.total_assets > 0 else 0.0
    solvent = cur.book_equity > 0 and not (da > 0.6)
    return cur.net_income > 0 and cur.cfo > 0 and solvent
