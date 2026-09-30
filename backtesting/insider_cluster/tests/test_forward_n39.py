"""Offline tests for the forward n=39 tracker. The parity test needs the frozen backtest caches
(gitignored, local only) and is skipped without them."""
import pandas as pd
import pytest

from backtesting.insider_cluster import forward_n39 as F
from backtesting.insider_cluster import retest_n39 as R

P20 = {"202609": 1e9, "202610": 1e9}
BIG, SMALL = (lambda t, prices, when: 5e9), (lambda t, prices, when: 1e8)


def ohlc(start="2026-06-01", n=200, px=10.0, slope=0.0):
    idx = pd.bdate_range(start, periods=n, tz="UTC")
    c = [px * (1 + slope) ** i for i in range(n)]
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": 1e6}, index=idx)


def arms(events, beats, prices, today="2026-12-31", mcap=BIG, p20=P20, since=F.FORWARD_START):
    return F.forward_arms(events, prices, beats, p20, today, since=since, mcap=mcap)


def test_mature_bar_needs_a_full_window():
    o = ohlc(n=100)
    assert F.mature_bar(o, 100 - F.H) is True          # bars i .. i+59 end exactly at the last bar
    assert F.mature_bar(o, 100 - F.H + 1) is False      # one bar short: a clamped "60d" return
    assert F.mature_bar(o, None) is False


def test_old_event_is_graded_and_young_event_is_pending_not_clamped():
    o = ohlc("2026-08-01", 200, slope=0.001)
    ev_old = {"ticker": "AAA", "date": "2026-09-03"}
    ev_new = {"ticker": "AAA", "date": o.index[-10].strftime("%Y-%m-%d")}
    a = arms([ev_old, ev_new], {"AAA": [pd.Timestamp("2026-08-20"), o.index[-40].tz_localize(None)]}, {"AAA": o})
    assert len(a["ins_cat"]["graded"]) == 1 and len(a["ins_cat"]["pending"]) == 1
    t, d, r, est, since_beat = a["ins_cat"]["graded"][0]
    assert r is not None and r > 0 and since_beat == 14
    assert a["ins_cat"]["pending"][0][2] is None


def test_beat_after_the_filing_is_not_a_catalyst():
    o = ohlc("2026-08-01", 200)
    a = arms([{"ticker": "AAA", "date": "2026-09-03"}], {"AAA": [pd.Timestamp("2026-09-10")]}, {"AAA": o})
    assert len(a["ins_nocat"]["graded"]) == 1 and not a["ins_cat"]["graded"], "a beat announced after entry is unknowable at entry"
    a = arms([{"ticker": "AAA", "date": "2026-09-03"}], {"AAA": [pd.Timestamp("2026-05-01")]}, {"AAA": o})
    assert not a["ins_cat"]["graded"], "a beat older than 90 days is not a current catalyst"


def test_cat_only_excludes_beats_within_30d_of_a_cluster_and_respects_since():
    o = ohlc("2026-08-01", 200)
    beats = {"AAA": [pd.Timestamp("2026-09-15"), pd.Timestamp("2026-10-20"), pd.Timestamp("2026-08-15")]}
    a = arms([{"ticker": "AAA", "date": "2026-09-10"}], beats, {"AAA": o})
    assert [r[1] for r in a["cat_only"]["graded"] + a["cat_only"]["pending"]] == [pd.Timestamp("2026-10-20")]


def test_microcap_and_missing_data_are_named_not_counted():
    o = ohlc("2026-08-01", 200)
    a = arms([{"ticker": "AAA", "date": "2026-09-03"}, {"ticker": "ZZZ", "date": "2026-09-03"}], {"AAA": []}, {"AAA": o}, mcap=SMALL)
    assert a["drops"]["microcap"] == [("AAA", "2026-09-03")]
    assert a["drops"]["no_price"] == [("ZZZ", "2026-09-03")]
    a = arms([{"ticker": "AAA", "date": "2026-09-03"}], {"AAA": []}, {"AAA": o}, mcap=lambda *x: None)
    assert a["drops"]["no_mcap"] == [("AAA", "2026-09-03")]


def test_stale_prices_are_flagged_and_event_stays_pending():
    o = ohlc("2026-08-01", 45)                      # ends ~2026-10-02, far before "today"
    a = arms([{"ticker": "AAA", "date": "2026-09-03"}], {"AAA": []}, {"AAA": o}, today="2026-12-31")
    assert a["drops"]["stale_price"] and a["ins_nocat"]["pending"] and not a["ins_nocat"]["graded"]


