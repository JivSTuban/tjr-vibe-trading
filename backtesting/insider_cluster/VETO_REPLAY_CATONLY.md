# Replay of the 8-K/6-K veto on the catalyst-only arm (pre-registered 2026-10-01)

**Question.** Across the catalyst-only events (a public beat, no insider requirement; the re-test's
`cat_only` arm, the largest matured sample we have), did the events `veto_extract.mjs` would have
vetoed do worse over the next 60 trading days than the events it did not veto?

The first replay (`VETO_REPLAY.md`, insider + beat arm) had n=5 vetoes and could not answer this. This
arm exists to get a sample where the answer is readable.

## Decision rule (written BEFORE any result; do not edit after the run)

Let `V` = events with verdict VETO, `N` = events with verdict CLEAR or CAVEAT. Returns are the matured
L4 returns from `forward_n39.rescore_retest_window()` (full 60-bar window, t+2 open, 150 bps, ex-microcap),
the same definition as the first replay. Statistic: median 60d net return, `median(N) - median(V)`,
with a 90% bootstrap CI (10,000 resamples, seed 7) on that difference.

| Outcome | Condition | Consequence |
|---|---|---|
| **VETO EARNS ITS PLACE** | `n(V) >= 15` AND difference `>= 3.0pp` AND CI lower bound `> 0` | keep the veto as a filter; consider making the ordinary equity-raise classes binding again |
| **NO EVIDENCE IT HELPS** | `n(V) >= 15` and the condition above fails | veto stays a presumption the DD may overrule; STOP building on it; no tuning on this sample |
| **INCONCLUSIVE** | `n(V) < 15` | same as NO EVIDENCE: do not extend or tune; the veto cannot be shown to earn a place |

There is no rule that turns a bad result into "needs one more tweak". Any filter idea that comes out of
reading the vetoed rows (age of raise, size vs market cap) is a hypothesis for a NEW pre-registered test,
not something to apply to this sample.

## Reported alongside (descriptive, not decision inputs)

- Median, 10% trimmed mean and hit rate per verdict.
- The portfolio effect: median and mean of all events versus all events with `V` removed.
- How many of the top-decile winners were vetoed.
- Events that errored or returned no verdict: named and excluded, never cached; their count.
- Cost: total model spend and cost per event.

## Population note

The catalyst-only names are what `/stock-scan` surfaces first, so unlike the insider + beat arm they DO
reach the veto in production without an insider filter in front of them.
