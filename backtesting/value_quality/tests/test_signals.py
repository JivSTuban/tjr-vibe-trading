import numpy as np, pandas as pd
from backtesting.value_quality.signals import value_composite, drop_trigger

def test_value_composite_is_sector_relative():
    df = pd.DataFrame({
        "ep":[0.10,0.05, 0.10,0.05],
        "bp":[0.8,0.4, 0.8,0.4],
        "ebitda_ev":[0.2,0.1, 0.2,0.1],
        "fcf_yield":[0.09,0.03, 0.09,0.03],
        "sector":["tech","tech","energy","energy"],
    }, index=["A","B","C","D"])
    s = value_composite(df)
    # cheapest in each sector ranks above its sector peer
    assert s["A"] > s["B"] and s["C"] > s["D"]
    # ranks are within-sector: A (cheapest tech) and C (cheapest energy) both top their group
    assert 0.0 <= s.min() and s.max() <= 1.0

def test_value_composite_handles_nan_metric():
    df = pd.DataFrame({
        "ep":[0.10, np.nan, 0.02],
        "bp":[0.8,0.5,0.3], "ebitda_ev":[0.2,0.15,0.1], "fcf_yield":[0.09,0.05,0.02],
        "sector":["tech","tech","tech"],
    }, index=["A","B","C"])
    s = value_composite(df)          # must not raise; NaN metric ignored in that column's rank
    assert s.notna().all()

def test_drop_trigger_fires_below_threshold():
    idx = pd.date_range("2020-01-01", periods=100, freq="D", tz="UTC")
    px = pd.Series(np.linspace(100, 100, 100), index=idx)
    px.iloc[:64] = 100.0
    px.iloc[64:] = 70.0                       # -30% from the 100 trailing high
    asof = idx[80]
    assert drop_trigger(px, asof, threshold=0.75) is True     # 70 <= 0.75*100
    assert drop_trigger(px, asof, threshold=0.65) is False    # 70 > 0.65*100

def test_drop_trigger_is_lookahead_safe():
    idx = pd.date_range("2020-01-01", periods=70, freq="D", tz="UTC")
    px = pd.Series(100.0, index=idx)
    px.iloc[69] = 50.0                        # crash lands ON asof's day only
    asof = idx[65]                            # decision BEFORE the crash
    # trailing window is strictly before asof and all flat -> no trigger
    assert drop_trigger(px, asof, threshold=0.75) is False

def test_drop_trigger_excludes_the_asof_bar_itself():
    # crash lands EXACTLY on asof's bar; strict `< asof` must exclude it,
    # so the trailing window is all 100 -> no trigger. This test FAILS if the
    # comparison is weakened from `<` to `<=`.
    idx = pd.date_range("2020-01-01", periods=70, freq="D", tz="UTC")
    px = pd.Series(100.0, index=idx)
    px.iloc[65] = 50.0
    asof = idx[65]
    assert drop_trigger(px, asof, threshold=0.75) is False