def test_p20_forward_fill_is_reported():
    assert F.p20_for({"202608": 7.0}, "2026-10-05") == (7.0, True)
    assert F.p20_for({"202610": 9.0}, "2026-10-05") == (9.0, False)
    assert F.p20_for({}, "2026-10-05") == (None, False)
    o = ohlc("2026-08-01", 200)
    a = arms([{"ticker": "AAA", "date": "2026-09-03"}], {"AAA": []}, {"AAA": o}, p20={"202608": 1e9})
    assert a["drops"]["p20_ffill_months"] == ["202609"] and a["ins_nocat"]["graded"]


def test_verdict_never_decides_early():
    ic, co = [0.10] * 29, [0.0] * 50
    assert F.verdict(ic, co)["status"] == "PENDING"
    v = F.verdict([0.05] * 8, [0.0] * 8)
    assert v["status"] == "PENDING" and v["diff"] == pytest.approx(0.05), "interim diff shown but non-binding"
    assert "diff" not in F.verdict([0.05] * 7, [0.0] * 50)


def test_verdict_at_n_applies_the_precommitted_3pp_rule():
    assert F.verdict([0.05] * 30, [0.01] * 40)["status"] == "KEEP"       # +4pp
    assert F.verdict([0.03] * 30, [0.01] * 40)["status"] == "KILL"       # +2pp
    assert F.verdict([0.04] * 30, [0.01] * 40)["status"] == "KEEP"       # exactly +3pp counts
    v = F.verdict([0.05] * 30, [0.01] * 3)
    assert v["status"] == "PENDING" and "control" in v["note"], "no verdict without a control arm"


def test_retest_rule_needs_all_three_checks():
    assert F.retest_rule([0.06] * 20, [0.01] * 50)["survives"] is True
    assert F.retest_rule([0.06] * 19, [0.01] * 50)["a_n"] is False, "n=19 fails (a)"
    assert F.retest_rule([0.04] * 20, [0.02] * 50)["c_diff"] is False, "+2pp fails (c)"
    r = F.retest_rule([-0.05] * 10 + [0.30] * 10, [0.0] * 50)
    assert r["b_trim"] is True and r["survives"] is True
    assert F.retest_rule([], [0.01])["survives"] is False


def test_report_shows_pending_and_next_maturity():
    o = ohlc("2026-08-01", 200)
    a = arms([{"ticker": "AAA", "date": o.index[-5].strftime("%Y-%m-%d")}], {"AAA": [o.index[-20].tz_localize(None)]}, {"AAA": o})
    a["universe"], a["events"] = 1, 1
    txt = F.report(a)
    assert "ins_cat" in txt and "pending   1" in txt and "next matures" in txt and "RULE: PENDING" in txt


@pytest.mark.skipif(not R.os.path.exists(R._CACHE + "/panel_2021-01_2026-08.csv"), reason="frozen backtest caches not present")
def test_parity_with_frozen_ladder():
    """Same events, same definitions: forward_arms on the frozen data classifies every event the
    way the frozen L3/L4 ladder does, and matured returns are identical."""
    events, _, prices = R.load_universe()
    results = R.fetch_results_filings(list(prices))
    p20 = R.nyse_p20()
    lad = R.ladder(events, prices, 3, 150.0, results, p20)
    beats = {t: R.actual_beat_dates(t, results)[0] for t in prices}
    fa = F.forward_arms(events, prices, beats, p20, "2026-08-31", since=R.CAT_START, cost=150.0)
    for arm in ("ins_cat", "ins_nocat", "cat_only"):
        mine = {(t, pd.Timestamp(d)): r for t, d, r, *_ in fa[arm]["graded"]}
        pend = {(t, pd.Timestamp(d)) for t, d, *_ in fa[arm]["pending"]}
        ref = {(t, pd.Timestamp(d)): r for t, d, r, _ in lad[arm]}
        # Every event the frozen ladder scored is present here, nothing it scored is lost...
        assert set(ref) <= set(mine) | pend, f"{arm}: lost {sorted(set(ref) - set(mine) - pend)[:5]}"
        # ...anything extra is an event the ladder silently DROPPED for lack of a t+2 bar (here: PENDING)...
        assert (set(mine) | pend) - set(ref) <= pend, f"{arm}: extra graded events"
        # ...and matured returns are identical.
        for k, r in mine.items():
            assert r == pytest.approx(ref[k]), (arm, k)
    # The frozen ladder grades immature trades with a clamped exit; this module must not.
    immature = [k for k in ref_all(lad) if k not in {(t, pd.Timestamp(d)) for a in fa.values() if isinstance(a, dict) and "graded" in a for t, d, *_ in a["graded"]}]
    assert immature, "expected the frozen window to contain trades without a full 60d exit"


def ref_all(lad):
    return [(t, pd.Timestamp(d)) for arm in ("ins_cat", "ins_nocat", "cat_only") for t, d, _, _ in lad[arm]]
