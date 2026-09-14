"""Network-free tests for the pure signal/strategy/metric layers.

These exist because every number in FINDINGS.md is downstream of this logic: an
off-by-one in the exit leg or a look-ahead in a rolling window would produce a
confident, wrong verdict.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.eod_pressure_reversal import earnings, metrics, signals, strategy


def _frame(closes, highs=None, lows=None, opens=None, vols=None):
    n = len(closes)
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame(
        {
            "open": opens or closes,
            "high": highs or [c * 1.02 for c in closes],
            "low": lows or [c * 0.98 for c in closes],
            "close": closes,
            "volume": vols or [1_000_000] * n,
            "adjclose": closes,
        },
        index=idx,
    )


def test_day_return_and_drawdown_are_exact():
    df = _frame([100.0, 97.9], highs=[100.0, 101.0], lows=[99.0, 97.0])
    bench = pd.Series(0.0, index=df.index)
    f = signals.compute_features(df, bench, adv_window=1)
    assert f["day_ret"].iloc[1] == pytest.approx(-0.021, abs=1e-6)
    assert f["dd_from_high"].iloc[1] == pytest.approx(97.9 / 101.0 - 1, abs=1e-6)


def test_close_location_is_zero_at_the_low_and_one_at_the_high():
    df = _frame([100.0, 90.0], highs=[100.0, 100.0], lows=[100.0, 90.0])
    f = signals.compute_features(df, pd.Series(0.0, index=df.index), adv_window=1)
    assert f["close_loc"].iloc[1] == pytest.approx(0.0)      # closed on the low
    df2 = _frame([100.0, 100.0], highs=[100.0, 100.0], lows=[100.0, 90.0])
    f2 = signals.compute_features(df2, pd.Series(0.0, index=df2.index), adv_window=1)
    assert f2["close_loc"].iloc[1] == pytest.approx(1.0)     # closed on the high


def test_relative_volume_excludes_today_no_lookahead():
    # 20 quiet days then one 5x day. The median must NOT be contaminated by today.
    closes = [100.0] * 22
    vols = [1_000_000] * 21 + [5_000_000]
    f = signals.compute_features(_frame(closes, vols=vols), pd.Series(0.0, index=_frame(closes).index))
    assert f["rel_vol"].iloc[-1] == pytest.approx(5.0)


def test_adv20_uses_only_prior_sessions():
    closes = [100.0] * 25
    vols = [100_000] * 24 + [99_999_999]
    f = signals.compute_features(_frame(closes, vols=vols), pd.Series(0.0, index=_frame(closes).index))
    # today's monster volume must not inflate today's ADV screen
    assert f["adv20"].iloc[-1] == pytest.approx(100_000 * 100.0)


def test_spec_example_trade_passes_every_filter():
    """Spec §15 worked example: -2.10% day, -3.07% from high, -1.70% vs sector."""
    df = _frame([100.0, 97.9], highs=[100.0, 101.0], lows=[100.0, 97.9])
    bench = pd.Series([0.0, -0.004], index=df.index)
    f = signals.compute_features(df, bench, adv_window=1)
    f = f.assign(rel_vol=2.1)
    flags = signals.passes(f)
    assert flags.iloc[1][["A_day", "B_late", "C_high", "D_sector", "E_vol"]].all()


def test_percentile_score_ranks_the_most_distressed_first():
    cands = pd.DataFrame(
        {
            "day_ret": [-0.05, -0.02],
            "close_loc": [0.01, 0.20],
            "dd_from_high": [-0.06, -0.02],
            "rel_sector": [-0.04, -0.01],
            "rel_vol": [3.0, 1.6],
        },
        index=["WORST", "MILD"],
    )
    s = signals.percentile_scores(cands)
    assert s["WORST"] > s["MILD"]


def test_costs_are_charged_per_side():
    t = pd.DataFrame({"price": [100.0], "next_open": [101.0]})
    out = strategy.simulate(t, cost_bps=5.0)
    assert out["gross_ret"].iloc[0] == pytest.approx(0.01)
    assert out["net_ret"].iloc[0] == pytest.approx(0.01 - 0.001)   # 5bps x 2 sides


def test_stage_order_is_monotonically_more_selective():
    n = 60
    idx = pd.bdate_range("2021-01-01", periods=n)
    rng = np.random.default_rng(0)
    cands = pd.DataFrame({
        "date": list(idx) * 3,
        "ticker": ["A"] * n + ["B"] * n + ["C"] * n,
        "day_ret": rng.normal(-0.01, 0.02, 3 * n),
        "close_loc": rng.uniform(0, 1, 3 * n),
        "dd_from_high": rng.normal(-0.02, 0.02, 3 * n),
        "rel_sector": rng.normal(-0.005, 0.02, 3 * n),
        "rel_vol": rng.uniform(0.5, 3.0, 3 * n),
        "price": 50.0, "next_open": 50.0,
    })
    flags = signals.passes(cands)
    cands = pd.concat([cands, flags], axis=1)
    counts = [len(strategy.apply_stage(cands, s)) for s in range(6)]
    assert counts == sorted(counts, reverse=True), counts


def test_top5_cap_is_per_day():
    idx = pd.to_datetime(["2021-01-04"] * 9)
    cands = pd.DataFrame({
        "date": idx,
        "ticker": list("ABCDEFGHI"),
        "day_ret": np.linspace(-0.10, -0.02, 9),
        "close_loc": np.linspace(0.01, 0.20, 9),
        "dd_from_high": np.linspace(-0.12, -0.03, 9),
        "rel_sector": np.linspace(-0.08, -0.02, 9),
        "rel_vol": np.linspace(3.0, 1.6, 9),
        "price": 50.0, "next_open": 50.0,
        "A_day": True, "B_late": True, "C_high": True, "D_sector": True, "E_vol": True,
    })
    out = strategy.apply_stage(cands, 7, top_n=5)
    assert len(out) == 5
    assert "A" in out["ticker"].tolist()      # most distressed is selected


def test_equal_weight_is_within_day_not_across_trades():
    trades = pd.DataFrame({
        "date": pd.to_datetime(["2021-01-04", "2021-01-04", "2021-01-05"]),
        "net_ret": [0.10, -0.10, 0.05],
    })
    daily = strategy.equity_curve(trades)
    assert daily.loc[0, "ret"] == pytest.approx(0.0)     # two names net to flat
    assert daily.loc[1, "ret"] == pytest.approx(0.05)


class TestEarningsWindow:
    """Filter F's timing logic — the part a naive +/-1 day band gets wrong."""

    sessions = pd.to_datetime(["2021-01-04", "2021-01-05", "2021-01-06"])

    def _blocked(self, date, time_flag):
        idx = pd.DataFrame({"date": [pd.Timestamp(date)], "symbol": ["XYZ"], "time": [time_flag]})
        return earnings.blocked_pairs(idx, self.sessions)

    def test_after_close_tonight_blocks_tonight(self):
        assert (pd.Timestamp("2021-01-05"), "XYZ") in self._blocked("2021-01-05", "time-after-hours")

    def test_before_open_tomorrow_blocks_tonight(self):
        assert (pd.Timestamp("2021-01-04"), "XYZ") in self._blocked("2021-01-05", "time-pre-market")

    def test_before_open_today_does_not_block(self):
        """A BMO print on the signal day is already in the close — not a forward shock."""
        blocked = self._blocked("2021-01-05", "time-pre-market")
        assert (pd.Timestamp("2021-01-05"), "XYZ") not in blocked

    def test_unknown_time_blocks_both_sides(self):
        """Nasdaq supplies no time flag historically, so unknown must block the report
        day too — otherwise an AMC reporter is held through its own release."""
        blocked = self._blocked("2021-01-05", "time-not-supplied")
        assert (pd.Timestamp("2021-01-04"), "XYZ") in blocked   # could be BMO tomorrow
        assert (pd.Timestamp("2021-01-05"), "XYZ") in blocked   # could be AMC tonight

    def test_known_amc_does_not_block_the_prior_session(self):
        """A known AMC print only threatens the night of the report, not the night before."""
        blocked = self._blocked("2021-01-05", "time-after-hours")
        assert (pd.Timestamp("2021-01-04"), "XYZ") not in blocked


