# EOD Pressure Reversal V1 — FINDINGS

**Status: REJECT. The effect is real but far too small to trade, and most of it is not the
strategy's hypothesis.**

**Run:** 2014-01-01 .. 2026-09-10 · point-in-time S&P 500 (784 member tickers, 637 priced) ·
3,190 sessions · 10,154 trades · entry = signal-day close, exit = next session open ·
plus a 60-day exact-spec intraday calibration (499 tickers, 29,327 sessions).

> The spec's own acceptance test (§17): *"must retain positive expected value and acceptable
> drawdown out of sample after realistic transaction costs."* It fails that test. The gross
> effect is statistically solid and economically negligible.

---

## 1. The headline

| | Gross | 2 bps/side | 5 bps/side | 10 bps/side |
|---|---|---|---|---|
| Mean / trade | **+5.67 bps** | +1.67 bps | −4.33 bps | −14.33 bps |
| Profit factor | 1.140 | 1.039 | 0.905 | 0.718 |
| Sharpe | 0.65 | 0.16 | −0.58 | −1.81 |
| Total return | +239.6% | +12.5% | −78.6% | −98.7% |
| t-stat | **+3.41** | — | −2.61 | — |

Win rate 54.9%, median +6.99 bps, n = 10,154. The gross edge is **statistically significant**
(t = 3.41). It is also **2.83 basis points per side wide** — that is the entire budget for
spread, slippage, and impact, on both legs combined.

For context: 2.83 bps on a $50 stock is **1.4 cents of round-trip execution**, at 3:55 PM and
again in the opening minutes, which are the two least forgiving moments of the session.

## 2. The finding that decides it — the effect is mostly not the strategy

Everything below is gross, so the comparison is like for like.

| What you buy overnight | n | Mean |
|---|---|---|
| SPY | 3,189 | +3.02 bps |
| **Any** liquid S&P 500 name | 1,327,133 | +3.77 bps |
| Any **red** S&P 500 name | 632,643 | +4.89 bps |
| **Full V1: six filters + top-5 ranking** | 10,154 | **+5.67 bps** |

The entire six-filter apparatus is worth **+0.77 bps over "buy any red S&P name"** and +1.90 bps
over "buy literally anything." It discards 98.4% of the candidate trades to earn that.

The base rate here is the well-documented **overnight drift** — US equities earn a
disproportionate share of their return between the close and the open. This strategy is
substantially a repackaging of that, with a selection overlay that adds a rounding error.

## 3. Where each filter actually helps (spec §9, gross)

| Stage | n | Mean | Δ vs previous |
|---|---|---|---|
| 0 any red stock | 632,643 | +4.89 bps | — |
| 1 + DayReturn ≤ −1.5% | 196,170 | +5.03 | +0.14 |
| 2 + late selling | 134,624 | +5.57 | +0.54 |
| 3 + drawdown from high ≤ −2% | 107,895 | +5.16 | −0.41 |
| 4 + sector-relative ≤ −1% | 74,386 | +5.45 | +0.29 |
| 5 + **late volume ≥ 1.5×** | 23,657 | **+3.26** | **−2.19** |
| 6 + no earnings | 21,112 | +4.33 | +1.07 |
| 7 + rank, top 5 | 10,154 | +5.67 | +1.34 |

**The abnormal-late-volume filter is the single most destructive rule in the spec**, and it is
the most distinctive part of the hypothesis. It costs more (−2.19 bps) than any other filter
contributes. The robustness sweep says the same thing monotonically — demanding *more* late
volume makes results *worse* every step of the way (1.25× → −3.22 bps net, 1.5× → −4.33,
2.0× → −5.14).

**This contradicts the core mechanism.** The spec assumes heavy late volume marks *forced,
uninformed* selling that should snap back. The data says the opposite: the heavier the late
volume, the more likely the move was **information**, and information does not reverse overnight.
Heavy late volume is a reason to stay away, not a reason to buy.

