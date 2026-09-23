# Insider-cluster-buy backtest — FINDINGS

**Verdict (multi-year, 2021–2026): the INTERSECTION is the edge, not either signal alone.**
- **Insider cluster buys ALONE are a dud** — mean +1.84% vs an unconditional base rate of +4.71% (60d,
  i.e. they *underperform*), **negative in the 2021/2022 regimes**, and **−5.99% after the survivorship
  stress** (49/683 truncated). Do not trade the filing on its own.
- **The earnings CATALYST alone is only modest** — +1.92% median / 56% hit (60d).
- **Insider cluster + a coincident earnings catalyst is materially better than either** — **60d median
  +11.15%, 67% hit (n=39)** vs catalyst-alone +1.92% and insider-without-catalyst +1.53%. On the recent
  apples-to-apples slice, the ~28% of insider clusters that coincide with an earnings beat carry
  essentially **all** the edge.

So: **neither signal alone; the conjunction.** This *vindicates* the `/stock-scan insider` mode's
catalyst-required design and sharpens the rule — **skip any insider cluster that lacks a catalyst**
(those are noise-to-negative). Confirms the deep-research/REPL frame (insider buys confirm; catalysts
drive) but upgrades "confirm" to a real filter *when combined*. Caveats: n=39 (modest, though median +
hit-rate are outlier-robust), the catalyst slice is one recent (bullish) regime, and all numbers are
survivorship-inflated upper bounds. Discipline mirrors [swing_bounce](../swing_bounce/FINDINGS.md).

## Multi-year results (2021-01 → 2026-08) — the headline
839 cluster events, 683 covered (75% ticker coverage), 350 largest-$ tickers. Catalyst arms restricted
to the Finnhub-covered slice (events ≥ 2025-06; free earnings history is only ~4 quarters — see note).

| Arm (60d) | n | mean | median | hit |
|---|---|---|---|---|
| control (base rate) | 55,897 | +4.71% | −1.80% | 47% |
| insider_all (full 2021–26) | 683 | +1.84% | −0.90% | 47% |
| insider_recent (all, ≥25-06) | 141 | +9.57% | +3.74% | 57% |
| catalyst_only (no cluster) | 513 | +11.17% | +1.92% | 56% |
| insider **no** catalyst | 102 | +7.52% | +1.53% | 53% |
| **insider + catalyst** | **39** | **+14.93%** | **+11.15%** | **67%** |

20d tells the same story: insider+catalyst median **+8.07%** / 64% hit vs catalyst-only +0.97% vs
insider_no_catalyst +2.20%.

**Regime robustness (insider_all, 60d) — why "alone" fails:**
| Year | n | mean | median | hit |
|---|---|---|---|---|
| 2021 (mania) | 151 | −5.25% | −2.17% | 45% |
| 2022 (bear) | 134 | −1.24% | −1.43% | 46% |
| 2023 | 113 | +2.17% | −3.19% | 44% |
| 2024 | 98 | +4.81% | −0.55% | 47% |
| 2025 | 114 | +6.42% | −0.90% | 47% |
| 2026 | 73 | +10.52% | +3.79% | 59% |

Insider-alone is negative/flat in 4 of 6 years and only "works" in the recent bull tape (and even then
mean-driven — TKNO alone is 42% of full-period P&L). The 2024-pilot's "modest 20d edge" was a
one-regime artifact; across regimes it disappears. Survivorship stress: +1.84% → **−5.99%** (49 truncated).

> **Data note (why the catalyst arm is recent-only):** free Finnhub earnings returns only ~4 quarters,
> and FMP free caps history at 5 rows + gates small-caps — so a *historical* earnings-surprise label
> for 2021–2024 small-caps isn't obtainable free. The catalyst intersection is therefore measured on
> 2025-06→2026-08 only. Answering it across regimes needs a paid/deep earnings-surprise source
> (Alpha Vantage EARNINGS is deep + free but 25 req/day) or a price-gap catalyst proxy built from OHLC.

## Pilot (2024 only) — superseded by the multi-year run above
Kept for provenance; the 2024-only slice showed a modest 20d insider edge that the multi-year run
reveals as regime-specific.

## Setup
- **Events:** openinsider historical panel, **2024** (12 months), open-market P purchases, grouped into
  cluster events (≥2 distinct insiders within 7 days). **429 cluster events**, 394 with price coverage,
  **92% ticker coverage** (301 tickers, capped by cluster $ size).
- **Entry:** open of **t+1** after the public filing date (genuinely tradeable, no look-ahead).
- **Metric:** H-day forward return (H=20, 60), net of ~30bps round-trip. Compared across arms.
- **Catalyst proxy:** a positive Finnhub earnings surprise near the event (±35d announcement approx) —
  the one small-cap catalyst labelable at scale (FDA/contracts out of automated scope).