def test_left_tail_flags_a_lottery_ticket_distribution():
    r = [-0.01] * 99 + [2.0]          # one giant winner carrying 99 small losses
    t = pd.DataFrame({"net_ret": r})
    lt = metrics.left_tail(t)
    assert lt["sum_all"] > 0
    assert lt["mean_ex_best_1pct"] < 0        # the edge is one trade -> spec §17 rejects


def test_regime_tagging_uses_signal_day_values():
    idx = pd.to_datetime(["2021-01-04", "2021-01-05"])
    trades = pd.DataFrame({"date": idx, "net_ret": [0.01, -0.01]})
    vix = pd.Series([12.0, 35.0], index=idx)
    spy = pd.Series([0.005, -0.02], index=idx)
    out = metrics.tag_regimes(trades, vix, spy)
    assert out["vix_bucket"].astype(str).tolist() == ["VIX<15", "VIX>30"]
    assert out["spy_bucket"].astype(str).tolist() == ["SPY>0%", "SPY<-1%"]


def test_membership_is_point_in_time():
    from backtesting.eod_pressure_reversal import universe
    m = pd.DataFrame({
        "ticker": ["LIVE", "GONE"],
        "start": pd.to_datetime(["2010-01-01", "2010-01-01"]),
        "end": pd.to_datetime([None, "2016-06-30"]),
    })
    assert universe.members_on(m, "2015-01-01") == ["GONE", "LIVE"]
    assert universe.members_on(m, "2020-01-01") == ["LIVE"]
    # the removal date itself is still tradable
    assert "GONE" in universe.members_on(m, "2016-06-30")


