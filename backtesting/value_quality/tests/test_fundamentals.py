import math
import pandas as pd
from backtesting.value_quality.fundamentals import FinYear, piotroski_fscore, valuation

def _fy(**kw):
    base = dict(net_income=100.0, total_assets=1000.0, cfo=150.0, revenue=800.0,
                gross_profit=320.0, cur_assets=400.0, cur_liab=200.0, lt_debt=100.0,
                shares=50.0, book_equity=600.0, ebitda=180.0, total_debt=150.0,
                cash=90.0, capex=40.0, filed=pd.Timestamp("2015-03-01", tz="UTC"))
    base.update(kw); return FinYear(**base)

def test_perfect_fscore_is_9():
    # cur strictly better than prev on every dimension a firm controls
    prev = _fy(net_income=10, total_assets=1000, cfo=5, revenue=800, gross_profit=240,
               cur_assets=300, cur_liab=250, lt_debt=200, shares=50)
    cur  = _fy(net_income=100, total_assets=1000, cfo=150, revenue=900, gross_profit=360,
               cur_assets=400, cur_liab=150, lt_debt=100, shares=50)
    assert piotroski_fscore(cur, prev) == 9

def test_all_bad_fscore_is_0_or_low():
    prev = _fy(net_income=100, total_assets=1000, cfo=150, revenue=900, gross_profit=360,
               cur_assets=400, cur_liab=150, lt_debt=100, shares=50)
    cur  = _fy(net_income=-10, total_assets=1000, cfo=-5, revenue=800, gross_profit=240,
               cur_assets=300, cur_liab=250, lt_debt=200, shares=60)  # loss, neg CFO, more debt, dilution
    assert piotroski_fscore(cur, prev) <= 1

def test_accrual_signal_rewards_cfo_above_ni():
    prev = _fy()
    strong = _fy(cfo=200, net_income=100)   # cfo > ni -> accrual point
    weak   = _fy(cfo=50,  net_income=100)    # cfo < ni -> no accrual point
    assert piotroski_fscore(strong, prev) > piotroski_fscore(weak, prev)

def test_valuation_basic_ratios():
    fy = _fy(net_income=100, shares=50, book_equity=600, ebitda=180,
             total_debt=150, cash=90, cfo=150, capex=40)
    v = valuation(fy, price=20.0)     # mktcap = 1000
    assert math.isclose(v["ep"], 100/1000, rel_tol=1e-9)          # earnings yield
    assert math.isclose(v["bp"], 600/1000, rel_tol=1e-9)          # book/price
    ev = 1000 + 150 - 90                                          # 1060
    assert math.isclose(v["ebitda_ev"], 180/ev, rel_tol=1e-9)
    assert math.isclose(v["fcf_yield"], (150-40)/1000, rel_tol=1e-9)

def test_valuation_guards_nonpositive_denominators():
    fy = _fy(shares=0)               # mktcap = 0 -> ratios undefined, not a crash
    v = valuation(fy, price=20.0)
    assert math.isnan(v["ep"])
