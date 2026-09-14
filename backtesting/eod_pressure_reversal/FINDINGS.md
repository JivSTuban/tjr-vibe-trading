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
