# TJR 4X — v0 event backtester

Look-ahead-safe research backtester for **one** approved setup (the "4X strat"), per `knowledge/decisions/0001-tjr-4x-backtest-thresholds.md`. Reuses `smartmoneyconcepts` detectors. **Research only — the underlying course rules remain `proposed`; a profitable result here would not approve anything for live.**

## Run
```bash
python3 -m backtesting.tjr_4x.run --months 18        # fetches BTC-USDT-PERP 5m via ccxt, writes runs/<ts>/
python3 -m pytest backtesting/tjr_4x/tests/ -q        # 12 unit tests (fixtures, no network)
```

## Method (all approved params)
BTC-USDT-PERP · 1D bias / 15m setup+sweep / 5m entry · pivot-3 swings · sweep = wick pierce + body close-back within 1 bar · body-close BOS/CHoCH confirmation · FVG/OB retrace entry · SL beyond sweep +0.1% · fixed **2R** TP · bias-aligned only · max 1 position · costs 0.05%/side fee + 0.05% slippage. The engine applies no look-ahead (forward-only from entry; strategy creation is causality-tested); exits fill at the exact SL/TP price; when SL & TP fall in one 5m bar it counts as SL-first (conservative).

## v0 result — 2025-01-29 → 2026-07-23 (155,520 bars)
| metric | value |
|---|---|
| trades | 129 (~1.7/week) |
| win_rate | **33.3%** |
| gross expectancy | **≈ +0.05R/trade** (+6R total — noise) |
| net expectancy | **−0.62R/trade** (−79R total) |
| profit_factor | 0.47 |
| avg win / avg loss | +1.61R / −1.73R (net of cost) |
| max consecutive losses | 8 |

## Interpretation (honest)
- **33.3% at 2R is exactly the pre-cost breakeven** (`1/(1+2)`). Gross return is ~flat → **this naive encoding has no measurable edge** over BTC 5m before costs.
- **Costs dominate.** Structural stops are tight (~0.13–0.26% of price), so a 0.10% round-trip is ~0.6R/trade — that's the whole difference between breakeven and −79R.
- **This is a floor, not a verdict on TJR.** v0 deliberately guesses the unresolved `OPEN_QUESTIONS` thresholds and **disables session/news gating** (24/7 crypto ≠ TJR's London/NY + CPI/PPI model). It also uses a crude daily-bias proxy and enters any FVG/OB rather than TJR's discretionary building-block selection.

## What would move the number (next steps, not yet done)
1. **Session/news gating** — restrict to specific hours; TJR's edge is session-timing-heavy.
2. **Higher R targets / wider structural stops** — cut the fee-per-R tax; test opposite-liquidity TP (approved but not yet built) and the L54 scale-out.
3. **Bias quality** — replace the proxy with the real top-down 1D→4H bias rules.
4. **Resolve OPEN_QUESTIONS** (prominent-level, equilibrium reference-swing, 30m-sweep precondition) and re-run.
5. **In-sample / out-of-sample split + param sweep** — the harness supports it; not run for v0.

---

## Iteration 1 — session/kill-zone gating (2026-07-23)

Hypothesis: TJR's edge is session-timed, so restricting entries to London/NY windows should help. **Result: it does not.** Same 941 candidate setups, filtered by UTC session windows (`session_sweep.py`):

| preset | trades | win% | exp_R (net) | PF | net_R |
|---|--:|--:|--:|--:|--:|
| none (24/7) | 129 | 33.3% | **−0.616** | 0.47 | −79.4 |
| london (07–10) | 119 | 31.1% | −0.692 | 0.40 | −82.4 |
| ny_am (12–15) | 50 | 38.0% | −1.315 | 0.31 | −65.7 |
| london+ny_am | 67 | 32.8% | −1.461 | 0.26 | −97.9 |
| kill_zones (07–09,12–14) | 86 | 34.9% | −1.101 | 0.32 | −94.7 |
| ny_full (13–20) | 104 | 37.5% | −0.817 | 0.43 | −84.9 |

**No preset beats the 24/7 baseline on expectancy.** NY windows raise win-rate (37–38%) but expectancy gets *worse* — small-sample R-quality drops. Conclusion: on 24/7 BTC, TJR's session concept (an FX/index liquidity+news artifact) is **not** the missing edge.

**Root-cause diagnostic (all 941 setups):** median stop distance 0.53% of price, median cost 0.38R (only 4% of setups have <0.10% stops). So costs are a real drag but *not* the whole story — **gross expectancy is ~0 (33% at 2R = breakeven), i.e. the entry logic has no edge over random.** The next lever is **setup quality** (real top-down bias, discretionary building-block selection, opposite-liquidity TP), not timing. Caveat: fixed-UTC windows ignore DST (an OPEN_QUESTION).
