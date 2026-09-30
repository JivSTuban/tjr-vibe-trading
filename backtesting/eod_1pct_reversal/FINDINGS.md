# EOD 1% Previous-Low Reversal — backtest findings

**Verdict: REJECT as specified.** The gate stack is worth **+1.28 bps per trade**
over buying a random liquid stock the same afternoon (t = 1.14, n = 3,128 sessions),
and the strategy needs **2.85 bps per side** just to break even. One component —
late-session pressure — is the only part with a real claim, and it is the one part
that cannot be measured over history. It is **unproven, not disproven**.

Spec: `EOD_1Percent_Codex_Skill_Automation_Design.pdf` v1.0, September 2026.
Run: `backtesting/eod_1pct_reversal/`, 14 tests, 2026-09-19.

---

## What was tested

| | Long history | Literal spec |
|---|---|---|
| Window | 2014-01-02 → 2026-09-09 | 2026-06-18 → 2026-09-14 |
| Sessions | 3,190 | 57 |
| Universe | 630 point-in-time S&P 500 names | 515 names with 5m bars |
| Ticker-sessions | 1,864,469 (1,599,140 liquid) | 28,962 |
| 15:50 signal | **proxied by the close** | **the actual 15:50 bar open** |
| Entry | close | 15:55 bar open |
| `late_return` gate | unavailable | measured |

Free intraday history is 60 days (Yahoo), so there is no window where the literal
spec and a meaningful sample size coexist. Both runs share one feature contract and
one execution model; the runner names every substitution rather than degrading
silently.

**Proxy error, measured not assumed** (n = 29,058 overlapping ticker-sessions):
the close sits **1.26 bps below** the 15:50 price on average (median −1.40, σ 36.31)
and **0.75 bps below** the 15:55 entry. The long-history run therefore *overstates*
the edge by roughly 0.75 bps — about 13% of it.

## The headline

Spec configuration (§12 defaults), T+1, 2014-2026:

| | n | hit rate | gross | net @2bps | net @5bps | net @10bps |
|---|---|---|---|---|---|---|
| **Spec config** | 102,052 | 52.9% | **+5.69 bps** | +1.69 | −4.31 | −14.31 |
| Control: any liquid name | 1,549,730 | 47.4% | +5.17 bps | +1.17 | −4.83 | −14.83 |

**The entire four-filter stack is worth +0.52 bps over buying literally anything**,
while discarding 93.4% of candidates. Break-even is **2.85 bps per side**. A retail
round trip in liquid US equities is not reliably under that.

This reproduces the sibling study (`eod_pressure_reversal`) almost exactly, which
found its six-filter stack worth +0.77 bps over "buy any red name" and broke even at
2.83 bps/side. Two different specs, two different gate sets, the same answer: the
filters are selecting the market, not the stock.

## The three findings that matter

### 1. The +1% target earns less than doing nothing with it

The spec's own §6.2 close→open control — same names, no target, exit at the next
open — beats the whole target-and-time-stop machinery:

| | T+1 with +1% target | close → open control |
|---|---|---|
| Spec config | +5.69 bps | **+5.84 bps** |
| Any liquid name | +5.17 bps | +4.13 bps |

The +1% cap truncates the winners and the time stop eats what is left. And the
control's **+4.13 bps on any name at all** is the market-wide overnight drift, which
is most of the +5.69 the strategy reports. The strategy is a holding period, not a
signal.

### 2. The hit rate improves while the P&L does not

The gates lift the +1% hit rate from **47.4% → 52.9%**, exactly as designed. Gross
expectancy moves +5.17 → +5.69 bps. The extra wins are paid for by bigger losses:
average MAE is **−124 bps** to capture +100.

This is the same trap banked in `memecoin-exit-policy-findings`, where win rate and
P&L correlated **−0.486**. Optimising the thing a +1% target makes look good is how
you pick the worst rule in the set. **Do not rank configurations by hit rate.**

### 3. Every threshold in the spec's own sweep is a plateau at zero

Spec §7's promotion rule asks for a broad stable region rather than one lucky
threshold. Sweeping §3.2's stated ranges, one parameter at a time, session-weighted
excess over the same-afternoon control:

| parameter | range swept | excess (bps) | t |
|---|---|---|---|
| prev-low band max | 0.25 … 1.50% | +1.07 … +1.50 | 0.95 … 1.28 |
| day return max | −0.50 … −2.00% | +0.07 … +1.50 | 0.04 … 1.28 |
| close location max | 0.20 … 0.50 | +0.49 … +1.50 | 0.47 … 1.28 |
| range capacity min | 1.0 … 2.5% | −0.28 … +1.71 | −0.18 … 1.28 |