Only two components genuinely earn their place: **the no-earnings filter (+1.07)** and **the
cross-sectional ranking (+1.34)**. Both are risk controls, not the thesis.

## 4. The spec as literally written is worse than what we could backtest

The full-history run had to enter at the close and exit at the open. The 60-day intraday
calibration measured both substitutions on real 5-minute bars (n = 3,856 selloff sessions):

| Correction | Effect |
|---|---|
| Modelled: close → next open | **+5.67 bps** |
| Spec enters at 3:55 PM, not the close (close is 1.11 bps cheaper) | −1.11 |
| Spec exits at 9:35, not the open (the first 5 minutes give back 3.96 bps) | −3.96 |
| **The spec's actual rules, gross** | **≈ +0.60 bps** |

**Roughly six tenths of one basis point per trade, before any cost at all.** The spec's own
choice of a 9:35 exit — its stated "practical baseline" — throws away about 40% of the raw
overnight gap. Exiting at the open is materially better, and exiting at 10:00 worse still.

Running the unmodified rules (filters A-E, all measured intraday including sector-relative at
15:50) over the 60-day window produced 109 trades: **−73.8 bps at the open, −39.0 at 9:35,
−4.5 at 10:00**. None statistically significant at n=109, so this is not proof of a negative
edge — but there is no sign of a positive one, in the most recent data, under the exact rules.

## 5. Out of sample — the edge is a regime, not a constant

| Period | n | Win | Gross mean | t | PF |
|---|---|---|---|---|---|
| Development 2014-2021 | 5,987 | 55.0% | +3.53 bps | 1.54 | 1.088 |
| Validation 2022-2024 | 2,529 | 53.5% | +3.94 bps | 1.40 | 1.096 |
| Final untouched 2025-2026 | 1,638 | 56.8% | **+16.14 bps** | 3.93 | 1.382 |

Neither the development nor the validation period is individually significant. The final
untouched window is 4× stronger than either — which sounds like good news and is not. Year by
year (gross): 2022 **−8.56**, 2023 −0.91, 2024 **+19.44**, 2025 **+22.13**, 2026 **+8.42**.

Two years (2024-2025) carry the entire result, and 2026 is already **down 62% from 2025's level**
and heading back toward the long-run average. An effect that only exists in the two most recent
full years, is negative in 2015/2020/2022/2023, and is fading in the current year is a regime
you would be betting on continuing, not an edge you have measured.

## 6. The left tail is against you (spec §14)

- Worst single trade: **−40.3%** overnight.
- 1st-percentile trade: −4.59%.
- Average winner +0.85% vs average loser **−0.88%** → payoff ratio **0.965**. You win 55% of the
  time and lose slightly more per loss.
- Removing the worst 1% of trades flips the 5 bps-cost result from −4.33 bps to **+4.5 bps**.
  The entire net loss lives in 100 trades out of 10,154.
- Worst 1% sum / best 1% sum = **1.24** — the bad tail is 24% larger than the good one.

This is precisely the failure mode §14 names: *a strategy can have a high win rate and still lose
money if occasional overnight gaps are much larger than its typical winners.* And no stop can
save it, because per §8 an overnight stop cannot be assumed to fill — the −40% trade gapped
through everything.

Max drawdown at 5 bps/side: **−86.3%**. Even gross: −45.1%.

## 7. Regime behaviour (§13, net at 5 bps)

| VIX | n | Mean | | SPY on signal day | n | Mean |
|---|---|---|---|---|---|---|
| < 15 | 3,661 | −8.94 bps | | > 0% | 4,344 | −5.69 bps |
| 15-20 | 3,573 | −2.14 bps | | −1% .. 0% | 4,209 | −5.83 bps |
| 20-30 | 2,380 | **+0.81 bps** | | < −1% | 1,601 | **+3.26 bps** |
| > 30 | 540 | −10.28 bps | | | | |

The reversal is strongest on **broad market down days at moderate volatility** and worst in calm
tapes and in panics. Consistent with the mechanism being *market-wide* rebound rather than
*stock-specific* pressure relief — which is the same conclusion §2 reaches from a different angle.

