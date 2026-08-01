import pandas as pd

from backtesting.swing_bounce.trade_sim import simulate_trade


def _ohlc(rows):  # rows: list of (o,h,l,c)
    idx = pd.date_range("2020-01-01", periods=len(rows), freq="D", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def test_target_hit():
    df = _ohlc([(100, 100, 100, 100), (101, 121, 100, 120)])  # day1 high 121 >= 120 target(+20%)
    r = simulate_trade(df, 0, target_pct=0.20, stop_pct=0.10, horizon_days=5)
    assert r["outcome"] == "target" and abs(r["exit_price"] - 120) < 1e-9
    assert 0.19 < r["net_ret"] < 0.20                   # +20% minus ~30bps costs
    assert abs(r["R"] - r["net_ret"] / 0.10) < 1e-9


def test_stop_hit():
    df = _ohlc([(100, 100, 100, 100), (99, 101, 89, 90)])     # day1 low 89 <= 90 stop(-10%)
    r = simulate_trade(df, 0, target_pct=0.20, stop_pct=0.10, horizon_days=5)
    assert r["outcome"] == "stop" and abs(r["exit_price"] - 90) < 1e-9
    assert r["net_ret"] < -0.10                          # -10% plus costs


def test_same_bar_both_touched_is_stop_first():
    df = _ohlc([(100, 100, 100, 100), (100, 121, 89, 105)])   # both target(120) and stop(90) in range
    r = simulate_trade(df, 0, target_pct=0.20, stop_pct=0.10, horizon_days=5)
    assert r["outcome"] == "stop"


def test_gap_through_stop_fills_at_open():
    df = _ohlc([(100, 100, 100, 100), (80, 82, 78, 79)])      # opens 80, below 90 stop -> fill at 80
    r = simulate_trade(df, 0, target_pct=0.20, stop_pct=0.10, horizon_days=5)
    assert r["outcome"] == "stop" and abs(r["exit_price"] - 80) < 1e-9


def test_time_exit_at_horizon_close():
    df = _ohlc([(100, 100, 100, 100), (100, 105, 96, 101), (101, 106, 97, 102)])
    r = simulate_trade(df, 0, target_pct=0.20, stop_pct=0.10, horizon_days=2)
    assert r["outcome"] == "time" and abs(r["exit_price"] - 102) < 1e-9


def test_no_bars_after_entry_returns_none():
    df = _ohlc([(100, 100, 100, 100)])
    assert simulate_trade(df, 0, target_pct=0.20, stop_pct=0.10, horizon_days=5) is None