It is a genuinely broad, genuinely stable plateau. It sits at zero. **No cell in the
entire sweep reaches significance**, so there is no threshold to promote and nothing
here was tuned.

## The one open question: late-session pressure

On the 57-day intraday window the `late_return` gate is the only thing that moves the
number, and it moves it hard: adding it takes T+1 from **+8.87 → +38.30 bps**. This
is also the one gate the spec's academic source ([12] Baltussen, Da & Soebhag) is
actually about.

It does not survive scrutiny at this sample size:

- **90.2% of the spec config's return lands on three sessions**; 52.6% on one.
  Removing the single best session takes T+1 from +31.48 → +16.14 bps.
- The strategy fires **~8 names per afternoon**, so a good day is one bet in eight
  tickers, not eight observations. Trade-weighted t = 2.12; **session-weighted
  t = 0.37**. Where those disagree, the session-weighted one is right. This is the
  correlated-beta failure from `stock-scan-performance-audit` (5 of 7 stops died on
  two days) in a new costume.
- **The window itself is rich.** The ungated control earns +8.17 bps on these 57 days
  versus +5.17 over 12.7 years, and decays from +13.00 in the first half to +3.36 in
  the second.

The decisive cross-check: `L2_red` at T+3 (a rung with **no** late gate, so it is
measurable in both runs) shows **+14.63 bps session-excess (t = 2.27) on 54 sessions**
and **−0.27 bps (t = −0.23) on 3,157 sessions**. The 60-day window flatters *every*
rung by roughly that margin. That is the strongest available evidence that the late
gate's apparent edge is the window, not the filter — but it is evidence, not proof,
because the late gate itself was never in the long run.

**So: unproven, not disproven.** The honest way to settle it is forward paper signals
(spec §18 step 10), which costs nothing but time. It is not settled by loosening a
threshold or by re-running the 60 days.

## What would have to be true to revisit this

1. **Intraday history beyond 60 days.** Alpaca's free tier (the spec's own primary
   provider, §4.1) serves minute bars further back than Yahoo. That is the single
   unlock — it converts the late-pressure question from unanswerable to answerable.
2. **Costs demonstrably under ~2.5 bps/side**, evidenced by real fills, not assumed.
3. **A same-session excess that survives session weighting**, not trade weighting.

Absent all three, this is a signal-only email that reports the overnight drift.

## Engineering notes (things that would have produced a fake result)

- **Gap before touch.** If the next session opens above the target, the fill is the
  open, not a tidy +1.00%. Pinned by `test_gap_open_above_target_fills_at_the_open`.
- **Splits.** Ratios are computed on split-adjusted prices; a 2:1 split otherwise
  prints a −50% "distance to yesterday's low" and manufactures a perfect setup. The
  split session and the one before it are dropped.
- **Unfinished trades are dropped, not truncated** to the last close.
- **A NaN feature never passes a gate.** On the daily path `late_return` is always
  NaN, so the gate is *removed from the rung and the rung renamed* (`L5_range-late`)
  rather than silently evaluating False — which in the first run deleted the spec's
  own configuration from the output table. A gate that cannot fire is
  indistinguishable from a quiet market; see `trap-a-signal-that-cannot-fire`.
- **MAE is measured only up to the exit**, so a crash after the target filled is not
  charged to the trade.
- **Earnings blocking is horizon-aware.** Unknown report times block both sides,
  because Nasdaq leaves the flag empty on historical rows.
- **Survivorship.** Point-in-time S&P 500 membership only. 154 of 784 tickers had no
  cached prices and are disclosed, not quietly dropped. The EXTENDED universe was
  deliberately not blended in; the sibling study showed it doubles the headline.

## Reproduce

```bash
PYTHONPATH=. uv run pytest backtesting/eod_1pct_reversal/tests/ -q
PYTHONPATH=. uv run python -m backtesting.eod_1pct_reversal.run --mode daily --sweep
PYTHONPATH=. uv run python -m backtesting.eod_1pct_reversal.run --mode intraday
PYTHONPATH=. uv run python -m backtesting.eod_1pct_reversal.analyze   # concentration
PYTHONPATH=. uv run python -m backtesting.eod_1pct_reversal.excess    # session excess
```

Outputs land in `runs/`.

---

# ADDENDUM 2026-09-19 — the open question is closed. The late gate is negative.

The body of this document had to leave one thing unresolved: `late_return`, the
15:30 -> 15:50 pressure gate, was the only component that moved the number and the
only one no free data could measure over history. Alpaca's Basic plan turned out to
serve consolidated-tape minute bars **back to 2016**, so it is now measured.

**It does not merely fail to help. It actively destroys value, significantly.**

## What was run