## 8. Parameter robustness (§10)

All five parameters produce a **flat plateau**, not a spike: every tested value of every threshold
lands between −3.2 and −5.6 bps net at 5 bps/side. That is the good news — nothing here is curve
fit. It is also the bad news: **no setting of any parameter makes the strategy work.** The result
is stable and stably unprofitable after costs.

## 9. What would have to be true for this to be tradable

1. **All-in execution under ~2.8 bps per side** — and under ~1.5 bps to have any margin once the
   real 3:55 entry and 9:35 exit are used. That is institutional-grade execution on both a
   closing-auction-adjacent fill and an opening print. Retail through a PH-accessible broker is
   not close.
2. **Drop filter E entirely** and re-derive. The late-volume rule is negative-value; the
   hypothesis behind it appears to be backwards.
3. **Exit at the open, not 9:35.** Worth ~4 bps, the largest single improvement available.
4. **Tail control that does not rely on an overnight stop** — position sizing or a hard cap on
   names with pending binary events, since a −40% gap ends a small account.

## 10. Verdict

**Do not trade this. Do not build V2 on top of it.**

The core hypothesis — that abnormal late selling creates temporary pressure that reverses
overnight — is **not supported**. What the data actually shows is that the general overnight
drift exists (+3.8 bps for any S&P name), that being down on the day adds a little (+4.9 bps),
and that the spec's specific machinery adds **+0.8 bps** while its signature filter *subtracts*
2.2 bps. Corrected to the spec's real entry and exit times, the whole thing earns about
**+0.6 bps per trade gross** — roughly one fifth of what it costs to execute.

The spec deserves credit for its own §17 discipline: it told us to reject if the edge does not
survive realistic fills, costs, and overnight tail risk. It does not.

---

## Caveats on this result

- **Survivorship: reduced, not eliminated.** Membership is point-in-time (including SIVB, FRC,
  TWTR), but 147 of 784 member tickers have no free price history and drop out. Missing names
  skew toward acquisitions and failures, so the true left tail is likely *worse* than measured.
- **Filters B and E are proxies in the full-history run.** Calibration puts filter E's proxy at
  0.79 correlation with the real intraday measure (acceptable) but filter B's at **8.8%
  precision** (poor) — "closed on the low" is a weak stand-in for "fell between 3:30 and 3:50."
  Since stage 2 is one of the few *positive* steps, the true filter B could be somewhat better
  than modelled. It cannot plausibly be worth the ~5 bps needed to change the verdict.
- **Sector map is current, not point-in-time** (the 2018 Communication Services rebuild is applied
  retroactively); unmapped names fall back to SPY, which makes filter D harder to pass, not easier.
- **The intraday leg is 60 days / 109 trades.** It calibrates bias well and decides nothing.
- **No borrow, impact, or partial fills** are modelled; all three make the real result worse.

---

# Addendum — Causality + catalyst overlay

**This changes the verdict conditionally.** The V1 spec as written is still rejected. But
splitting its trades by *why* the stock fell and *whether its demand chain was wanted*
isolates a subset with a real, cost-surviving, tail-favourable edge.

Run: `run_causality.py`, same universe and window, causal features on 93.2% of rows.

## A1. The question

The base result said the spec's signature filter is backwards — abnormal late volume costs
2.19 bps, because heavy volume marks **information**, and information does not reverse. The
natural fix is the one §16 already lists: separate temporary pressure from new information.

For each (stock, date), with a beta fitted only on data **before** the signal day:

```
day_ret = beta x theme_ret + residual
          \___ common ___/   \_ idio _/
```

- **PRESSURE** (`common_share >= 0.5`) — the whole chain fell and the stock was carried.
  Nothing was learned about the company.
- **INFORMATION** — the chain held up and this name broke on its own.

Crossed with whether that chain was **in demand**: trailing 60-day relative strength vs SPY,
also lagged.

## A2. Avoiding the hindsight trap

