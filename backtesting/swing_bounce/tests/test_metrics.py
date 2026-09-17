from backtesting.swing_bounce.metrics import expectancy


def _t(outcome, net, R):
    return {"outcome": outcome, "net_ret": net, "R": R}


def test_empty():
    m = expectancy([])
    assert m["n"] == 0 and m["hit_rate"] == 0.0 and m["expectancy_R"] == 0.0


def test_rates_and_expectancy():
    trades = [_t("target", 0.19, 1.9), _t("stop", -0.105, -1.05),
              _t("target", 0.19, 1.9), _t("time", 0.02, 0.2)]
    m = expectancy(trades)
    assert m["n"] == 4
    assert abs(m["hit_rate"] - 0.5) < 1e-9
    assert abs(m["stop_rate"] - 0.25) < 1e-9
    assert abs(m["time_rate"] - 0.25) < 1e-9
    assert abs(m["expectancy_R"] - (1.9 - 1.05 + 1.9 + 0.2) / 4) < 1e-9
    assert m["avg_win"] > 0 and m["avg_loss"] < 0
