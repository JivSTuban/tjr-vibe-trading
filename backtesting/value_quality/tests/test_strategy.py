import pandas as pd
from backtesting.value_quality.strategy import ValueQualityCfg, select_holdings

def _cand():
    return pd.DataFrame({
        "value_score":[0.95,0.90,0.80,0.20,0.85],
        "fscore":     [8,   7,   9,   9,   5   ],
        "drop_fired": [True,True,True,True,True],
    }, index=["A","B","C","D","E"])

def test_selects_only_all_three_gates():
    cfg = ValueQualityCfg(value_top_frac=0.6, max_names=10)
    picks = set(select_holdings(_cand(), cfg))
    assert picks == {"A","B","C"}   # D fails value (0.20), E fails quality (F=5)

def test_respects_max_names_by_value():
    cfg = ValueQualityCfg(value_top_frac=1.0, max_names=2, f_min=7)
    picks = select_holdings(_cand(), cfg)
    assert picks == ["A","C"] or picks == ["A","B"]  # top-2 by value among F>=7 & dropped
    assert len(picks) == 2

def test_empty_when_no_drop():
    c = _cand(); c["drop_fired"] = False
    assert select_holdings(c, ValueQualityCfg()) == []