Knowing in 2026 that AI is the dominant theme, and that memory, rare earths, copper, uranium
and power are its supply chain, is *hindsight*. Hard-coding that basket back to 2014 would
manufacture an edge from knowledge we did not have.

So **no theme is ever named or dated in the code.** Themes are 15 real ETFs gated by their true
inception dates; a stock is assigned to one by trailing correlation; demand is trailing relative
strength. The AI narrative becomes a *prediction to test*, not an input.

**It validated itself.** The chains the model found in demand, from relative strength alone:

| Year | Top chains vs SPY |
|---|---|
| 2023 | SMH +7.8%, SOXX +6.2%, IGV +5.5% |
| 2024 | SMH +5.5% |
| 2025 | **URA +11.4%, REMX +10.7%, XME +8.7%** |
| 2026 | SOXX +22.5%, SMH +16.8% |

Compute in 2023-24, **power and materials in 2025** (uranium, rare earths, mining), semis again
in 2026 — the AI supply-chain rotation, recovered without the code knowing what AI is.

**One correction to the narrative:** broad **energy did not participate.** XLE was among the
*worst* chains in 2024 (−5.3%) and 2025 (−3.9%), and XLE names were the second-worst theme to
buy dips in (−14.2 bps, n=773). The AI power trade went to **uranium and nuclear**, not oil and
gas. "Energy rose because of AI" is not supported at the sector level.

## A3. The result (gross)

Wider pool, n=74,386 — the statistically powerful read:

| | TAILWIND | HEADWIND |
|---|---|---|
| **PRESSURE** | **+18.30 bps** (n=10,213, t=**9.37**) | −2.12 bps (t=−1.11) |
| **INFORMATION** | +3.82 bps (t=3.91) | +5.04 bps (t=4.74) |

V1 top-5 pool, n=10,154 — the decision-relevant read:

| | TAILWIND | HEADWIND |
|---|---|---|
| **PRESSURE** | **+27.76 bps** (n=588, t=3.36) | +15.81 bps (t=1.70) |
| **INFORMATION** | +4.57 bps (t=2.27) | +3.00 bps (t=1.04) |

Against +5.67 bps for the strategy overall, the best cell pays **~5x**.

**Two things the data insists on, which sharpen the original intuition:**

1. **Demand matters more than causality.** The tailwind/headwind axis splits +8.35 vs +2.61 bps
   (t=9.18, n=32,666). The pressure/information axis splits only +7.02 vs +4.46. *Whether the
   chain is wanted* is the stronger signal.
2. **It is an interaction, not two additive effects.** Chain-wide selling is only good inside a
   wanted chain; in an out-of-favour chain it is **negative** (−2.12 bps). A dip in something the
   market needs gets bought. The identical dip in something it does not need keeps falling.

## A4. Does it survive the checks the base strategy failed?

For `PRESSURE / TAILWIND` in the V1 pool (n=588):

| Check | Base V1 strategy | This cell |
|---|---|---|
| Gross mean | +5.67 bps | **+27.76 bps** |
| Adjusted to 3:55 entry / 9:35 exit | +0.60 bps | **+22.69 bps** |
| Net at 5 bps/side | −4.33 | **+17.76** |
| Net at 10 bps/side | −14.33 | **+7.76** |
| Worst trade | −40.3% | **−9.1%** |
| Worst 1% / best 1% | 1.24 (bad tail bigger) | **0.84** (good tail bigger) |
| Mean excluding best 1% | −11.6 bps | **+19.73 bps** |
| Years positive | 7 of 13 | **9 of 13** |
| Leave-one-year-out | — | **all 13 positive**, min +15.80 |

**Every failure mode of the base strategy is reversed.** It survives realistic costs, the left
tail is *favourable* rather than fat, and the edge is not a handful of lottery tickets — removing
the best 1% of trades still leaves +19.7 bps. Dropping 2026, the most influential year, still
leaves +15.80 bps (wider pool: +12.46).

## A5. Why this is still not a green light

