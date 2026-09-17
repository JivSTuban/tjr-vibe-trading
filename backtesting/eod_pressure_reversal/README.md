# eod_pressure_reversal — overnight mean-reversion backtest (spec V1)

Tests the **EOD Pressure Reversal Strategy V1** spec: abnormal late-session selling creates
temporary price pressure that partially reverses overnight. Buy the most distressed names near
the close, sell the next morning, hold nothing over a second night.

**Result:** see `FINDINGS.md`. Short version — the spec as written is **rejected** (the gross edge
is +5.67 bps/trade and breaks even at 2.83 bps per side, and most of it is just the market-wide
overnight drift). The **causality addendum** finds the one subset that does survive costs: stocks
that fell *with their whole demand chain* while that chain was *outperforming the market*.

## Run

```bash
PYTHONPATH=. uv run python -m backtesting.eod_pressure_reversal.run            # full history, daily bars
PYTHONPATH=. uv run python -m backtesting.eod_pressure_reversal.calibrate      # 60-day exact-spec intraday
PYTHONPATH=. uv run python -m backtesting.eod_pressure_reversal.run_causality  # causality + catalyst overlay
PYTHONPATH=. uv run pytest backtesting/eod_pressure_reversal/tests -q          # pure logic, network-free
```

First run fetches ~780 tickers of daily bars plus ~3,200 days of earnings calendar and takes
~25 minutes. Everything caches to `.cache/`, so re-runs are seconds.

## Pieces

- `universe.py` — point-in-time S&P 500 membership, the extended $2B/$10 screen across
  NASDAQ/NYSE/AMEX, and the GICS sector -> sector-ETF map. `UNIVERSE_MODE` in `run.py`
  switches between `sp500` (survivorship-clean) and `extended` (adds the AI supply chain).
- `prices.py` — daily OHLCV (Yahoo primary, FMP rescue), split/spin detection, missing-log.
- `earnings.py` — spec filter F via Nasdaq's calendar, BMO/AMC aware.
- `signals.py` — spec §4 conditions + §6 composite percentile score.
- `strategy.py` — spec §9 staged build order, top-5 selection, §7 exits, §8 costs.
- `metrics.py` — spec §12 metrics, §13 regimes, §14 left tail, §11 OOS splits.
- `intraday.py` — 5m bar loader + exact 15:30/15:50/15:55 feature computation.
- `calibrate.py` — runs the unmodified spec on the 60-day intraday window.
- `causality.py` — PRESSURE vs INFORMATION decomposition + point-in-time demand-chain themes.
- `run_causality.py` — the causal/catalyst study (see FINDINGS addendum).
- `run.py` / `viz.py` — driver and offline HTML dashboard.

## The data problem, and what we did about it

The spec measures signals on an intraday tape (3:30 PM and 3:50 PM marks) and enters at 3:55 PM.
**No free source carries that history.** Verified 2026-09-15, not assumed:

| Source | Intraday result |
|---|---|
| Yahoo `interval=5m` | **60 calendar days only** — `422` beyond that |
| FMP `historical-chart/5min` | `403` legacy endpoint, retired for accounts created after 2025-08-31 |
| Finnhub `/stock/candle` | `403` — paid tier |
| Alpaca | free SIP history back ~7 years, but needs an account we do not have |

So the work splits in two:

**1. Full history (2014-2026) on daily bars.** Four of six filters are computed exactly; two
become explicitly-named proxies:

| Spec filter | Full-history implementation | Fidelity |
|---|---|---|
| A. DayReturn ≤ −1.5% | close / prev close − 1 | exact up to close-vs-15:50 |
| B. LateReturn ≤ −0.5% (15:30→15:50) | **proxy:** close in bottom 25% of day range | measured in `calibrate.py` |
| C. Drawdown from high ≤ −2% | close / day high − 1 | exact |
| D. Sector-relative ≤ −1% | stock return − sector ETF return | exact |
| E. Late relative volume ≥ 1.5× | **proxy:** day volume / median 20d volume | measured in `calibrate.py` |
| F. No earnings in the hold window | Nasdaq calendar, AMC tonight + BMO tomorrow | exact |

Entry is the signal-day **close** (the spec's 3:55 PM is unobservable here) and exit is the next
session's **open** — spec §7 variant A, the variant that isolates the overnight effect.

**2. The 60-day window, exact.** `calibrate.py` runs the unmodified spec on real 5-minute bars:
3:50 PM signal, 3:55 PM entry, and all three exits (9:30 / 9:35 / 10:00). It measures the entry
bias the daily run carries, the exit-timing difference, and how faithfully the two proxies track
the intraday quantities they stand in for.

## Disclosed biases

- **Entry-at-close is optimistic** vs the spec's 3:55 PM entry, because a name still being sold
  into the bell is cheaper at 4:00 than at 3:55. Quantified by `calibrate.py`, not hand-waved.
- **The EXTENDED universe slice is survivorship-dirty.** It is built from *today's* $2B+
  listings, so it holds survivors only and implicitly knows which companies later grew. Every
  trade carries a `segment` and `era` label and results are reported split, never blended —
  see FINDINGS Addendum 2. The `SP500_PIT` slice remains the clean lower bound.
- **Survivorship (index slice): materially reduced, not eliminated.** Membership is point-in-time from
  `fja05680/sp500`, which retains names that later failed (SIVB, FRC) or were acquired (TWTR) —
  this is the first backtest in this repo with a PIT universe. But Yahoo serves no prices for a
  minority of removed names, and those sessions drop out. The count is in the run manifest and
  on the dashboard; read it before quoting any number.
- **Sector map is current, not point-in-time.** The 2018 Communication Services reshuffle is
  applied retroactively; names no longer in the index fall back to SPY, which makes filter D
  strictly harder to pass rather than easier.
- **Proxy filters B and E are looser than the spec's**, so the full-history run trades a
  somewhat wider set than the true rules would.
- **No borrow, no market impact, no partial fills.** Costs are a flat per-side bps charge.
- **`limit`-free exits.** Per spec §8 no overnight stop is simulated, because an overnight stop
  cannot be assumed to fill.
