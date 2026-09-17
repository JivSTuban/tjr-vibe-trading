# backtesting/value_quality

A monthly, point-in-time long-only equity backtest combining a **value composite**
(E/P, B/P, EBITDA/EV, FCF yield — sector-relative ranked), a **Piotroski F-score ≥ 7**
quality gate, and an optional **drawdown-trigger** (drop ≥ threshold in the lookback
window prevents entry). Tested against SPY, a cheap-only (value-gate-only) baseline,
and an equal-weight universe.

All fundamentals are sourced from the free **SEC EDGAR** API (point-in-time, using
`filed` dates). Prices come from **Yahoo Finance** via `yfinance` (and optionally
Stooq as a fallback — see note below).

---

## Strategy logic

```
Universe filter  : market-cap ≥ $1 B, price ≥ $5, median 30-day dollar-volume ≥ $5 M
Value composite  : sector-relative rank of (E/P, B/P, EBITDA/EV, FCF yield) — top 33%
Quality gate     : Piotroski F-score ≥ 7 (9 binary signals across profitability,
                   leverage/liquidity, and operating efficiency)
Drop trigger     : skip a name if close dropped ≥ cfg.drop_threshold in the lookback
                   window ending strictly before the rebalance date
Portfolio        : equal-weight, monthly rebalance; up to cfg.max_names names;
                   max hold cfg.max_hold_months months; 15 bps/side transaction cost
                   applied to turnover each month
```

---

## Free data sources

| Source | What | Access |
|--------|------|--------|
| SEC EDGAR `company_tickers.json` | Ticker → CIK map | Public, no key |
| SEC EDGAR `companyfacts/{cik}.json` | Fundamentals (XBRL tags) | Public, no key |
| Yahoo Finance (`yfinance`) | OHLCV prices | Public, no key |
| Stooq (fallback) | OHLCV prices | **Currently non-functional** — JS challenge blocks the fetcher; Yahoo is the sole working price source |

All data is cached under `.cache/` (gitignored). Re-runs are cache-first; the network
is only hit on a cold cache.

---

## Quickstart

```bash
# Install dependencies (pyproject.toml managed via uv)
uv sync

# One-shot: fetch data + run the bounded validation backtest (2015–2020, 20 names)
uv run python -m backtesting.value_quality.run

# Outputs (gitignored):
#   backtesting/value_quality/.cache/          — fundamentals + price CSVs
#   backtesting/value_quality/runs/<ts>/results.json
#   backtesting/value_quality/runs/<ts>/equity_curves.png
#   backtesting/value_quality/runs/<ts>/dashboard.html

# Open the dashboard
open backtesting/value_quality/runs/$(ls -t backtesting/value_quality/runs | head -1)/dashboard.html

# Run tests (network-free, uses fixtures)
uv run pytest backtesting/value_quality/tests -q
```

---

## Module map

| File | Role |
|------|------|
| `edgar.py` | EDGAR fetch + PIT `pit_finyears` (uses `filed` dates only) |
| `fundamentals.py` | `piotroski_fscore`, `valuation` ratios |
| `signals.py` | `value_composite` (sector-relative), `drop_trigger` |
| `strategy.py` | `ValueQualityCfg`, `select_holdings` |
| `metrics.py` | `PortfolioResult`, `metrics_from_returns` (CAGR, Sharpe, MaxDD) |
| `prices.py` | `fetch_prices`, `load_prices`, `passes_universe`, `median_dollar_volume` |
| `run.py` | Driver: fetch universe → run backtest → sweep / sub-periods / survivorship → dashboard |
| `viz.py` | `render_dashboard` → `equity_curves.png` + `dashboard.html` (offline, no network) |

---

## Disclosed biases

### 1. Look-ahead (mitigated)
EDGAR PIT discipline uses only facts where `filed <= asof`. The return leg uses
`last price < asof` as entry and `last price <= next month-end` as exit — no
forward-looking bar is read.

### 2. Survivorship (UN-backstopped — material)
**Yahoo Finance silently drops delisted and bankrupt tickers.** Stooq was the
intended fallback but is currently non-functional (JavaScript challenge page
returned instead of data). Any ticker that was removed, renamed, or went bankrupt
after the price history ends lands in `missing_prices.txt` with no second source.

On the 20-name large-cap validation universe this gap is zero (0 missing). On a
full S&P 500 run (including small/mid-caps over 2009–now) it would be severe:
the universe over-represents survivors. A delisted-price source such as
**Polygon.io** ($29/mo) is the correct fix before drawing any production conclusions.

The `_survivorship` function runs a pessimistic stress test (missing names realize
−50% in their last available month) to bound the downside — but this is a
diagnostic, not a solution.

### 3. EDGAR tag coverage
EDGAR XBRL coverage varies by company and year. The `coverage_pct` field (100%
on large caps in this run) measures what fraction of the universe had all required
tags. Small-cap or pre-2010 filings may be missing tags (EV/EBITDA and FCF
especially), which could selectively exclude lower-quality filers and introduce a
subtle bias.

### 4. Sector mapping
The validation run uses a hardcoded `SECTOR_STUB` (20 names, 8 sectors). A
production run must replace this with real SIC-code or GICS sector data; the
sector-relative value ranking is meaningless if sector assignments are wrong.

### 5. Transaction costs
15 bps/side is applied to each leg of turnover at every rebalance. This is
conservative for large-caps with tight spreads but may understate costs for
less-liquid names. No market-impact model is included.
