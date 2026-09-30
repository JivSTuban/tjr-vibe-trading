# eod_1pct_reversal

Backtest of `EOD_1Percent_Codex_Skill_Automation_Design.pdf` v1.0 — buy a liquid US
stock at 15:50 ET when it is red, weak into the bell, and near its **previous day's
low**; target +1%.

**Verdict: REJECT as specified.** Read [`FINDINGS.md`](FINDINGS.md). Short version:
the gate stack beats "buy any liquid stock the same afternoon" by **+1.28 bps
(t = 1.14)** while needing **2.85 bps/side** to break even, and the spec's own
close→open control earns *more* than its +1% target machinery.

## Layout

| file | role |
|---|---|
| `features.py` | Spec §3.2 features. `daily_features` (12.7y, close-proxied) and `intraday_features` (60d, the literal 15:50 bar). One contract, two regimes. |
| `strategy.py` | §3.2 hard gates + the §7 incremental ladder. `ladder_for()` removes an unmeasurable gate from a rung and renames it, rather than dropping the rung. |
| `execution.py` | §6 contract: gap-before-touch fills, time stops, close→open control, costs. |
| `run.py` | Orchestrator. `--mode daily\|intraday`, `--sweep`. |
| `analyze.py` | Concentration + stability stress on the intraday result. |
| `excess.py` | Same-session excess return, session-weighted. |

## Why it reuses `eod_pressure_reversal`

Prices, 5m bars, PIT universe, earnings calendar and metrics are imported from the
sibling package. That study already solved the Yahoo bar convention, the split trap
and point-in-time membership, and its caches (582 MB daily, 239 MB intraday, 3,190
earnings days) are the same data this one needs. A second copy would rot separately.

## Run

```bash
PYTHONPATH=. uv run pytest backtesting/eod_1pct_reversal/tests/ -q
PYTHONPATH=. uv run python -m backtesting.eod_1pct_reversal.run --mode daily --sweep
PYTHONPATH=. uv run python -m backtesting.eod_1pct_reversal.run --mode intraday
PYTHONPATH=. uv run python -m backtesting.eod_1pct_reversal.analyze
PYTHONPATH=. uv run python -m backtesting.eod_1pct_reversal.excess
```

`PYTHONPATH=.` is required — the repo root is not an installed package.

## The one thing left open

The `late_return` gate (15:30 → 15:50 pressure) is the only component that moves the
number, and 60 days of free intraday history is the only place it can be measured.
Settle it with forward paper signals or with a longer minute-bar source (Alpaca free
tier), **not** by re-running the 60 days or loosening a threshold.
