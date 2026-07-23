"""Strategy detection tests on hand-built synthetic fixtures (no network)."""

import numpy as np
import pandas as pd
import pytest

from tjr_4x.config import Config
from tjr_4x import strategy
from tjr_4x.tests.conftest import EXPECTED


def _force_bias(monkeypatch, sign):
    """Pin daily bias to a constant sign so the detection path is isolated.

    ``find_trades`` selects its bias via ``strategy._select_bias`` (which
    dispatches on ``cfg.bias_mode``); patch that so the test is independent of
    the promoted default mode (C)."""
    monkeypatch.setattr(
        strategy, "_select_bias",
        lambda df5m, cfg: pd.Series(
            sign, index=strategy._resample(strategy._prep(df5m),
                                           cfg.bias_timeframe).index),
    )


def test_bullish_sweep_bos_fvg_yields_one_long(bullish_5m, monkeypatch):
    """(1) A constructed bullish sweep -> MSS -> FVG yields exactly one long
    trade with SL below the sweep extreme and TP at fixed 2R."""
    _force_bias(monkeypatch, +1)
    cfg = Config()
    trades = strategy.find_trades(bullish_5m, cfg)

    assert len(trades) == 1
    t = trades[0]
    assert t.direction == 1
    assert t.entry == pytest.approx(EXPECTED["entry"], abs=1e-6)
    assert t.sweep_level == pytest.approx(EXPECTED["sweep_level"], abs=1e-6)
    assert t.bos_index == EXPECTED["bos_index"]

    # SL just beyond the sweep extreme (94) minus 0.1% buffer, and BELOW entry
    expected_sl = EXPECTED["sweep_extreme"] * (1 - cfg.sl_buffer_pct)
    assert t.sl == pytest.approx(expected_sl, abs=1e-6)
    assert t.sl < t.entry

    # TP is exactly 2R above entry
    risk = t.entry - t.sl
    assert t.tp == pytest.approx(t.entry + cfg.rr_target * risk, abs=1e-6)


def test_wick_only_break_is_not_a_sweep(bullish_15m):
    """(2) A wick that pierces the swing but whose body does NOT close back
    beyond the level within the window yields NO sweep event."""
    df = bullish_15m.copy()
    o = df.reset_index(drop=True)
    cfg = Config()
    shl = strategy.smc.swing_highs_lows(o, swing_length=cfg.swing_length)

    # baseline: our valid sweep exists
    base = strategy._detect_sweeps(o, shl, cfg)
    assert any(ev["direction"] == 1 for ev in base)

    # break the close-back: the wick still pierces 96 (bar 9 low 94), but no
    # body closes back above 96 within the 1-bar window (bars 9 and 10 both
    # close below the level) -> wick-only, NOT a valid sweep.
    o.loc[9, "open"] = 95.5
    o.loc[9, "high"] = 95.8
    o.loc[9, "close"] = 94.5   # below 96
    o.loc[10, "open"] = 95.0
    o.loc[10, "high"] = 95.6
    o.loc[10, "close"] = 95.2  # still below 96 -> no reclaim in window
    sweeps = strategy._detect_sweeps(o, shl, cfg)
    assert not any(ev["direction"] == 1 and ev["level"] == 96.0
                   for ev in sweeps)


def test_counter_bias_setup_is_filtered_out(bullish_5m, monkeypatch):
    """(3) The same bullish setup under a BEARISH daily bias produces no
    trade (long-only in bullish bias, short-only in bearish)."""
    _force_bias(monkeypatch, -1)
    trades = strategy.find_trades(bullish_5m, Config())
    assert trades == []


def test_causality_no_data_after_confirmation(bullish_5m, monkeypatch):
    """(5) Causality: mutating bars AFTER the trade's confirmation bar must
    NOT change the created trade (entry/sl/tp/direction). If future data
    leaked into creation, corrupting it would move the trade."""
    _force_bias(monkeypatch, +1)
    cfg = Config()

    baseline = strategy.find_trades(bullish_5m, cfg)
    assert len(baseline) == 1
    t0 = baseline[0]

    # confirmation is the 15m bar bos_index=13 -> corrupt everything strictly
    # after its close. Any 5m bar whose start > confirm close is "future".
    confirm_close = t0.confirm_time
    df = bullish_5m.copy()
    future = df.index > confirm_close
    assert future.any()
    df.loc[future, ["open", "high", "low", "close"]] *= 1.5  # violent corruption

    after = strategy.find_trades(df, cfg)
    assert len(after) == 1
    t1 = after[0]
    assert t1.direction == t0.direction
    assert t1.entry == pytest.approx(t0.entry, abs=1e-9)
    assert t1.sl == pytest.approx(t0.sl, abs=1e-9)
    assert t1.tp == pytest.approx(t0.tp, abs=1e-9)
    assert t1.bos_index == t0.bos_index
    assert t1.entry_time == t0.entry_time


def test_confirmation_respects_pivot_lag(bullish_5m, monkeypatch):
    """(5b) The confirming break bar is at/after pivot_bar + swing_length,
    i.e. the pivot was already confirmable when the trade was created."""
    _force_bias(monkeypatch, +1)
    cfg = Config()
    setup = strategy._resample(strategy._prep(bullish_5m), cfg.setup_timeframe)
    o = setup.reset_index(drop=True)
    shl = strategy.smc.swing_highs_lows(o, swing_length=cfg.swing_length)
    sweeps = strategy._detect_sweeps(o, shl, cfg)
    assert sweeps
    for ev in sweeps:
        # the close-back bar itself is >= pivot_bar + swing_length
        assert ev["bar"] >= ev["pivot_bar"] + cfg.swing_length
