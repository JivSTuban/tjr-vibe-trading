"""Shared synthetic fixtures for the TJR 4X tests. No network.

The canonical bullish setup is authored on the 15m timeframe, then
upsampled to 5m so that ``df.resample("15min")`` reconstructs the exact
15m OHLC. This lets the tests exercise the real resample -> smc ->
detection path end-to-end without any network or recorded data.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

# make ``tjr_4x`` importable regardless of pytest rootdir
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def _bar(o, h, l, c):
    return dict(open=o, high=h, low=l, close=c, volume=1.0)


# --- Canonical bullish sweep -> MSS(CHoCH) -> FVG story on 15m -------------- #
# swings settle to: low1@96 (bar0), high1@101 (bar5), sweep-low@94 (bar9),
# high2@102.6 (bar14). Body-close of bar13 (102.4 > 101) confirms a bullish
# MSS (CHoCH). A gap on bar13 leaves a bullish FVG (Top 101.2) -> entry.
_BULLISH_15M = [
    (98.0, 98.2, 96.0, 96.1),    # 0  swing low region (level 96)
    (96.1, 97.0, 96.0, 96.9),    # 1
    (96.9, 97.2, 95.9, 96.1),    # 2
    (96.1, 97.5, 96.0, 97.4),    # 3
    (97.4, 99.5, 97.3, 99.4),    # 4
    (99.4, 101.0, 99.3, 100.6),  # 5  swing high (level 101)
    (100.6, 100.8, 99.5, 99.6),  # 6
    (99.6, 99.8, 98.0, 98.2),    # 7
    (98.2, 98.4, 96.5, 96.7),    # 8
    (96.7, 96.9, 94.0, 96.5),    # 9  SWEEP: wick 94 < 96, close 96.5 back above
    (96.5, 97.5, 96.4, 97.4),    # 10 displacement up begins
    (97.4, 98.8, 97.3, 98.7),    # 11
    (98.7, 100.2, 98.6, 100.1),  # 12
    (100.5, 102.5, 100.4, 102.4),  # 13 MSS: close 102.4 > 101; gap -> FVG(top 101.2)
    (102.4, 102.6, 101.2, 101.4),  # 14 swing high 2
    (101.4, 101.6, 100.5, 100.7),  # 15 retrace into FVG
    (100.7, 101.0, 99.8, 100.0),   # 16
    (100.0, 100.4, 99.2, 99.5),    # 17
    (99.5, 99.8, 98.8, 99.2),      # 18
    (99.2, 99.5, 98.5, 99.0),      # 19
]

# entry = Top of the bullish FVG at bar 12 (known at bar 13 = the MSS bar);
# the FVG at bar 13 itself is EXCLUDED because it needs bar 14 (look-ahead).
EXPECTED = dict(direction=1, entry=100.4, sweep_level=96.0,
                sweep_extreme=94.0, bos_index=13)


def _upsample_to_5m(df15: pd.DataFrame) -> pd.DataFrame:
    """Explode each 15m bar into three 5m bars whose resample('15min')
    reproduces the original OHLC exactly."""
    rows = []
    for ts, row in df15.iterrows():
        o1, h, l, c = row["open"], row["high"], row["low"], row["close"]
        mid = (o1 + c) / 2.0
        trip = [
            (o1, max(o1, mid), min(o1, mid), mid),
            (mid, h, l, mid),          # middle bar carries the extreme high/low
            (mid, max(mid, c), min(mid, c), c),
        ]
        for k, (oo, hh, ll, cc) in enumerate(trip):
            rows.append(dict(open=oo, high=max(hh, oo, cc), low=min(ll, oo, cc),
                             close=cc, volume=1.0,
                             ts=ts + pd.Timedelta(minutes=5 * k)))
    out = pd.DataFrame(rows).set_index("ts")
    out.index.name = None
    return out


@pytest.fixture
def bullish_15m():
    idx = pd.date_range("2024-01-01", periods=len(_BULLISH_15M),
                        freq="15min", tz="UTC")
    return pd.DataFrame([_bar(*x) for x in _BULLISH_15M], index=idx)


@pytest.fixture
def bullish_5m(bullish_15m):
    df = _upsample_to_5m(bullish_15m)
    # sanity: resample must reconstruct the 15m frame
    re = df.resample("15min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min",
         "close": "last", "volume": "sum"})
    assert np.allclose(re["high"].values, bullish_15m["high"].values)
    assert np.allclose(re["low"].values, bullish_15m["low"].values)
    assert np.allclose(re["close"].values, bullish_15m["close"].values)
    return df
