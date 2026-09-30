# Re-test of the banked n=39 result (insider cluster + earnings catalyst)

**Banked claim (FINDINGS.md, 2026-08-06):** insider cluster + a coincident earnings beat = 60d
median **+11.15%**, 67% hit, **n=39**, vs catalyst-only +1.92% and insider-without-catalyst +1.53%.

**Why re-test (2026-09-30).** `docs/research/INSIDER_CATALYST_AI_REVIEW.md` found that both halves
fail independently outside microcaps in the literature, so the result is most likely a small-cap,
small-sample artifact. Reading `catalyst.py` added a sharper suspicion: the catalyst date is not
the real announcement. It is `fiscal period end + 35 days`, and `had_beat_near` accepts a beat up
to 5 days AFTER the insider filing. Small caps often report 40 to 90 days after period end, so a
"coincident" beat may have been announced during the hold, i.e. unknowable at entry.

## Decision rule (written BEFORE running anything)

The corrected spec applies all four fixes at once:
1. **Point-in-time catalyst:** the beat must be publicly announced (first 8-K Item 2.02, 10-Q or
   10-K filed after the fiscal period end, from SEC EDGAR) **on or before** the insider event date.
2. **Entry at the t+2 open** instead of t+1.
3. **Ex-microcap:** market cap at the event (EDGAR shares outstanding filed before the event x
   close) at or above the cutoff stated in the results.
4. **Realistic small-cap cost:** 150 bps round trip (the research measured a 133 bps median spread
   for insider-purchase names), reported beside the original 30 bps.

**The banked claim SURVIVES only if, in the fully corrected spec at 60d, all three hold:**
- (a) n >= 20
- (b) the insider + catalyst 10%-trimmed mean is > 0 net of 150 bps
- (c) the insider + catalyst median beats the catalyst-only median (same corrections) by >= 3pp

**Otherwise it is DOWNGRADED to "not established"**, and `/stock-scan` stops citing
+11% / 67% / n=39 as evidence. No re-tuning of windows or cutoffs after seeing results.

Each fix is also applied one at a time (a ladder), so the report shows which fix moves the number.

## Results (run 2026-09-30, `python -m backtesting.insider_cluster.retest_n39`)

> **CORRECTED 2026-10-01 (see "Correction 2026-10-01" below): on matured trades check (c) FAILS and the claim is downgraded. The original verdict is kept here for the record.**

**Verdict under the pre-committed rule: SURVIVES, at less than half the banked size, and fragile.**
The corrected edge is **+4.79% median / +8.26% trimmed mean net of 150 bps, 67% hit, n=24**, not
+11.15%. Stop citing +11% / n=39.

### The ladder (60 trading days)

| Rung | ins + cat n | median | trim10 | hit | cat-only median | diff | 90% boot on diff |
|---|---|---|---|---|---|---|---|
| L0 replica (t+1, guessed date, 30 bps) | 39 | +11.15% | +12.98% | 67% | +1.92% | +9.23% | [+0.32, +15.18] |
| L1 + real announcement date | 41 | +9.72% | +12.05% | 68% | +1.95% | +7.78% | [+1.41, +13.82] |
| L2 + t+2 open | 41 | +6.01% | +9.55% | 68% | +2.62% | +3.39% | [-2.03, +10.25] |
| L3 + ex-microcap (NYSE p20, ~$1B) | 24 | +5.99% | +9.46% | 71% | +2.46% | +3.54% | [-1.66, +8.36] |
| **L4 + 150 bps round trip** | **24** | **+4.79%** | **+8.26%** | **67%** | **+1.26%** | **+3.54%** | **[-1.66, +8.36]** |

Rule at L4: (a) n=24 >= 20 PASS · (b) trim10 +8.26% > 0 PASS · (c) diff +3.54pp >= 3pp PASS.

### What each fix did
- **The look-ahead suspicion was mostly wrong.** Real SEC filing dates put **38 of the 39 beats
  before the insider filing**; only TECX (+23%) was announced after. L1 barely moves the number.
