import numpy as np, pandas as pd
from backtesting.value_quality.prices import median_dollar_volume, passes_universe

def test_median_dollar_volume_uses_trailing_window():
    idx = pd.date_range("2020-01-01", periods=80, freq="D", tz="UTC")
    df = pd.DataFrame({"close":[10.0]*80, "volume":[1_000]*80}, index=idx)
    dv = median_dollar_volume(df, asof=idx[79], window=60)
    assert abs(dv - 10_000) < 1e-6

def test_universe_gate():
    assert passes_universe(price=20, mktcap=5e8, dollar_vol=2e6) is True
    assert passes_universe(price=3, mktcap=5e8, dollar_vol=2e6) is False   # penny
    assert passes_universe(price=20, mktcap=1e8, dollar_vol=2e6) is False  # too small
    assert passes_universe(price=20, mktcap=5e8, dollar_vol=5e5) is False  # illiquid
