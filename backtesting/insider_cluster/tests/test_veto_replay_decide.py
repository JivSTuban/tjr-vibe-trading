from backtesting.insider_cluster.veto_replay_decide import decide


def _rows(vetoed, cleared, errors=0):
    r = [{"arm": "cat_only", "ticker": f"V{i}", "date": "2026-01-01", "ret": x, "verdict": "VETO"} for i, x in enumerate(vetoed)]
    r += [{"arm": "cat_only", "ticker": f"C{i}", "date": "2026-01-01", "ret": x, "verdict": "CLEAR"} for i, x in enumerate(cleared)]
    r += [{"arm": "cat_only", "ticker": f"E{i}", "date": "2026-01-01", "ret": 0.5, "verdict": "ERROR"} for i in range(errors)]
    return r


def test_earns_its_place_when_vetoed_events_are_clearly_worse():
    v = [-0.10 + 0.002 * i for i in range(20)]      # median about -0.08
    c = [0.04 + 0.002 * i for i in range(60)]       # median about +0.10
    d = decide(_rows(v, c), "cat_only")
    assert d["outcome"] == "VETO EARNS ITS PLACE" and d["diff"] >= 0.03 and d["boot90"][0] > 0


def test_no_evidence_when_gap_is_too_small():
    v = [0.03 + 0.001 * i for i in range(20)]       # median about +0.040
    c = [0.03 + 0.001 * i for i in range(60)]       # median about +0.060, a 2pp gap: under the 3pp bar
    assert decide(_rows(v, c), "cat_only")["outcome"] == "NO EVIDENCE IT HELPS"


def test_no_evidence_when_vetoed_events_do_better():
    v = [0.10 + 0.001 * i for i in range(20)]
    c = [0.02 + 0.001 * i for i in range(60)]
    assert decide(_rows(v, c), "cat_only")["outcome"] == "NO EVIDENCE IT HELPS"


def test_too_few_vetoes_is_inconclusive_not_a_pass():
    d = decide(_rows([-0.5] * 14, [0.1] * 60), "cat_only")
    assert d["outcome"] == "INCONCLUSIVE"


def test_errors_are_named_and_excluded_never_cleared():
    d = decide(_rows([-0.5] * 14, [0.1] * 60, errors=3), "cat_only")
    assert len(d["errors"]) == 3 and d["n_not_veto"] == 60
