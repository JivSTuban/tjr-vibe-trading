import numpy as np
import pandas as pd
from backtesting.value_quality.metrics import metrics_from_returns, equity_curve


def _rets(vals, start="2010-01-31"):
    idx = pd.date_range(start, periods=len(vals), freq="ME", tz="UTC")
    return pd.Series(vals, index=idx)


def test_cagr_of_constant_growth():
    r = _rets([0.01]*12)                 # +1%/mo for 12 months
    m = metrics_from_returns(r)
    assert abs(m.total_return - (1.01**12 - 1)) < 1e-9
    assert abs(m.cagr - (1.01**12 - 1)) < 1e-6   # exactly 1 year


def test_max_drawdown_captures_worst_peak_to_trough():
    r = _rets([0.10, -0.50, 0.05])        # up, big crash, small recover
    m = metrics_from_returns(r)
    assert abs(m.max_drawdown - (-0.50)) < 1e-9


def test_sharpe_zero_vol_is_not_inf():
    r = _rets([0.0]*12)
    m = metrics_from_returns(r)
    assert m.sharpe == 0.0                # guarded, not nan/inf


def test_equity_curve_starts_at_one():
    ec = equity_curve(_rets([0.1, -0.1]))
    assert abs(ec.iloc[0] - 1.1) < 1e-9 and ec.name != "raise"
