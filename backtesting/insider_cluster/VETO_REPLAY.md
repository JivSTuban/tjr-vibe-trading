# Replay of the 8-K/6-K veto on historical insider + beat events (2026-10-01)

**Question.** Among the re-test's insider events that already have a public beat (the only names
that reach the veto in production, because a bare insider buy is refused first), did the events
`stock-scan/engines/veto_extract.mjs` would have vetoed do worse over the next 60 trading days?

**Method.** `uv run python -m backtesting.insider_cluster.veto_replay` (prompts and taxonomy exactly
as shipped, pass 1 Sonnet, pass 2 Haiku). Each event is run `--asof <event date>`: filings made after
the event are excluded by an upper bound (tested), so the veto never sees the future. Returns are the
matured L4 returns from `forward_n39` (full 60-bar window, t+2 open, 150 bps, ex-microcap). 23 events,
2025-06 to 2026-08, 0 errors, $8.61 of model usage. None of GME / RWT / ADC-notes / INR (the cases the
prompts were written against) is in this sample.

## Result

| Veto verdict | n | median 60d net | hit |
|---|---|---|---|
| CLEAR | 9 | +6.64% | 67% |
| CAVEAT | 9 | +4.36% | 67% |
| VETO | 5 | +5.23% | 80% |

| Vetoed event | As of | 60d net | What the veto read |
|---|---|---|---|
| ADC | 2026-05-19 | -2.74% | ATM agreement (up to $1.75B) plus forward sales of ~8.3M shares |
| ALMS | 2026-01-13 | +2.70% | 17.65M-share public offering, $345M |
| MLYS | 2025-09-08 | +5.23% | upsized underwritten offering, 9.8M shares at $25.50 |
| RIG | 2025-11-25 | **+54.96%** | 125M-share public offering at $3.05, $381M, priced 2025-09-25 |
| PLSE | 2026-05-15 | **+71.78%** | ATM sales agreement up to $59.98M |

## What this says, and what it does not

- **The extraction is right.** Every vetoed quote is a real completed or established equity raise
  (checked against the filing text). The tool is a sound detector of dilution.
- **As a veto it did not help here.** There is no gradient across verdicts (+6.6 / +4.4 / +5.2),
  and the two largest winners in the sample were vetoed. Blocking all five would have avoided one
  small loss (ADC -2.74%) and given up +55% and +72%.
- **All five are equity-raise classes** (EQUITY_ISSUANCE, EQUITY_LINE_OR_ATM_AGREEMENT). Nothing in
  this sample exercised going-concern, non-reliance, default, listing-deficiency, exchange-for-equity
  or convertible labels, so this replay says nothing about them.
- **n = 5 vetoes is an anecdote, not a test.** It cannot show the veto hurts, only that there is no
  evidence it helps on this population. It conflicts with, and does not overturn, the DD gate's own
  record (12 vetoes, average -1.4%, 0 winners missed), which used a different population.
- **Likely reading, not tested:** a raise that has already priced and funds a runway is stale news,
  and insiders buying after it is a positive, unlike an imminent raise. Do not turn that into a
  rule (an age cutoff or a size-vs-market-cap test) from five events; it needs a larger replay.

## Decision

`SKILL.md` I5-DD item 1 called the tool's verdict **binding**. That claim was made before any replay
and is not supported for the equity-raise classes. It is narrowed: a VETO on EQUITY_ISSUANCE or
EQUITY_LINE_OR_ATM_AGREEMENT is a strong presumption the DD must weigh and may overrule with a named
reason (what the money is for, how old the raise is, how the stock reacted); every other VETO class
stays binding. Revisit when a larger replay exists: extend `veto_replay --arms ins_cat,ins_nocat`
after the forward tracker has more matured events, or replay the catalyst-only arm.

## Pass-2 engine: Codex vs Haiku (2026-10-01)

Ran `veto_extract.mjs <T> --json` (Haiku pass 2, the default) and `--p2 codex` on GME RWT ADC UBER INR
GIII APTV GRAB. Pass 1 and the prompts are identical, so any difference is the pass-2 model.

- **Verdict: 7 of 8 tickers agree, 1 flips.** GME is VETO on Haiku and CAVEAT on Codex.
- **Row status: 6 of ~20 graded rows differ** (GME 3, RWT 2, INR 1). Every difference is Codex
  grading LOWER (CONFIRMED to PROBABLE or REJECTED); none goes the other way.
- **Why:** Codex reads ordinary closing conditions ("subject to customary conditions", "may be
  terminated") as `contradicted_nearby`, and judges the quoted span alone. It REJECTED "a maximum of
  56,473,810 shares may be issued upon conversion of the Notes" (RWT) and "the Existing Noteholders will
  receive approximately 55.5 million shares" (GME) as "not an actual issuance". Both are real events:
  the GME 8-K states the exchange completed 2026-09-03, and the RWT 8-K is the 2026-09-15 indenture for notes already issued.
- **Decision:** Haiku stays the default (it matches the known outcome on both flipped names).
  `runCodex` and `--p2 codex` are KEPT as a stricter second opinion, per the pre-agreed rule (any label
  disagreement keeps Codex). Do not treat a Codex REJECTED on an announced-but-unclosed deal as
  evidence the event did not happen.
- **Side finding: pass 1 is not deterministic across runs.** ADC's label changed
  (EQUITY_LINE_OR_ATM_AGREEMENT vs EQUITY_ISSUANCE) and GRAB returned 7 rows vs 6, with the same model
  and prompt. The two ADC labels land in the same VETO class, so the verdict held; it is unmeasured
  how often this crosses a class boundary.
- **Not tested:** whether Codex's stricter grading ever catches a false VETO. n=8 names, no outcome
  labels beyond GME/RWT.
