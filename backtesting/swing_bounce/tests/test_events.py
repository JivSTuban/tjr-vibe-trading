import numpy as np
import pandas as pd

from backtesting.swing_bounce.events import rsi, is_oversold, is_drop_event


def _s(vals):
    return pd.Series(vals, index=pd.date_range("2020-01-01", periods=len(vals), freq="D", tz="UTC"))


def test_rsi_bounds_and_low_after_selloff():
    s = _s(list(np.linspace(100, 60, 40)))          # steady decline
    r = rsi(s)
    assert (r.dropna() >= 0).all() and (r.dropna() <= 100).all()
    assert r.iloc[-1] < 40                            # persistent decline -> low RSI


def test_drop_event_fires_below_threshold_and_oversold():
    s = _s([100.0] * 63 + [70.0] * 10)               # -30% cliff then flat-low
    t = len(s) - 1
    assert is_drop_event(s, t, threshold=0.75) is True   # 70 <= 0.75*100
    assert is_drop_event(s, t, threshold=0.65) is False  # 70 > 0.65*100


def test_drop_event_returns_bool():
    s = _s(list(np.linspace(100, 74, 70)))
    t = len(s) - 1
    assert isinstance(is_drop_event(s, t, threshold=0.75), bool)


def test_oversold_needs_history():
    s = _s([100.0] * 5)
    assert is_oversold(s, 4) is False                 # <20 bars -> not enough history