- **The validation period is flat.** In the wider pool, 2022-2024 pays +2.89 bps (t=0.96) between
  a strong development period (+20.07, t=7.68) and a strong final one (+40.79, t=6.58). A real
  mechanism should not go quiet for three years.
- **The continuous version is not monotonic.** Common-share quintiles run Q5 +12.5, Q1 +8.0,
  Q3 +7.9, Q2 +5.9, **Q4 −3.6**. Only the top bucket separates cleanly; the binary cut works
  better than the variable underneath it, which is a signature of partial noise.
- **Thin in the tradable pool.** 588 trades over 12.7 years is ~46/year, roughly one every
  eleven sessions.
- **Multiple comparisons.** Four cells were examined and the best reported. The wider pool's
  t = 9.37 is reassuring but is a superset of the same trades, not independent evidence.
- **Untested intraday.** The 60-day exact-spec window was negative overall; the cell has too few
  trades there to check, so the entry/exit correction is applied from population constants rather
  than measured on these trades.

## A6. Revised verdict

**The V1 spec: still reject.** Its own filters do not produce the edge, and its signature
late-volume rule actively subtracts.

**The causal overlay: promising enough to paper-trade, not to fund.** What actually works is not
"buy heavy late-session losers." It is:

> **Buy a stock that fell *with its whole demand chain*, when that chain is *outperforming the
> market*. Skip it when the stock fell alone, and skip it when the chain is out of favour.**

That is a different strategy from the one in the PDF — it keeps the spec's timing and its
earnings filter, discards the late-volume rule, and adds the two causal conditions. The honest
next step is forward paper trading, because this result was found by slicing an existing dataset
four ways, which is exactly the process that produces convincing accidents.

---

# Addendum 2 — Extended universe (the spec's real screen, not just the index)

The first two studies used the S&P 500 as a stand-in for the spec's §2 screen. That was a
convenient substitution and a materially wrong one: the index **excludes most of the 2023-2026
AI supply chain**. MP, UEC, LEU, CCJ, OKLO, BWXT, TLN, NBIS, CRDO and ALAB all clear the spec's
$2B / $50M bar and none are members. Only VRT, VST and CEG were in the original universe.

Rebuilt from the spec's actual screen across NASDAQ/NYSE/AMEX: **2,285 tickers** (784 index +
1,501 extended), 2,136 priced (93.5%).

## B1. The headline roughly doubles

| | S&P 500 only | Extended |
|---|---|---|
| Trades | 10,154 | 12,914 |
| Gross mean | +5.67 bps | **+11.04 bps** |
| t-stat | 3.41 | **5.79** |
| Breakeven | 2.83 bps/side | **5.52 bps/side** |
| Gross Sharpe | 0.65 | **1.20** |
| OOS dev / val / final | +3.5 / +3.9 / +16.1 | **+8.8 / +9.1 / +22.6** — all significant |

The flat validation window that undermined the index-only result is gone.

## B2. But nearly all of it is in the slice we cannot verify

| Segment | n | Gross | t |
|---|---|---|---|
| EXTENDED (non-index) | 7,255 | **+17.36 bps** | 2.60 |
| SP500_PIT (survivorship-clean) | 5,659 | +2.94 bps | — |

The only point-in-time-clean slice got **worse**. The extended list is built from *today's*
$2B+ listings, so it contains survivors only and implicitly knows which companies later grew.

**The diagnostic that partly rescues it** — splitting extended names by when they first cleared
the liquidity screen. Names already liquid in 2014-15 carry far less "we knew it would make it"
selection:

| Segment | Listing era | n | Gross |
|---|---|---|---|
| EXTENDED | early (liquid by 2015) | 3,215 | **+14.75 bps** (t=1.55) |
| EXTENDED | late arrival | 4,040 | +19.42 bps (t=2.11) |
| SP500_PIT | early | 4,242 | +1.20 bps |

