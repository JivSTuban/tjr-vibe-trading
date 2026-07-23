# TJR-4X Backtest — Banked Findings (2026-07-23)

**Status: research complete for now. A real but low-margin edge. NOT live-ready. Nothing approved — all rules `proposed`.**

This is the canonical summary. Blow-by-blow detail + tables are in `README.md`; per-config numbers in `runs/`.

## What was tested
One approved TJR setup — the "4X strat" (decision `knowledge/decisions/0001`): daily draw-on-liquidity **bias** → 15m liquidity **sweep** (pivot-3 + body close-back) → body-close **BOS/MSS** → **FVG/OB** entry → **SL** beyond the sweep +0.1% → **2R** TP. Encoded as a look-ahead-safe event backtester (`strategy.py`/`engine.py`), reused `smartmoneyconcepts` detectors. 45 unit tests incl. causality guards.

## The result
| dimension | finding |
|---|---|
| **Edge exists?** | **Yes (gross).** 8/8 perps gross-positive; pooled **881 trades, +0.216R/trade**; equal-trade walk-forward 6/8 folds positive. Transfers to instruments it was never tuned on (ETH/XRP/ADA). Not a BTC/ETH artifact. |
| **Profitable after costs?** | **Barely / not reliably.** Pooled net@realistic (50% taker) **+0.040R, PF 1.06**; only **4/8** instruments clear realistic fees. BTC full-sample ≈ breakeven; BNB/LINK net-negative. |
| **Robust across time?** | Partially. 6/8 equal-trade folds positive; one losing regime (late-2025). Single 18-month window — no multi-year/regime coverage yet. |
| **Best / worst** | XRP (+0.27R net, PF 1.43), ETH (+0.14R) / BNB (−0.18R), LINK (−0.08R). |

**Progression:** 33% breakeven-noise → draw-on-liquidity bias (edge appears, win 33→41%) → min-stop filter (first +gross) → maker cost model (first +net) → validation (real, fragile on BTC alone) → 8-instrument breadth (real & broad, thin margin). PRs #1–8, all merged.

## Honest caveats (load-bearing)
- Net positivity **hinges on genuine maker fills** (limit entry/TP resting uncrossed). At all-taker fills the pooled edge is net-negative.
- `min_stop 0.2%` was picked from a full-sample diagnostic (mild in-sample leakage).
- Small per-instrument samples (n=64–142); single 18-month regime; funding excluded; no latency/queue/partial-fill modeling; pooled metrics assume unlimited cross-instrument concurrency (not a single-account equity curve).

## Highest-value next work (NOT another cost/param sweep — that risks overfitting)
1. **Execution realism** — the pivotal unknown. Model whether the limit entry actually rests-and-fills (maker) or gets crossed (taker) under real 5m paths; add latency, partial fills, funding. This single question decides the entire net picture.
2. **Setup quality** — resolve `knowledge/conflicts/OPEN_QUESTIONS.md` (equilibrium reference "#1 gap", the 30-min-sweep precondition L55, prominent-level definition) to get *better entries*, not cheaper costs. Higher gross edge is the durable lever.
3. **Multi-year / multi-regime** data (2022 bear → 2026) before trusting magnitude.
4. Only if all three hold → PRD §27 **shadow-mode** gate (proposals, no orders), then testnet.

## Reproduce
```bash
python3 -m pytest backtesting/tjr_4x/tests/ -q            # 45 tests
python3 -m backtesting.tjr_4x.run                          # single-instrument (BTC) backtest
python3 -m backtesting.tjr_4x.run_validation               # walk-forward + cost stress + ETH holdout
python3 -m backtesting.tjr_4x.run_multi                    # 8-instrument breadth
```
