from backtesting.insider_cluster import veto_replay as V


def test_run_one_caches_and_a_crash_is_an_error_row_never_a_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "_CACHE", str(tmp_path))
    calls = []
    ok = lambda t, d: (calls.append((t, d)), {"ticker": t, "verdict": "VETO", "rows": [], "unknowns": []})[1]
    assert V.run_one("AAA", "2026-01-05", runner=ok)["verdict"] == "VETO"
    assert V.run_one("AAA", "2026-01-05", runner=ok)["verdict"] == "VETO"
    assert calls == [("AAA", "2026-01-05")], "second call must come from the cache"

    def boom(t, d):
        raise RuntimeError("claude exit 1")
    e = V.run_one("BBB", "2026-01-06", runner=boom)
    assert e["verdict"] == "ERROR" and "claude exit 1" in e["error"]
    assert not (tmp_path / "BBB_2026-01-06.json").exists(), "an error must not be cached as a result"


def test_summarize_groups_by_arm_and_verdict_and_names_errors():
    rows = [
        {"arm": "ins_cat", "ticker": "A", "date": "d1", "ret": 0.10, "verdict": "CLEAR"},
        {"arm": "ins_cat", "ticker": "B", "date": "d2", "ret": -0.20, "verdict": "VETO", "why": "CONVERTIBLE_ISSUANCE"},
        {"arm": "ins_nocat", "ticker": "C", "date": "d3", "ret": 0.05, "verdict": "CAVEAT"},
        {"arm": "ins_cat", "ticker": "D", "date": "d4", "ret": 0.30, "verdict": "ERROR"},
    ]
    s = V.summarize(rows)
    assert s["stats"][("ins_cat", "VETO")]["median"] == -0.20
    assert [r["ticker"] for r in s["vetoed"]] == ["B"]
    assert s["errors"] == [("D", "d4")], "an errored event is excluded by name, not counted as clear"
    assert "CONVERTIBLE_ISSUANCE" in V.render(s)


def test_why_reads_only_veto_class_confirmed_or_provisional_findings():
    res = {"rows": [
        {"status": "CONFIRMED", "cls": "VETO", "label": "EQUITY_ISSUANCE", "amount": "$50 million"},
        {"status": "EXPLAINED", "cls": "CLEAR", "label": "NON_DILUTIVE_DEBT"},
        {"status": "PROBABLE", "cls": "VETO", "label": "GOING_CONCERN"},
    ]}
    assert V.why(res) == "EQUITY_ISSUANCE $50 million"