The effect is present in **both** sub-slices, so it is not purely a survivor artifact. The more
likely reading is a **size effect**: mid-caps and volatile growth names mean-revert overnight
harder than mega-caps, and the S&P 500 is mega-cap dominated — the one place the effect is
weakest. Survivorship is *reduced, not removed* (early-liquid names that died before 2026 are
still absent), and t=1.55 on the cleanest sub-slice is not significant alone.

## B3. The causal result gets stronger and the interaction becomes decisive

Wider pool, n=168,882 — gross:

| | TAILWIND | HEADWIND |
|---|---|---|
| **PRESSURE** | **+17.97 bps** (n=23,402, t=**12.65**) | **−3.97 bps** (t=**−2.95**) |
| **INFORMATION** | +4.80 bps (t=6.00) | +8.88 bps (t=10.61) |

Chain-wide selling into a **wanted** chain pays +18 bps; the identical selling into an
**unwanted** chain is *significantly negative*. On the index-only universe that cell was merely
flat (−2.12, t=−1.11); with the real universe it is a confirmed sign flip. **The interaction is
the finding**, not either axis alone.

Robustness on that cell: spec-adjusted **+12.90 bps**, positive at 5 bps/side (+8.0), all 13
leave-one-year-out means positive (min +8.18 dropping 2026), tail ratio 0.95, still +8.6 bps
excluding the best 1% of trades. The 2022-2024 soft patch persists across both universes
(+3.1 bps, t=1.43) and is now the single most consistent weakness in the whole study.

## B4. The chains where buying dips actually pays

| Theme | n | Gross | t |
|---|---|---|---|
| **SOXX** semis | 10,500 | **+26.63 bps** | **11.30** |
| **URA** uranium | 1,874 | **+23.96 bps** | **4.06** |
| **SMH** semis | 5,964 | **+21.45 bps** | **6.65** |
| **XLU** utilities / power | 6,623 | +9.93 bps | 6.42 |
| REMX rare earth | 1,702 | +8.66 bps | 1.24 |
| IGV software | 27,619 | +0.23 bps | 0.17 |
| **XLE** oil & gas | 12,597 | **−1.28 bps** | −0.74 |

**This is the AI supply chain, recovered from returns alone.** Compute (SOXX, SMH), power
(URA, XLU), materials weakly (REMX). Software — the "AI application layer" — pays nothing.

And it settles the energy question raised in Addendum A2: **power yes, oil and gas no.** XLU
(+9.93, t=6.42) and URA (+23.96, t=4.06) are real; XLE is negative and insignificant. "Energy
rose because of AI" is only true for *electricity*, not for energy as a sector.

## B5. The spec's own ranking fights the causal edge

In the V1 top-5 pool the PRESSURE/TAILWIND cell drops to n=555, +14.63 bps, **t=1.69 — not
significant** — and is beaten by INFORMATION/HEADWIND (+11.99, t=4.01). Yet in the wider pool
the same cell is +17.97 at t=12.65.

The reason: the spec's §6 score ranks by *severity* (biggest selloff, deepest drawdown, heaviest
volume). In a universe containing volatile mid-caps, the most severe decliners are
overwhelmingly **idiosyncratic blowups** — exactly the INFORMATION names the causal thesis says
to avoid. **The top-5 selector systematically selects away from the edge.**

Actionable: if the causal version is ever traded, rank by `common_share x theme_strength`, not
by the spec's severity score.

## B6. Revised verdict

- **V1 spec as written: still reject.** Its late-volume filter is negative-value and its ranking
  actively selects against the only cell that works.
- **Causal version on the real universe: the strongest result in this study**, and the one worth
  paper-trading — buy a stock that fell *with* a demand chain that is *outperforming*, in semis,
  uranium or power; never when the chain is out of favour.
- **Confidence is capped by data, not by the result.** The extended slice cannot be made
  survivorship-free with free sources (FMP gates delisted symbols, Yahoo 404s them — the same
  wall `value_quality` hit). Treat +18 bps as an upper bound and the S&P-clean +2.94 bps as a
  lower one.
