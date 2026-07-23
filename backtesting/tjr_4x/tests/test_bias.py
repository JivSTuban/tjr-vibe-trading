"""Synthetic-fixture tests for the daily-bias engines. No network.

Covers:
  (a) Encoding A carries the last confirmed break sign forward and is 0
      before the first confirmed break.
  (b) Causality -- corrupting daily bars strictly AFTER day D does not
      change the bias at D (for every engine).
  (c) Encoding B neutralizes a long when price is in premium (> eq).
  (d) The 4H confluence gate zeros a daily +1 when the 4H sign is -1.
"""

import numpy as np
import pandas as pd

from backtesting.tjr_4x.config import Config
from backtesting.tjr_4x.bias import (
    bias_structure,
    bias_premium_discount,
    bias_draw_liquidity,
    confluence_4h,
    _apply_4h_gate,
    _last_break_sign,
)


CFG = Config(swing_length=2)


def _daily(bars):
    """bars: list of (o,h,l,c). Return a daily-indexed OHLCV frame."""
    idx = pd.date_range("2024-01-01", periods=len(bars), freq="1D", tz="UTC")
    return pd.DataFrame(
        [dict(open=o, high=h, low=l, close=c, volume=1.0) for (o, h, l, c) in bars],
        index=idx,
    )


# A rising series that prints a clean confirmed bullish break: a swing low,
# a swing high, a dip (swing low), then a body-close ABOVE the prior swing
# high -> bullish BOS/CHoCH. swing_length=2 so pivots confirm quickly.
_BULLISH = [
    (100, 101, 99, 100),   # 0
    (100, 102, 99, 101),   # 1
    (101, 103, 98, 98.5),  # 2  swing low region
    (98.5, 104, 98, 103),  # 3
    (103, 106, 102, 105),  # 4  swing high region (~106)
    (105, 105.5, 101, 101.5),  # 5  pullback
    (101.5, 102, 99, 99.5),    # 6  swing low
    (99.5, 103, 99, 102.5),    # 7
    (102.5, 107, 102, 106.8),  # 8  body close 106.8 > prior high -> bullish break
    (106.8, 109, 106, 108.5),  # 9
    (108.5, 111, 108, 110.5),  # 10
    (110.5, 113, 110, 112.5),  # 11
]


def test_a_carries_sign_and_zero_before_first_break():
    daily = _daily(_BULLISH)
    a = bias_structure(daily, CFG)
    # 0 before the first confirmed break
    assert a.iloc[0] == 0
    # a bullish break confirms and is carried forward to the end
    assert a.iloc[-1] == 1
    # once it turns +1 it stays +1 through the rising tail (carry-forward)
    first_pos = next(i for i, v in enumerate(a.values) if v == 1)
    assert (a.values[first_pos:] == 1).all()


def test_causality_future_bars_do_not_change_bias_at_D():
    daily = _daily(_BULLISH)
    D = 9  # evaluate bias at day index 9
    ref = {
        "A": bias_structure(daily, CFG).iloc[D],
        "B": bias_premium_discount(daily, daily, CFG).iloc[D],
    }
    # corrupt every bar strictly AFTER D with wild values
    corrupt = daily.copy()
    for j in range(D + 1, len(corrupt)):
        corrupt.iloc[j] = [50.0, 60.0, 10.0, 15.0, 1.0]  # o,h,l,c,volume
    after = {
        "A": bias_structure(corrupt, CFG).iloc[D],
        "B": bias_premium_discount(corrupt, corrupt, CFG).iloc[D],
    }
    assert ref == after, f"future bars leaked into day {D}: {ref} != {after}"


def test_b_neutralizes_long_in_premium():
    # Build a case where A is +1 but the close sits ABOVE equilibrium
    # (premium) -> B must stand down (0).
    daily = _daily(_BULLISH)
    a = bias_structure(daily, CFG)
    b = bias_premium_discount(daily, daily, CFG)
    # find a day where A is bullish
    bull_days = [i for i, v in enumerate(a.values) if v == 1]
    assert bull_days, "fixture must produce a bullish A"
    # On the rising tail the close is extended (premium) -> B should have at
    # least one day where it neutralizes a bullish A to 0.
    neutralized = [i for i in bull_days if b.iloc[i] == 0]
    assert neutralized, "B never neutralized a premium long"
    # and B must never flip a +1 into -1
    assert not ((a.values == 1) & (b.values == -1)).any()


def test_4h_confluence_gate_zeros_opposing_daily():
    idx = pd.date_range("2024-01-01", periods=5, freq="1D", tz="UTC")
    base = pd.Series([1, 1, 1, 1, 1], index=idx, dtype=int)
    conf = pd.Series([-1, -1, 0, 1, -1], index=idx, dtype=int)
    gated = _apply_4h_gate(base, conf)
    # opposing (-1) zeros the +1; neutral (0) and agreeing (+1) pass through
    assert list(gated.values) == [0, 0, 1, 1, 0]


def test_c_keeps_and_causal():
    # Bullish A, but leave an UNSWEPT prior high ABOVE the closes on the tail
    # so C keeps +1 (draw is up), while the sell-side pool sits far below.
    bars = list(_BULLISH)
    # after the break, print a tall unswept high (pool ABOVE) then let the
    # close sit JUST under it, with the prior-day low far below -> nearest
    # unswept pool is the one above, so C keeps the bullish sign.
    bars[9] = (106.8, 120, 100, 107.0)   # tall high 120 (pool above); wide low
    bars[10] = (107.0, 119.5, 107, 119.0)  # close 119 hugs the 120 pool
    bars[11] = (119.0, 119.8, 118.5, 119.5)  # close 119.5, nearest pool=120 above
    daily = _daily(bars)
    a = bias_structure(daily, CFG)
    c = bias_draw_liquidity(daily, daily, CFG)
    assert a.iloc[-1] == 1, "fixture must keep A bullish"
    # nearest unswept pool above -> C keeps the bullish sign on the tail
    assert c.iloc[-1] == 1
    # C must never flip a +1 into -1
    assert not ((a.values == 1) & (c.values == -1)).any()

    # causality: corrupting bars after D must not change C at D
    D = 10
    ref = c.iloc[D]
    corrupt = daily.copy()
    for j in range(D + 1, len(corrupt)):
        corrupt.iloc[j] = [50.0, 200.0, 5.0, 10.0, 1.0]
    assert bias_draw_liquidity(corrupt, corrupt, CFG).iloc[D] == ref


def test_last_break_sign_is_zero_then_signed():
    daily = _daily(_BULLISH)
    signs = _last_break_sign(daily.reset_index(drop=True), CFG.swing_length)
    assert signs[0] == 0
    assert signs[-1] == 1