- **The t+2 open is the biggest single cut** (median +9.72% to +6.01%). Much of the move lands in
  the first session after the filing, matching the research (3.27 of 6.9 points in that session).
- **Ex-microcap halves n but not the median.** The set was never mostly microcaps: AVTR, NDAQ,
  KKR, AMH, ADC, LW, RYAN, MIDD are all well above $1B.

### It is not "coincident" either
Insiders bought a median **27 days after** the beat was announced (range 4 to 78). The real setup
is **"insiders buy 1 to 11 weeks after a public earnings beat"**, which the scanner can check
point-in-time. The catalyst gate should look back for a beat that is already public, not wait for
one.

### Stress tests (not pre-committed; they qualify the verdict)
| Change | n | median | diff vs cat-only | rule |
|---|---|---|---|---|
| as run | 24 | +4.79% | +3.54% | PASS |
| drop ABCL (only 5% above the cutoff) | 23 | +4.36% | +3.10% | PASS |
| drop the top winner (AVTR +61%) | 23 | +4.36% | +3.10% | PASS |
| **drop the top two (AVTR, RIG)** | 22 | +3.53% | +2.27% | **FAIL** |
| drop all borderline-cap names | 18 | +3.97% | +2.71% | **FAIL** |

- **The insider layer's added value is not statistically distinguishable from zero**: the 90%
  interval on the median difference is [-1.66%, +8.36%]. My pre-committed rule used a point
  threshold and did not require significance; in hindsight that bar was too low. It is recorded
  here rather than changed.
- **Against a timing-matched control it looks stronger.** Catalyst-only beats entered at the same
  delays after the announcement (4 to 78 days) earn a median **-0.04%** (trim10 +1.02%), versus
  +4.79% for the insider arm. Diagnostic only.
- The insider + catalyst median itself is only just above zero at 90%: [+0.04%, +9.26%].
- One vote per ticker (20 tickers; ALKT appears 3 times, KKR and REZI twice): median +4.28%.

### The most robust finding: a bare insider buy LOSES
Insider cluster **without** a prior beat, ex-microcap, net of 150 bps: **n=54, median -3.04%,
41% hit.** This is the cleanest number in the re-test and it hardens the existing rule: never
trade an insider buy that lacks a catalyst.

### Limits
- **One regime.** Every catalyst-arm event falls between Aug 2025 and Jul 2026 (Finnhub free only
  covers ~4 quarters), a strong tape. Unknown in a bear market.
- **Market cap** uses SEC share counts filed before the event (11,342 lookups) with Yahoo's dated
  share history as the fallback (1,886; multi-class issuers and recent IPOs); 4 lookups unpriced.
  Yahoo prices are split-adjusted while SEC shares are as-filed, so a name that split after its
  event is understated; checked names within 2x of the cutoff (ABCL, ALKT, FRSH, PLSE).
- Survivorship: Yahoo has no delisted names. Small effect here (recent, mostly large caps).

### What changes
1. Cite **+4.8% median / +8.3% trimmed / 67% hit, n=24 (net, ex-microcap, t+2)**, one bull year,
   instead of +11.15% / n=39.
2. Treat the insider cluster as a **filter that may add ~3-5pp over the catalyst alone, unproven
   at 90%**, not as a proven multiplier.
3. The gate is "a beat **already public**, within the last ~90 days", and the bare-insider case is
   now measured negative.
4. Forward test: the same rule on live `/stock-scan` output. Kill it if the ins + cat median over
   the next 30 graded setups (ex-microcap, t+2, net) does not beat the catalyst-only median by 3pp.

## Correction 2026-10-01: the banked L4 numbers included trades with no 60-day window

`fwd()` clamps the exit to the last available bar, and the frozen OHLC stops at 2026-08-06. So the
"60d" returns above include trades entered as late as 2026-07 (5 of the 24 ins + cat trades, 12 of
the 54 ins-nocat, 58 of the 262 catalyst-only). Found while building the forward tracker.
Re-scored on MATURED trades only (a full 60-bar window after the t+2 open), with prices refreshed to
2026-09-30 for the 79 tickers that had an immature trade (`forward_n39.py --retest-window`, which
reproduces this table; the parity test proves the event definitions are identical to the ladder):

