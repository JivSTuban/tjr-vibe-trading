import pandas as pd

from backtesting.swing_bounce.prices_ohlc import normalize_ohlc


def test_normalize_builds_ohlc_frame():
    raw = {"timestamp": [1577836800, 1577923200],
           "open": [100, 101], "high": [102, 103], "low": [99, 100],
           "close": [101, 102], "volume": [10, 11]}
    df = normalize_ohlc(raw)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is not None and len(df) == 2 and df["high"].iloc[0] == 102


def test_normalize_drops_null_close():
    raw = {"timestamp": [1577836800, 1577923200],
           "open": [100, 101], "high": [102, 103], "low": [99, 100],
           "close": [101, None], "volume": [10, 11]}
    df = normalize_ohlc(raw)
    assert len(df) == 1 and df["close"].iloc[0] == 101
