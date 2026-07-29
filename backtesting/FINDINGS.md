# Crypto Edge Research — Consolidated Findings

**A six-experiment, evidence-first search for a tradable crypto edge — and the honest conclusion.**

Status: research only. No live execution, no API keys, nothing approved. All backtests are
look-ahead-safe and cost-aware; every strategic claim is backed by an adversarially-verified
research pass (25 claims each, 3-vote refutation).

---

## TL;DR

We tested six strategies across two families (directional and structural) on 8 large-cap perps,
and cross-checked each against dedicated deep-research. **Every retail-taker-accessible edge lands
in the same thin band once costs are honest — roughly ±0.2R per trade, or low-single-digit APR.**

> The binding constraints on a solo crypto edge are **regime** (is there fuel?) and **execution**
> (can you get maker fills?) — **not signal cleverness.** No amount of picking a better direction,
> timing, or entry rule rescued a strategy whose gross edge was already thin.

That is the result. It was reached with zero capital at risk.

---

## The question

Does a retail/solo quant have a durable, cost-surviving edge in crypto — and if so, which one?
The trigger was an intuition ("what goes up must come down" — fade the day's biggest gainer). We
tested that literally, then followed the evidence wherever it led: to the opposite direction, to a
different strategy family, and finally to the execution layer itself.

## Method (why the numbers are trustworthy)

- **Look-ahead-safe event backtesting.** Ranking/decisions use only bars at or before the decision
  time; resolution starts the *next* bar. Verified by unit tests per module.
- **Honest, outcome-aware cost accounting.** Fees + slippage charged per leg at actual fill prices,
  expressed in R. Maker vs taker modeled explicitly. Funding modeled from **settled** rates
  (`fetch_funding_rate_history`), not the estimated endpoint.
- **Robustness, not a single number.** Equal-count walk-forward folds, per-instrument breadth, and
  cost/funding sensitivity bands on every result — a headline is only trusted if it survives them.
- **Adversarial research.** Three deep-research passes (frameworks, mean-reversion, strategy edges),
  each fanning out 5 search angles → ~20 sources → 25 claims → 3-vote refutation before synthesis.

**Data.** 8 Binance USDⓈ-M perps (BTC, ETH, SOL, BNB, XRP, ADA, DOGE, LINK), 5m bars, ~18 months
(Jan 2025 – Jul 2026). Funding: ~6 months (H1 2026) settled rates from Gate (Binance funding
endpoint is geo-blocked from our environment; rates are arbitrage-pinned across venues).

---

## Results — six experiments

| # | Experiment | Family | Gross | Net (realistic) | Verdict |
|---|---|---|---|---|---|
| 1 | **TJR-4X** SMC setup | directional | +0.216 R | +0.040 R (PF 1.06, 50% taker) | Real, broad, thin — maker-gated |
| 2 | **FADE** top gainer (short) | directional | −0.018 R | −0.289 R (PF 0.70, taker) | Dead — 76% continuation |
| 3 | **RIDE** top gainer (long) | directional | +0.036 R (PF 1.12) | −0.011 R taker / +0.007 R maker | Real gross, ~breakeven net, 1-coin |
| 4 | **Funding carry** (always-on) | structural | +0.83% APR | +0.23% taker / +0.67% maker | Real edge, no fuel this regime |
| 5 | **Funding-timed** (per-interval) | structural | — | −53% APR | Churn trap — never toggle |
| 6 | **Gated carry** (hysteresis) | structural | — | −5.62% taker / −0.67% maker | Whipsaws in a fuel-less regime |

### 1. TJR-4X — the SMC intraday setup (prior work)
Daily draw-on-liquidity bias → 15m sweep → BOS/MSS → FVG/OB entry → 2R TP. 881 pooled trades,
8/8 instruments gross-positive, transfers to instruments never tuned on. But pooled net at
realistic (50%-taker) execution is only **+0.040 R (PF 1.06)**; 4/8 clear realistic costs, 6/8
walk-forward folds positive. **Real but low-margin; net hinges on maker fills.** Canonical detail:
[`tjr_4x/FINDINGS.md`](tjr_4x/FINDINGS.md).

### 2. FADE — short the day's biggest gainer
The literal "what goes up must come down." 179 trades, **win rate 24%** — the faded gainer closed
lower only a quarter of the time, i.e. **76% kept running (continuation).** Gross −0.018 R (noise),
net −0.289 R after fees. Walk-forward 1/6 folds positive, 7/8 instruments net-negative. **Dead —
and the wrong sign.** Confirmed by research (crypto MAX effect is *positive* for liquid majors).

### 3. RIDE — long the same gainer (the flip)
Same universe, opposite direction. Win rate flips to **43.5%**, gross **+0.036 R (PF 1.12)** — a
genuine continuation edge before costs. But net is ~breakeven (−0.011 R taker, +0.007 R with maker
entry), and the entire positive net is carried by **one instrument (XRP, +8.9 R; strip it → −7.6 R)**
in one regime. **Direction is right, edge is real gross, but too thin and too concentrated to trade.**

### 4. Funding carry — delta-neutral (long spot / short perp)
The top "survivor" from the strategy-edges research. Harvest perp funding, market-neutral. Gross
**+0.83% APR**, net **+0.23%** (taker) / **+0.67%** (maker), funding positive 58.7% of intervals.
The killer: **BTC funding averaged 0.086 bps/8h — ~10× below the classic-neutral 1 bps.** A
structurally real edge with **no fuel in this compressed regime.** Best LINK +2.45%, BNB +1.77%;
worst SOL −2.35%. Detail: [`funding_carry/`](funding_carry/).

### 5–6. Timing the carry — both variants lose
- **Per-interval timing** (hold when last funding ≥ 0): 150–200 toggles × 0.15% → **−53% APR.**
  When the signal is worth 0.08 bps and a round-trip costs 30 bps, *never toggle.*
- **Regime gate with hysteresis** (enter on elevated trailing funding, exit below a lower band):
  **−5.62% APR (taker), −0.67% (maker).** The enter-threshold sweep is monotonic toward zero — the
  only "profitable" gate is one tuned so high it never trades. In a choppy near-zero regime the
  signal whipsaws the band; there were no *sustained* elevated periods to gate on.

### The execution test (isolating the fee tax)
Re-running carry at maker legs (0.08% round-trip vs 0.30% taker): always-on **+0.23% → +0.67%** (~3×),
gated **−5.62% → −0.67%** (~8× less bad). Maker is the correct lever — but +0.67% on ~1% gross
funding is still nothing. **Deadness decomposes to ≈ ⅓ fee tax, ⅔ dead regime.** You cannot
cost-optimize your way to a return that the gross edge doesn't contain.

---

## What the research said (3 adversarial passes)

1. **Mean-reversion on top gainers.** No cost-surviving short edge in either universe. Liquid majors
   show *continuation* (positive MAX effect); the real reversal lives in small-caps but is an
   illiquidity/pump-and-dump artifact that's un-shortable and cost-dominated. → predicted results 2–3.
2. **Retail bot tooling.** For execution realism, adopt an engine that models fills natively:
   **NautilusTrader** (queue-position fill models, `LatencyModel`, native funding settlement,
   backtest→live parity) or **hftbacktest** (L2/L3 book reconstruction) — not Freqtrade's naive
   zero-slippage default backtester. Storage: Parquet + DuckDB/QuestDB. The `fetch_funding_rate`
   estimated-vs-settled trap is real (use `_history`).
3. **Which edges actually survive.** *Pursue:* funding/basis carry and (funding-aware) market-making —
   both structural (a cash flow / a paid service), not predictions. *Avoid:* triangular &
   cross-exchange arb (arbitrage-free net of fees for retail), CEX-DEX/MEV (gated behind block-builder
   integration), grid/DCA (disguised short-vol), listing pumps (avg +54% then 89% dump), cointegration
   pairs (overfit headline; robust variant ~9% APR, Sharpe ~0.95).

---

## The meta-lesson

Plot all six on one axis and they collapse to a point: **directional edges (1–3) are noise-to-thin
and die at the cost layer; the structural edge (4) is real but regime-gated and, in a compressed
funding quarter, also thin.** Cleverness at the signal layer (fade→ride) and the timing layer
(always-on→gated) changed nothing. The two levers that *did* move the number — **maker execution**
and **regime** — are exactly what the tooling and strategy research independently pointed at.

This is the lesson most retail traders pay tuition (real losses) to learn. Here it cost nothing.

## What a serious/live version would require

1. **L2/order-book data**, not 5m OHLCV — fills can only be modeled honestly against the book.
2. **A real execution engine** (NautilusTrader) with queue-position fill modeling, latency, and
   native funding — stop hand-rolling toy backtesters.
3. **Regime detection** — funding carry is worth running only when funding is *persistently* elevated
   (bull regimes: 0.05–0.10%/8h → 20–40% APR, where maker fees are the difference-maker).
4. **A different bot shape** — the surviving edges are market-making / carry (be the liquidity, hold
   the cash flow), not direction-picking. That is a materially different system than this repo.
5. **Multi-year, multi-regime data** and shadow-mode before any capital.

---

## Reproduce

```bash
python3 -m backtesting.tjr_4x.run_multi          # TJR-4X breadth
python3 -m backtesting.tjr_4x.run_validation     # TJR-4X walk-forward / cost
python3 -m backtesting.top_gainer_fade.run       # FADE vs RIDE (+ maker ladder) → runs/*.html
python3 -m backtesting.funding_carry.run         # carry: always-on / timed / gated / maker → runs/*.html
```

Each writes a self-contained HTML dashboard under its package's `runs/`. Tests: `pytest backtesting/`.

## Guardrails

No live execution. No API keys (public data only). Zero rules approved — every strategy here is a
research artifact, not a trading signal. Raw course transcripts are gitignored (copyright).