| Arm (L4: ex-microcap, t+2, 150 bps) | Banked (clamped) | Matured, refreshed |
|---|---|---|
| ins + cat | n=24, +4.79% median, +8.26% trim, 67% hit | **n=23, +5.23%, +8.17%, 70%** |
| catalyst-only | n=262, +1.26% | **n=221, +3.25%, 53%** |
| insider, no beat | n=54, -3.04%, 41% | **n=54, -2.61%, 43%** |
| difference ins + cat minus catalyst-only | +3.54pp | **+1.99pp, 90% boot [-3.48, +6.81]** |

Pre-committed rule on the matured numbers: (a) n >= 20 PASS (23) · (b) trim10 > 0 PASS (+8.17%) ·
**(c) diff >= 3pp FAIL (+1.99pp)**. Under the rule as written, the banked claim is **DOWNGRADED to
"not established"**. The original SURVIVES verdict above came from the clamped trades: the 58
immature catalyst-only trades held that arm's median down to +1.26%, which inflated the gap.

What this does and does not say:
- The insider layer adds about 2pp over a public beat, with an interval that includes zero. It is
  not proven to add anything. Stop citing "cluster + beat" as validated; cite "a public beat in the
  last ~90 days, ex-microcap" as the operative gate and the insider cluster as unproven confirmation.
- The beat requirement itself is the robust part: insider + beat +5.23% (n=23) against insider with
  no beat -2.61% (n=54), a gap of 7.8pp on clean counts. A bare insider buy stays a refuse.
- The catalyst-only arm is +3.25% net and 53% hit over 2025-06..2026-09, a strong bull stretch and
  with no market-relative control here. Do not read it as a standalone edge either.
- 1 ins + cat trade (NTSK, entered 2026-07-14) is still immature and matures 2026-10-07.

## Forward test protocol (pre-registered 2026-10-01, before any forward event has matured)

Code: `forward_n39.py` (`uv run python -m backtesting.insider_cluster.forward_n39`), tests in
`tests/test_forward_n39.py`. It keeps scoring the L4 definitions above on events dated on or after
**2026-09-01** (the first month the re-test never saw). Frozen now; do not move it after looking.

- **Not journaled picks.** The control arm (catalyst-only) is every beat event in the universe, so a
  cohort of ranked `/stock-scan` picks would compare a selected arm with an unselected one. The
  forward test re-runs the same event definitions instead.
- **Binding rule, unchanged from above:** at 30 graded insider + catalyst events, KILL the insider
  requirement if the ins + cat median does not beat the catalyst-only median by >= 3pp (ex-microcap,
  t+2 open, 60 trading days, 150 bps). Below 30 it reports PENDING. From 8 events in both arms it
  prints an interim median difference and a 90% bootstrap interval, which is NOT binding.
- **Graded means a full 60-bar window exists after the t+2 open.** Anything younger is PENDING and
  listed with its expected maturity date. A trade is never graded on a clamped exit.
- **Named drops.** Microcap, no-market-cap, no-price and stale-price events are listed by ticker and
  date. A source failure exits non-zero. The frozen caches are never read or written (they stop at
  2026-08 and would report a confident "no new events"); the tracker uses `.cache/forward/` with a
  20-hour TTL.
- **Timeline, measured not guessed.** The re-test found 24 ins + cat events over 2025-06..2026-08
  (7 in 2025, 17 in 2026 through August, about 2 a month) against 262 catalyst-only events. Thirty
  ins + cat events therefore arrive in roughly 15 months and each needs 60 trading days (about 3
  months) to mature: **the binding rule cannot fire before about early-to-mid 2028.** The interim line is
  the only early signal. Shortening the wait means changing the rule (a lower n or an interval-based
  stop), which is Jiv's call and must be written here BEFORE the data it would judge.