def test_corporate_action_flag_catches_a_split_not_a_dividend():
    from backtesting.eod_pressure_reversal import prices
    idx = pd.bdate_range("2020-01-01", periods=4)
    df = pd.DataFrame({
        "open": [100.0] * 4, "high": [100.0] * 4, "low": [100.0] * 4,
        "close": [100.0, 100.0, 50.0, 50.0],
        "volume": [1e6] * 4,
        "adjclose": [50.0, 49.99, 50.0, 50.0],      # ratio: .50, .4999, 1.0, 1.0
    }, index=idx)
    flags = prices.flag_corporate_actions(df)
    assert not flags.iloc[1]        # tiny dividend drift -> not flagged
    assert flags.iloc[2]            # 2:1 split -> flagged


def test_overnight_return_is_split_and_dividend_adjusted():
    """A 2:1 split overnight must read as flat, not -50%."""
    t = pd.DataFrame({
        "price": [100.0],          # close before the split
        "next_open": [50.0],       # raw open after the 2:1 split
        "adj_factor": [0.5],       # adjclose/close before  (adjusted back by the split)
        "next_adj_factor": [1.0],  # after the split, no further adjustment
    })
    out = strategy.simulate(t, cost_bps=0.0)
    assert out["gross_ret"].iloc[0] == pytest.approx(0.0, abs=1e-9)
    assert out["raw_gap"].iloc[0] == pytest.approx(-0.5)   # the trap we avoided


def test_overnight_return_falls_back_to_raw_without_factors():
    t = pd.DataFrame({"price": [100.0], "next_open": [101.0]})
    out = strategy.simulate(t, cost_bps=0.0)
    assert out["gross_ret"].iloc[0] == pytest.approx(0.01)
