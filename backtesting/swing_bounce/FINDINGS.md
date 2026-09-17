# Swing Bounce Backtest — FINDINGS

**Status:** Preliminary result — **NEGATIVE / INCONCLUSIVE. Edge NOT proven. Do not automate.**
**Run:** bounded — 30 large-cap names, 2015–2023, 642 drop events (380 "alive"), 100% EDGAR coverage.

> This backtest exists to answer one question before any broker automation: *does buying a
> beaten-down + "financially alive" US stock with a stop/target actually have positive expectancy?*
> The honest answer on this data is **no, not reliably** — and the quality gate did not help.

## The hypothesis (and how it did)

**Hypothesis:** beaten-down + "financially alive" (profitable + positive CFO + solvent) → positive
expectancy over a swing horizon, and the alive gate **improves** expectancy vs ungated.

**Result — the intuitive setup loses.** The headline cell (your intuition: +20% target / −10% stop /
20-day horizon, 25% drop trigger):
- **Gated: n=99, 16% hit rate, expectancy −0.068R** (loses after 15 bps/side costs).
- **Ungated: n=162, 20% hit, +0.019R.** → **the gate made it WORSE by 0.087R.**

A +20% target with a −10% stop needs ~33%+ hit just to break even; 16–20% is far below. Over 20
days a 20% bounce simply doesn't materialize often enough.

## The full sweep (81 cells × gated/ungated)

- **45/81 gated cells are positive** — barely better than a coin flip across the grid.
- **The only decent cells sit at long-horizon + wide-stop**: e.g. 35%-drop / +10% / −15% / 40d →
  73% hit, +0.223R; 25%-drop / +20% / −15% / 40d → 40% hit, +0.172R. But these are a **"pick up
  pennies" shape** — small target, wide stop (negative reward:risk), high hit rate. That profile
  produces steady small wins and occasional large losses — it *looks* good on a survivor basket and
  **blows up in a real crash**. It is the classic overfit-to-mean-reversion trap.
- **vs SPY:** SPY's unconditional forward return was +0.4% (10d) / +0.9% (20d) / +1.6% (40d) — the
  bounce trades are not clearly beating "just hold the index for the same window."

## The gate is not the edge (the important negative)

Across all 81 cells, the "financially alive" gate **helped 12, hurt 69, mean −0.048R.**

**The mechanism (verified):** at the headline cell, splitting events by the gate gives
**ALIVE: 16% hit / −0.068R** vs **NOT-ALIVE: 27% hit / +0.155R.** The *lower-quality* names bounce
**harder** — the well-known higher-beta-junk-bounces-bigger effect. So the quality gate systematically
removes the biggest bounces. (Labeling verified correct + point-in-time: 61% of events are "alive,"
and the same tickers appear in both legs at different dates as their fundamentals change.) **The
differentiator we built the swing skill around is counterproductive for pure bounce-catching on this
data.**

**But do NOT flip to buying junk:** that NOT-ALIVE +0.155R is the **most survivorship-inflated number
in the whole study** — the low-quality names that bounced are in the sample; the ones that went to
zero (the reason the quality gate exists) are *gone from the price data entirely*. The "junk bounces
harder" premium is largely the survivors of a distribution whose losers we can't see. It may still
matter on a broad universe with genuine distress/delistings — which this survivor-only run cannot test.

## Why even the positives are untrustworthy

1. **Maximal survivorship bias:** 0 of 380 gated events were truncated/delisted — the universe is
   30 *survivors*. The worst falling knives (names that went to zero) are entirely absent, so every
   number here is **optimistically biased**, and it's *still* only borderline.
2. **Concentration:** the headline gated cell's P&L is **110% carried by ROKU** — strip it and it's
   net negative. A handful of names drive the surface.
3. **Small n per cell** (48–233) on a cherry-pickable 81-cell grid — a lucky cell is not an edge.

## Verdict → gates the paper loop SHUT

**Do not proceed to the Alpaca paper-trading loop.** The edge is not proven: negative at the
intuitive setting, non-robust and low-quality (negative R:R) where positive, gate-doesn't-help, and
measured on survivors only. Automating this would be exactly the trap this project keeps flagging.

**Keep `stock-scan swing` as a discretionary idea-surfacer only** — a disciplined way to look at
beaten-down solvent names with defined risk, *not* a mechanical signal to auto-execute.

## What would change the verdict (future work, if pursued)

- A **survivorship-free universe with delisted names** (Polygon $29) — the biggest hole; the honest
  test needs the knives that went to zero.
- A **broader universe** (small/mid-caps in real distress) where the alive gate can actually
  discriminate.
- **Structure-based levels** (stop below the real swing low, target at a Fib retracement) instead of
  fixed %, and a **catalyst filter** (the drop's *reason*) — the mechanical drop+oversold trigger is
  crude.
- Until then: **no automation.** Banked as a negative, like top-gainer fade and funding carry.
