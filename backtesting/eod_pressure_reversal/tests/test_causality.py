"""Tests for the causality overlay.

The point-in-time guarantees are what make this study honest rather than a hindsight
story, so they are pinned here: a theme chosen using the signal day's own return, or a
beta fitted through the selloff, would explain the crash with itself and invent an edge.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.eod_pressure_reversal import causality


def _rets(n=400, seed=0):
    idx = pd.bdate_range("2020-01-01", periods=n)
    rng = np.random.default_rng(seed)
    return idx, rng


def test_theme_etfs_are_masked_before_inception():
    """REMX did not exist in 2009; a theme must be invisible before its ETF traded."""
    idx = pd.bdate_range("2009-01-01", periods=600)
    frames = {"REMX": pd.DataFrame({"close": np.linspace(10, 20, 600)}, index=idx)}
    tr = causality.theme_returns(frames)
    before = tr.loc[tr.index < pd.Timestamp(causality.THEME_ETFS["REMX"]), "REMX"]
    after = tr.loc[tr.index > pd.Timestamp("2010-12-01"), "REMX"]
    assert before.isna().all()
    assert after.notna().any()


def test_assign_theme_picks_the_basket_it_actually_moves_with():
    idx, rng = _rets(400)
    semis = pd.Series(rng.normal(0, 0.02, 400), index=idx)
    energy = pd.Series(rng.normal(0, 0.02, 400), index=idx)
    themes = pd.DataFrame({"SMH": semis, "XLE": energy})
    stock = semis * 1.3 + rng.normal(0, 0.002, 400)      # clearly a semis name
    label = causality.assign_theme(stock, themes)
    assert label.dropna().eq("SMH").mean() > 0.95


def test_assign_theme_never_uses_the_labelled_day_itself():
    """A one-day shock on the decision day must not change that day's label."""
    idx, rng = _rets(400)
    a = pd.Series(rng.normal(0, 0.02, 400), index=idx)
    b = pd.Series(rng.normal(0, 0.02, 400), index=idx)
    themes = pd.DataFrame({"A": a, "B": b})
    stock = a * 1.2 + rng.normal(0, 0.002, 400)
    base = causality.assign_theme(stock, themes)

    shocked = stock.copy()
    shocked.iloc[300] = -0.5                    # a crash on one session only
    after = causality.assign_theme(shocked, themes)
    assert base.iloc[300] == after.iloc[300]


def test_assign_theme_returns_nan_when_nothing_correlates():
    idx, rng = _rets(400)
    themes = pd.DataFrame({"A": rng.normal(0, 0.02, 400), "B": rng.normal(0, 0.02, 400)},
                          index=idx)
    stock = pd.Series(rng.normal(0, 0.02, 400), index=idx)   # independent noise
    label = causality.assign_theme(stock, themes, min_abs_corr=0.9)
    assert label.isna().all()


def test_rolling_beta_is_shifted_so_today_is_excluded():
    idx, rng = _rets(200)
    theme = pd.Series(rng.normal(0, 0.02, 200), index=idx)
    stock = theme * 2.0
    beta = causality.rolling_beta(stock, theme, window=60)
    # Corrupting only the last session must not move the last beta.
    stock2 = stock.copy()
    stock2.iloc[-1] = -0.9
    beta2 = causality.rolling_beta(stock2, theme, window=60)
    assert beta.iloc[-1] == pytest.approx(beta2.iloc[-1])
    assert beta.iloc[-1] == pytest.approx(2.0, abs=1e-6)


def test_decompose_calls_a_chainwide_selloff_pressure():
    """Whole chain down, stock carried by beta -> common_share near 1."""
    idx, rng = _rets(200, seed=3)
    theme = pd.Series(rng.normal(0, 0.015, 200), index=idx)
    stock = theme * 1.5                                    # pure beta, no idio
    themes = pd.DataFrame({"SMH": theme})
    label = pd.Series("SMH", index=idx)
    dec = causality.decompose(stock, themes, label, window=60)
    assert dec["common_share"].dropna().tail(50).mean() > 0.95


def test_decompose_calls_a_lone_break_information():
    """Chain flat, stock gaps down on its own -> common_share near 0."""
    idx, rng = _rets(200, seed=4)
    theme = pd.Series(rng.normal(0, 0.015, 200), index=idx)
    stock = theme * 1.0
    themes = pd.DataFrame({"SMH": theme})
    label = pd.Series("SMH", index=idx)

    stock = stock.copy()
    stock.iloc[-1] = theme.iloc[-1] - 0.20                 # -20% idiosyncratic shock
    dec = causality.decompose(stock, themes, label, window=60)
    assert dec["common_share"].iloc[-1] < 0.15


def test_theme_strength_is_relative_to_spy_and_lagged():
    idx = pd.bdate_range("2020-01-01", periods=200)
    strong = pd.Series(0.002, index=idx)       # +0.2%/day
    spy = pd.Series(0.000, index=idx)
    st = causality.theme_strength(pd.DataFrame({"T": strong}), spy, window=60)
    assert st["T"].dropna().iloc[-1] > 0
    # lagged by one session: the value at t cannot include t's own return
    st_mod = causality.theme_strength(
        pd.DataFrame({"T": pd.concat([strong.iloc[:-1], pd.Series([-0.5], index=idx[-1:])])}),
        spy, window=60)
    assert st["T"].iloc[-1] == pytest.approx(st_mod["T"].iloc[-1])


def test_label_cells_builds_the_four_causal_buckets():
    t = pd.DataFrame({
        "common_share": [0.9, 0.9, 0.1, 0.1, np.nan],
        "theme_strength": [0.05, -0.05, 0.05, -0.05, 0.05],
    })
    out = causality.label_cells(t)
    assert out["cell"].tolist()[:4] == [
        "PRESSURE / TAILWIND", "PRESSURE / HEADWIND",
        "INFORMATION / TAILWIND", "INFORMATION / HEADWIND",
    ]
    assert pd.isna(out["cause"].iloc[4])


def test_jackknife_flags_a_single_year_carrying_the_result():
    """One huge year on top of flat years must be detected as the whole result."""
    from backtesting.eod_pressure_reversal import metrics
    dates = ([pd.Timestamp("2021-06-01")] * 100) + ([pd.Timestamp("2022-06-01")] * 100)
    rets = ([0.0] * 100) + ([0.05] * 100)          # 2022 carries everything
    t = pd.DataFrame({"date": dates, "net_ret": rets})
    jk = metrics.jackknife_years(t)
    assert jk["most_influential_year"] == 2022
    assert jk["survives_dropping_best_year"] is False


def test_jackknife_passes_a_broadly_positive_result():
    from backtesting.eod_pressure_reversal import metrics
    dates, rets = [], []
    for y in range(2018, 2024):
        dates += [pd.Timestamp(f"{y}-06-01")] * 50
        rets += [0.002] * 50                        # every year contributes
    t = pd.DataFrame({"date": dates, "net_ret": rets})
    jk = metrics.jackknife_years(t)
    assert jk["survives_dropping_best_year"] is True
    assert jk["min_loo_bps"] > 0
