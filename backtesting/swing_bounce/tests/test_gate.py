import pandas as pd

from backtesting.value_quality.fundamentals import FinYear
from backtesting.swing_bounce.gate import financially_alive


def _fy(**kw):
    base = dict(net_income=100.0, total_assets=1000.0, cfo=150.0, revenue=800.0,
                gross_profit=320.0, cur_assets=400.0, cur_liab=200.0, lt_debt=100.0,
                shares=50.0, book_equity=600.0, ebitda=180.0, total_debt=150.0,
                cash=90.0, capex=40.0, filed=pd.Timestamp("2015-03-01", tz="UTC"))
    base.update(kw)
    return FinYear(**base)


def test_healthy_is_alive():
    assert financially_alive(_fy()) is True


def test_loss_is_not_alive():
    assert financially_alive(_fy(net_income=-10)) is False


def test_negative_cfo_is_not_alive():
    assert financially_alive(_fy(cfo=-5)) is False


def test_negative_equity_is_not_alive():
    assert financially_alive(_fy(book_equity=-1)) is False


def test_over_levered_is_not_alive():
    assert financially_alive(_fy(lt_debt=700, total_assets=1000)) is False  # D/A 0.7 > 0.6