- **Control:** unconditional H-day base rate across the same covered tickers (every-5th-bar sample).

## Results

### H = 20 trading days
| Arm | n | mean | median | hit | vs control (mean) |
|---|---|---|---|---|---|
| control (base rate) | 34,851 | +1.48% | −0.30% | 50% | — |
| **insider_all** | 394 | **+4.07%** | **+1.29%** | 54% | **+2.59%** |
| insider_csuite | 240 | +4.17% | +1.47% | 55% | +2.69% |
| insider_big ($≥500k) | 289 | +4.05% | +1.38% | 54% | +2.57% |
| insider_no_catalyst | 390 | +3.97% | +1.24% | 53% | +2.49% |
| catalyst_only | 601 | +2.80% | +0.35% | 51% | +1.32% |
| insider_plus_catalyst | **4** | +13.97% | +7.11% | 100% | +12.49% *(n=4 — ignore)* |

### H = 60 trading days
| Arm | n | mean | median | hit | vs control (mean) |
|---|---|---|---|---|---|
| control (base rate) | 34,851 | +5.77% | −0.09% | 50% | — |
| catalyst_only | 601 | **+9.04%** | **+2.48%** | 57% | **+3.27%** |
| insider_all | 394 | +6.05% | +0.85% | 52% | +0.28% |
| insider_csuite | 240 | +6.57% | +0.61% | 50% | +0.80% |
| insider_big | 289 | +6.29% | +1.32% | 52% | +0.52% |
| insider_no_catalyst | 390 | +6.04% | +1.14% | 52% | +0.27% |
| insider_plus_catalyst | 4 | +6.99% | +0.16% | 50% | +1.22% *(n=4)* |

- Stop/target tradeable cell (+20% / −12% / 60d): **+0.328R**, hit 37%, n=392 (positive but thin, and
  survivorship-inflated).
- SPY 60d benchmark +2.36%; survivorship stress: base +6.05% → **+4.53%** (only 6 truncated = an
  UNDERCOUNT, see bias).

## Reading the result
1. **Insider clusters have a real but SHORT-HORIZON edge.** At 20d the median beats control by ~+1.6pp
   (54% hit) — a genuine post-buy drift, matching the Stanford microcap preprint. **It decays to ~zero
   by 60d.** So the horizon is ~2–4 weeks, not months.
2. **The edge is thin and cost-fragile.** +1.3% median at 20d is roughly eaten by a ~2% microcap
   bid/ask spread — net ≈ breakeven, exactly the preprint's warning (precision 0.38, ~3.3% net).
3. **The catalyst is the durable driver.** catalyst_only grows to +3.27% over control at 60d (57% hit)
   while insider-alone fades — the *opposite* horizon behavior. Selecting on the catalyst beats
   selecting on the insider filing.
4. **Does the insider ADD to the catalyst? UNRESOLVED.** The intersection is n=4 in one year — too rare
   to conclude. But `insider_no_catalyst ≈ insider_all` at both horizons, so most insider clusters
   aren't catalyst-driven, and the insider signal without a catalyst adds nothing durable.
5. **Mean ≫ median = fat right tail.** One microcap (ZIVO) is 14% of headline P&L. The mean is a few
   moonshots; the median is the honest central tendency.

## Biases / limitations (why these are UPPER bounds)
- **Survivorship (the big one):** Yahoo returns no delisted names, so the small-caps that blew up /
  delisted are largely absent from the universe entirely (not just truncated — the 6 truncated is an
  undercount). The true insider-alone edge is likely **below** these figures, plausibly negative net.
- **One year (2024 only):** a single regime; the insider+catalyst intersection never populated (n=4).
  A multi-year panel is the obvious next step to answer the marginal-add question.
- **Catalyst proxy is crude:** earnings surprise only, ±35d announcement approximation; misses
  FDA/contract catalysts (which the REPL case shows are the real small-cap 2x drivers).
- **No liquidity/price-floor filter in-panel:** microcaps + sub-$5 names are included; the mean is
  fragile to a few of them.

## Bottom line for `/stock-scan insider`
The mode's design was right: **hard-gate to open-market clusters + REQUIRE a catalyst + size small.**
But this backtest says the *insider filing itself* is a weak, ~2–4-week, cost-fragile confirmation —
**not** an edge to trade on its own, and **not** a 2x predictor. Trade the catalyst; use the cluster
as confirmation and a stop anchor (insiders' avg buy price). Don't automate an insider-only signal.

## Reproduce
```
python3 -m backtesting.insider_cluster.run     # fetch (rate-limited) + run; writes runs/<ts>/results.json
```
Modules: `panel.py` (openinsider historical P-buy panel + clustering), `catalyst.py` (Finnhub PEAD
overlay), `run.py` (arms + survivorship stress). Reuses swing_bounce `prices_ohlc`/`trade_sim`/`metrics`.