598 randomly sampled sessions from 2016-2026, **144,076 ticker-sessions**, real
1-minute consolidated-tape bars. Features computed at the open of the 15:50 bar —
a price that exists at 15:50:00 — using only bars opening at or before 15:49.

## Result: excess over the same afternoon's control, session-weighted

| Rung | T+1 | T+3 | T+5 |
|---|---|---|---|
| 1 · near previous low | **+2.35** (t 2.53) | **+3.49** (t 3.29) | **+4.65** (t 3.13) |
| 2 · + red on the day | +1.59 (t 0.97) | +0.89 (t 0.44) | +2.40 (t 0.99) |
| 3 · **+ late pressure** | **−3.04** (t −0.55) | **−10.91** (t −1.34) | **−17.89** (t −1.87) |
| 4 · + near today's low | −3.91 (t −0.69) | −12.00 (t −1.48) | −20.76 (t −2.12) |
| 5 · + range capacity (**spec default**) | −4.12 (t −0.68) | −11.67 (t −1.37) | **−21.11 (t −2.03)** |

Fill at 15:51. Every number is basis points per trade against the other stocks
available that same afternoon, weighting each afternoon once.

**The spec's own configuration is significantly worse than random at T+5.** Each
filter the spec adds after the first one subtracts, and the one it leans on hardest
subtracts the most.

## The 57-day window was the window, not the filter

The body reported the late gate at **+36.04 bps (t 2.33)** at T+3 on 57 days of Yahoo
5m bars, with the caveat that 90% of it sat on three sessions. On 598 sessions of real
minute data the same rung is **−10.91 (t −1.34)**. A complete sign flip.

That is the whole lesson of this study in one line: **the 57-day sample did not
understate the uncertainty, it inverted the sign.** The cross-check flagged it (a
no-late-gate rung showed +14.63 bps there and −0.27 over 3,157 sessions) but could
not prove it. Now it is proven.

## Only the loosest rung survives, and not by enough

"Near the previous day's low" on its own is genuinely positive and stable across
horizons (+2.35 / +3.49 / +4.65 bps, t 2.5-3.3, ~57-59% of sessions positive). But at
T+1 it grosses **4.84 bps** against a break-even of ~2.85 bps **per side** — so it
does not survive its own costs. At T+5 it nets +5.41 bps at 5 bps/side, over a 2.55
day hold, on a rung that fires ~131 names a day. That is an index fund with extra
steps and extra risk, not a signal.

## Price is moving — measured, and it corrects an earlier claim

An interim note from a 12-session pilot put the drift from the 15:50 print to a 15:55
fill at **−6.9 bps**. On the full 144,076-row sample that is wrong. The mean drift is
approximately **zero**:

| Fill | Mean | Median | p10 | p90 |
|---|---|---|---|---|
| 15:51 | +0.82 | +0.69 | −14.54 | +16.00 |
| 15:52 | +0.34 | 0.00 | −18.38 | +19.12 |
| 15:55 | +0.28 | +1.02 | −26.05 | +26.94 |
| 16:00 | −0.18 | 0.00 | −36.18 | +34.95 |

**The delay does not cost you on average. It buries you in variance.** By 15:55 the
p10-p90 spread is ±26 bps around a gross edge of 1-5 bps: the execution noise is five
to twenty times the signal. A strategy whose edge is smaller than the uncertainty of
its own fill is not tradable regardless of what the mean says.

This is also why the earlier daily-proxy run looked better than reality. Proxying
15:50 with the close produced 5.69 bps at the spec config; the true 15:50 signal
grosses **1.00 bps**.

## Bug found and fixed while doing this

Entry prices come from Alpaca and exits from the Yahoo daily cache, so the two must
agree on what a share cost. On 48 of 3,357 pilot rows they disagreed by up to **9.6x**
— GE, RTX, CNX, BDX: spin-offs and reverse splits the two providers adjust
differently. Each books a fake −90% trade, and together they dragged the **control**
to −103 bps when its real value is near +0.2. Now guarded by a cross-source agreement
check (`drop_price_basis_mismatches`, tolerance 5%, reported never silent) and two
tests. Healthy rows agree to within 0.07%.

## Verdict, final

**REJECT, and more firmly than before.** The price-pattern spec has no edge; its
signature filter has a negative one; and its execution assumption dissolves into noise
an order of magnitude larger than anything it is trying to capture.

What is NOT rejected, because it was never tested: a version where candidates are
chosen by research (§4 news/event risk, §5 empirical ranking) rather than by this
price pattern. That cannot be backtested honestly — any model reading 2019 news today
knows how 2019 ended — so the only sound test is forward paper signals, which is the
spec's own §18 step 10.
