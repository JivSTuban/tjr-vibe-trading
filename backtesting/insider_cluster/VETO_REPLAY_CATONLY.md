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

---

## Result (run 2026-10-01; the rule above was committed before it ran)

`veto_replay --arms cat_only` then `veto_replay_decide`. 221 events, 0 errors, 33 VETO / 188 not vetoed
(CLEAR 136, CAVEAT 52). Model spend: about $34 for the new events (the whole `.cache/veto_replay` holds
$42.62 including the earlier insider + beat replay).

**Outcome: NO EVIDENCE IT HELPS.** `n(V) = 33 >= 15`, so the rule was decidable, and it failed on both legs:

| | n | median 60d net | mean | trimmed 10% | hit |
|---|---|---|---|---|---|
| VETO | 33 | +2.59% | +8.43% | +3.01% | 52% |
| not vetoed | 188 | +3.36% | +5.26% | +4.00% | 53% |

- `median(N) - median(V) = +0.77pp` (bar: 3.0pp). Bootstrap 90% CI [-8.89pp, +10.68pp], so it spans zero by a
  wide margin.
- **The mean points the other way:** vetoed events average +8.43% against +5.26%, because the right tail
  (MBX +101%, NVTS +164%, GH +64%, ZBIO +58%, SOC +57%) sits in the vetoed set. 5 of the top-decile 22 events
  were vetoed while vetoed events are 15% of the sample.
- **Removing every vetoed event changes almost nothing:** all-event median +3.25% / mean +5.74%, versus
  +3.36% / +5.26% without them.
- **The vetoed set is symmetric, not bad:** 16 losers, 17 winners. Losers include MSTR -59%, NVTS -41%,
  ACET -32%, MLYS -30%; the same issuer and the same $95.6M raise (NVTS) appears at -41% and +164% on two
  dates. The label says a raise happened; it carries no information about where the stock goes next.
- **Caveat on the interval:** 33 vetoed events are 27 issuers (MDLN, KDP, RIVN, RKT, MBX, NVTS repeat) and
  60-day windows overlap, so the bootstrap, which treats events as independent, is too narrow. The true
  interval is wider than shown, which makes the "no evidence" call safer, not weaker.

## Consequence (per the pre-registered table)

- The veto stays a **presumption the DD may overrule**, exactly as `SKILL.md` I5-DD item 1 already says.
  Do not make ordinary equity-raise classes binding again.
- **Stop building on it.** No age-of-raise or size-vs-market-cap filter on this sample; those are
  hypotheses for a NEW pre-registered test, not tweaks to this one.
- The tool remains a sound dilution DETECTOR (every quote checked against filing text in the first replay).
  Its value is putting the raise in front of the DD with a named source, not blocking the trade.
- Combined with `VETO_REPLAY.md` (insider + beat arm, n=5 vetoes, same null), two independent populations
  now agree.
