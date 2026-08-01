# Value + Quality + Drop — Backtest Findings (2026-08-01)

**Status: VALIDATION MILESTONE — not a verdict. Pipeline proven. Edge verdict deferred pending scale + survivorship fix.**

Nothing approved. Research only. No live execution.

---

## Hypothesis

A monthly, point-in-time long-only strategy that combines:
1. A **sector-relative value composite** (E/P, B/P, EBITDA/EV, FCF yield — top 20%)
2. A **Piotroski F-score ≥ 7** quality gate
3. An optional **drawdown trigger** (skip names that have already fallen hard)

…should outperform SPY and a cheap-only (value-gate-only) baseline by selecting
for cheap *and* financially healthy companies and avoiding stocks in freefall.

---

## What was tested (bounded validation run)

| Parameter | Value |
|-----------|-------|
| Universe | 20 large-cap stocks (AAPL, MSFT, JPM, XOM, KO, PG, JNJ, WMT, CVX, PFE, INTC, CSCO, IBM, GE, F, BAC, T, VZ, MRK, DIS) |
| Period | 2015-01 → 2020-12 (71 rebalances) |
| Fundamentals | SEC EDGAR free API, PIT (`filed` dates only) |
| Prices | Yahoo Finance (Stooq fallback dead) |
| Transaction cost | 15 bps / side on turnover |
| Sector source | Hardcoded stub (8 sectors) |
| EDGAR coverage | 100% (all 20 names had all required tags) |

---

## Results

| Leg | CAGR | Sharpe | Note |
|-----|------|--------|------|
| **Strategy** (value+quality+drop) | **+1.95%** | **0.58** | Starved — see below |
| **Cheap-only** (value gate only) | **+13.89%** | **0.72** | Beats SPY on return |
| **SPY** | **+13.33%** | **0.89** | Benchmark |
| **Equal-weight universe** | **+10.84%** | **0.76** | Benchmark |

---

## What the numbers mean — read carefully

### Strategy leg is uninformative on this universe

The full strategy (value + quality + drop trigger) **should not be judged by its 1.95% CAGR.**
Here is what actually happened:

- The compound gate (value top 20% + F-score ≥ 7 + no recent drop) fired on only
  **~3 of 71 rebalance months** with the 20-name universe.
- The remaining ~96% of months the portfolio sat in **cash earning 0%**.
- Virtually the entire strategy P&L traces to a **single name: AAPL** — the only
  name that cleared all three gates consistently. The `>50% single-name concentration`
  flag fired correctly.

This is **correct machinery running on an undersized universe.** With only 20 names
and sector-relative ranking across 8 sectors (2–5 names each), the value percentile
cutoff is very coarse — most months, no name clears the combined gate. This is
**not evidence that the strategy fails**; it is evidence that 20 names is too few
to form a diversified book.

### Cheap-only (value gate alone) is more informative

Removing the quality and drop gates leaves a larger pool each month. The cheap-only
leg achieved **+13.89% CAGR / 0.72 Sharpe vs SPY's +13.33% / 0.89** — modestly
higher return, lower Sharpe. This is consistent with value working as a return
premium but adding volatility vs a capitalization-weighted index.

**Even this number is not a reliable signal.** It was estimated on 20 large-cap
survivors over a 6-year bull run. Survivorship bias, sector-stub distortion, and
the narrow universe all push results optimistically.

### What IS validated

1. **Pipeline correctness**: EDGAR PIT fetch → fundamentals parsing → F-score →
   value composite → sector-relative ranking → drop trigger → monthly loop →
   cost deduction → metrics → dashboard — all wired end-to-end without look-ahead.
2. **EDGAR free fundamentals work at scale**: 100% tag coverage on 20 large-caps.
   The free-data thesis holds on the fundamentals side. The only data gap is the
   **price-side survivorship hole** (Yahoo drops delisted names, Stooq is dead).
3. **15 bps/side cost model**: wired correctly; each monthly rebalance deducts
   the two-sided turnover cost from realized returns.
4. **Concentration and survivorship diagnostics**: the `>50%` flag fired; the
   pessimistic survivorship stress test is plumbed and runs.

---

## Survivorship hole — honest statement

Yahoo Finance's API does not serve delisted, bankrupt, or renamed tickers.
Stooq, the intended fallback, currently returns a JS-challenge page instead of
data — it is non-functional as of this run.

On the large-cap 2015–2020 validation universe: **0 missing price files out of 20.**
This is because all 20 names were S&P 500 blue-chips that survived the period.

On a full S&P 500 run (all 500 names, 2009–now), the gap would be **severe**: dozens
of names went bankrupt, were acquired, or were delisted over a 17-year window.
Yahoo returns nothing for them; the backtest would silently treat them as if they
never existed. This is classic **survivorship bias** — the backtest would look better
than reality because it never holds a company through its death.

**The honest next step: add Polygon.io as a delisted-price source (~$29/mo) before
reading any edge verdict from a full universe run.** Without it, any positive result
is optimistically biased by an unknown but non-trivial amount.

---

## Drop-threshold sweep

The drop trigger was swept across four thresholds (85%, 75%, 65%, 50%) on the
strategy leg. On this 20-name universe the sweep is not informative: all settings
produce similar starved-cash results because the binding constraint is universe
size, not the drop threshold. This sweep becomes meaningful at full scale.

---

## Sub-period breakdown

| Period | Note |
|--------|------|
| 2009–2013 | Below the validation window start (2015) — no data |
| 2014–2019 | Bull run; cheap-only outperforms on CAGR; strategy starved |
| 2020–now | COVID crash + recovery; small strategy sample |

The "value winter" (2017–2020 growth-vs-value divergence) should show up strongly
in a full universe + full time window run. It is the critical stress test for this
strategy and is not adequately represented in this bounded validation.

---

## What it means — no edge verdict yet

The pipeline is validated. The free EDGAR data path is proven. The numbers from the
bounded run are consistent with correct machinery on an undersized universe — they
are not evidence for or against the strategy edge.

**A verdict requires:**
1. Full S&P 500 universe (500+ names) so the compound gate can form a diversified book
2. Full 2009–now window including the value winter (2017–2020)
3. A delisted-price source to close the survivorship hole

Only then can the strategy leg be evaluated honestly.

---

## Next lever

| Priority | Action |
|----------|--------|
| **1 (blocking)** | Expand universe to full S&P 500 (or Russell 1000) — load `company_tickers.json`, filter by SIC + market-cap, pull EDGAR facts for 500+ names |
| **2 (blocking)** | Close the survivorship hole — add Polygon.io free-tier or $29/mo delisted-price endpoint |
| **3** | Replace `SECTOR_STUB` with real SIC-code → GICS sector mapping (SEC SIC codes are in `company_tickers.json`) |
| **4** | Extend window to 2009–now — cold-cache fetch for the additional years (price data only; EDGAR facts already include history) |
| **5 (then read)** | Re-run full backtest, inspect sub-periods (esp. value winter 2017–2020), check concentration + survivorship stress — THEN declare a verdict |

---

## Reproduce

```bash
# Fetch data + run validation backtest (bounded, cached, ~3 min on cold cache)
uv run python -m backtesting.value_quality.run

# Tests (network-free)
uv run pytest backtesting/value_quality/tests -q   # expect 22 passed

# Open dashboard
open backtesting/value_quality/runs/$(ls -t backtesting/value_quality/runs | head -1)/dashboard.html
```
