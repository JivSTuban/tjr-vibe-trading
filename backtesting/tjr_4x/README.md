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

---

## Iteration 2 — daily-bias engine ablation (2026-07-23)

Replaced the crude bias proxy with codable encodings of TJR's real top-down method (`docs/research/BIAS_METHOD.md`, lessons 34–36/50): **A** = structure (last confirmed daily BOS/CHoCH), **B** = A gated by premium/discount, **C** = A gated by draw-on-liquidity, plus an optional **4H confluence** filter. Same candidate setups generated once (`apply_bias_filter=False`), each bias variant applied as a post-filter (`bias_sweep.py`).

| mode | trades | win% | exp_R (net) | PF | net_R | maxDD_R |
|---|--:|--:|--:|--:|--:|--:|
| current (proxy) | 129 | 33.3% | −0.616 | 0.47 | −79.4 | −78.0 |
| A structure | 192 | 32.8% | −0.514 | 0.51 | −98.6 | −107.8 |
| B premium/discount | 152 | 18.4% | −0.917 | 0.23 | −139.4 | −138.8 |
| **C draw-on-liquidity** | 139 | **41.0%** | **−0.326** | **0.67** | −45.3 | −57.6 |
| A + 4H | 152 | 34.2% | −0.458 | 0.55 | −69.7 | −73.5 |
| **C + 4H** | 88 | **42.0%** | −0.353 | 0.66 | **−31.1** | **−39.3** |

**Findings:**
- **C (draw-on-liquidity) is the best lever found so far** — win-rate 33%→41%, PF 0.47→0.67, net loss halved. It matches TJR's actual teaching (bias = the draw toward opposing liquidity, L50). C's net −0.326R + ~0.35R avg cost ⇒ **gross ≈ breakeven-to-slightly-positive** — the first hint of a real directional edge.
- **B (premium/discount) actively hurts** (18% win). The logic is correct (verified: long only in discount); the culprit is the **unresolved equilibrium reference** (OPEN_QUESTIONS "#1 gap") — a bad range definition makes P/D filtering worse than none. Do not use P/D until that's resolved.
- **4H confluence** modestly helps (A+4H > A; C+4H has the best drawdown, −39R).
- **Still no profitable mode** — but C roughly halved the loss. Combined with cost reduction (wider R / opposite-liquidity TP), C is the candidate most likely to cross into positive expectancy.

**Next:** promote C to the default bias, then iteration 3 = opposite-liquidity TP + min-stop filter (cut the ~0.35R cost tax) and re-measure C's gross vs net edge. Resolve the equilibrium reference before revisiting B.

---

## Iteration 3 — promote C, opposite-liquidity TP + min-stop filter (2026-07-23)

Mode **C (draw-on-liquidity)** is now the default bias (`config.bias_mode="C"`).
Added an `opposite_liquidity` exit model (TP = nearest OPPOSING liquidity level
beyond entry — causal, formed at/before the confirming BOS bar; skip if planned
`rr < min_rr` or no level), a `min_stop_pct` filter (skip tiny-stop setups whose
cost-per-R tax is disproportionate), and variable-R engine accounting
(`gross_R = |tp-entry|/|entry-sl|` on a TP hit, still exactly 2.0 for fixed 2R).
`find_trades` is re-run per config (`exit_sweep.py`).

| config | trades | win% | avg_rr | exp_R (net) | PF | net_R | maxDD_R |
|---|--:|--:|--:|--:|--:|--:|--:|
| C_fixed2R (iter-2 ref) | 139 | 41.0% | 2.00 | −0.326 | 0.67 | −45.3 | −57.6 |
| **C_fixed2R_minstop** (0.002) | 137 | 40.9% | 2.00 | **−0.129** | **0.84** | **−17.7** | **−32.8** |
| C_oppliq | 9 | 11.1% | 3.20 | −8.762 | 0.01 | −78.9 | −75.8 |
| C_oppliq_minstop | 3 | 33.3% | 1.22 | −1.008 | 0.16 | −3.0 | −2.0 |
| C_oppliq_minstop_rr1.5 | 0 | — | — | 0.000 | — | 0.0 | 0.0 |
| C4h_oppliq_minstop | 2 | 50.0% | 1.13 | −0.703 | 0.28 | −1.4 | −2.0 |

**Findings:**
- **No config reaches positive net expectancy.** The best is
  **C_fixed2R_minstop**: exp_R −0.129, PF 0.84, net −17.7R, maxDD −32.8R — the
  min-stop filter (drop stops < 0.2% of price) cut the loss ~60% vs the iter-2
  reference by removing the highest cost-per-R setups. It is *close* to
  breakeven but still negative after costs.
- **Opposite-liquidity TP is a bust here.** Unfiltered it collapses to 9 trades
  at 11% win / PF 0.01 — the nearest opposing 15m swing/prior-day level is
  usually very close to entry, so most setups are either skipped (rr<1) or take a
  thin TP that the tight structural stop still beats. Adding min-stop leaves only
  3 trades; `rr≥1.5` leaves **zero**. The opposing-pool distance is simply
  smaller than 1R for this setup on BTC 5m.
- **Sample sizes for the opp-liq variants (0–9 trades) are far too small to be
  meaningful** — treat those rows as "the filter starves the strategy," not as
  performance estimates.

**Conclusion:** the min-stop filter is a real, cheap improvement (net −45→−18R)
and stacks on C; the opposite-liquidity exit as specified does not fit BTC 5m's
tight-stop / near-pool geometry. Still no positive edge. All course rules remain
**proposed**.

---

## Iteration 3 — exit model + min-stop filter (2026-07-23)

Promoted **C (draw-on-liquidity)** to the default bias, then tested a min-stop-distance filter and an opposite-liquidity TP (`exit_sweep.py`). Same detection, per-config re-run.

| config | trades | win% | avg_rr | exp_R (net) | PF | net_R | maxDD_R |
|---|--:|--:|--:|--:|--:|--:|--:|
| C_fixed2R (iter-2) | 139 | 41.0% | 2.00 | −0.326 | 0.67 | −45.3 | −57.6 |
| **C_fixed2R_minstop** | 137 | 40.9% | 2.00 | **−0.129** | **0.84** | **−17.7** | **−32.8** |
| C_oppliq | 9 | 11.1% | 3.20 | −8.76 | 0.01 | −78.9 | — |
| C_oppliq_minstop | 3 | 33.3% | 1.22 | −1.01 | 0.16 | −3.0 | — |
| C_oppliq_minstop_rr1.5 | 0 | — | — | — | — | 0.0 | — |
| C4h_oppliq_minstop | 2 | 50.0% | 1.13 | −0.70 | 0.28 | −1.4 | — |

### The milestone: a positive GROSS edge
**C + min-stop (0.2%)** is the best config found and the story changes here:
- win-rate **40.9% at 2R** clears the 33.3% breakeven by **+7.6 points** ⇒ **gross expectancy ≈ +0.227R/trade** — the strategy finally beats random.
- net is still **−0.129R/trade**, but that gap is now **entirely execution cost** (~0.356R/trade), not a missing edge. PF 0.84, net loss cut ~78% from the original −79R baseline.
- The min-stop filter dropped only **2** trades (139→137) yet removed ~28R of loss — those were **degenerate near-zero-stop setups** (entry ≈ SL) whose cost-in-R blew up to ~14R each. Filtering them is the correct fix, not curve-fitting.

### Opposite-liquidity TP fails on BTC 5m
The nearest opposing pool is usually **< 1R away**, so it starves (0–9 trades) — either skipped (rr<min_rr) or a thin TP the tight stop beats. Not viable as encoded (single-source pools + 15m pivots); a richer liquidity universe is untested.

### Where the edge now lives — it's a COST problem
Gross is positive; the last barrier is the ~0.36R/trade fee+slippage tax on tight stops. Next levers (iteration 4): **limit/maker entries** (the entry is already a limit into an FVG/OB — model maker fees, not taker), **higher R targets / partial scale-out**, and a **wider min-stop + fewer-better trades**. Then IS/OOS split to confirm the +0.23R gross edge is stable, not in-sample luck.

---

## Iteration 4 — realistic maker/taker cost model + IS/OOS split (2026-07-23)

Made cost **outcome-aware** and executes-as-modelled: the entry is a **limit** resting at the FVG/OB edge (price must trade INTO it) ⇒ **maker**; the TP is a **limit** ⇒ maker; the SL is a **stop→market** ⇒ **taker + slippage**. `maker_fee_pct=0.02%`, `taker=0.05%`, `slip=0.05%`. Funding excluded (intraday holds). The best config (**C bias + 0.2% min-stop, fixed 2R**) is run ONCE for 137 closed trades, then the CLOSED trades are split 80/20 by entry_time (cutoff **2026-04-10**, IS=103 / OOS=34) and re-scored per window/cost-model (`cost_oos_sweep.py`).

| window | cost_model | trades | win% | gross_expR | net_expR | PF | net_R |
|---|--:|--:|--:|--:|--:|--:|--:|
| FULL | taker_only | 137 | 40.9% | +0.226 | −0.129 | 0.84 | −17.7 |
| **FULL** | **maker_taker** | 137 | 40.9% | +0.226 | **+0.070** | **1.10** | **+9.6** |
| IS | taker_only | 103 | 38.8% | +0.165 | −0.171 | 0.79 | −17.6 |
| IS | maker_taker | 103 | 38.8% | +0.165 | +0.012 | 1.02 | +1.3 |
| OOS | taker_only | 34 | 47.1% | +0.412 | −0.004 | 0.99 | −0.1 |
| **OOS** | **maker_taker** | 34 | 47.1% | +0.412 | **+0.245** | **1.37** | **+8.3** |

**Findings:**
- **Under maker_taker, FULL net expectancy goes POSITIVE for the first time: +0.070R/trade (PF 1.10, +9.6R).** Charging the limit entry + limit TP as maker (not taker) roughly halves the round-trip tax versus taker_only and flips the sign — the gross edge was there; taker fees were eating it.
- **The gross edge is stable, not overfit.** IS gross +0.165R (n=103) vs **OOS gross +0.412R (n=34)** — OOS is *stronger*, not collapsed (Δ +0.247R). No sign of in-sample luck in the entry logic itself. Both windows are net-positive under maker_taker.
- **Biggest caveat:** the min_stop 0.2% threshold was chosen from a full-sample diagnostic (mild in-sample leakage), and **OOS n=34 is small** — a +0.41R OOS gap on 34 trades is well within sampling noise, so the honest read is "edge stable and plausibly real, magnitude uncertain." The maker-fill assumption also presumes the limit entry/TP actually rest and fill without being crossed — realistic for FVG/OB retraces but not guaranteed in fast markets. **All rules remain `proposed`; this is research, not a live green-light.**

---

## Iteration 5 — walk-forward + cost-mix stress + ETH holdout (2026-07-23)

The credibility test for the C-bias + min-stop + 2R edge. Best config held fixed (no retuning). `run_validation.py`.

**Walk-forward (6 equal-time folds, maker r=0):** gross positive in **3 of 6** folds, and *concentrated*: fold 1 +0.731R (57.7% win) does the lifting, fold 4 is **−0.182R** (27% win), folds 2–3 have **zero trades** (a real ~5.5-month dry spell — equal-time folds expose density clustering). → **not temporally consistent.**

**Cost-mix stress** (fraction of entries filled taker via `entry_taker_ratio`):
| scenario | FULL net | OOS net (n=34) | ETH net (n=89) |
|---|--:|--:|--:|
| optimistic (all maker) | +0.070 (PF 1.10) | +0.245 (1.37) | +0.191 (1.29) |
| **realistic (50% taker)** | **−0.001 (1.00)** | +0.162 (1.23) | +0.136 (1.19) |
| pessimistic (all taker) | −0.072 (0.91) | +0.079 (1.11) | +0.080 (1.11) |

**ETH instrument-holdout** (same cfg, never tuned on ETH): 89 trades, win **43.8%**, gross **+0.315R**, and **net-positive under all three cost scenarios** — cleaner than BTC full-sample.

### Verdict (honest)
- **There is a real directional signal.** It **transfers to ETH** (an untuned instrument) and holds in BTC OOS across every cost assumption — that's not what noise does. The C-bias (draw-on-liquidity) + min-stop setup finds better-than-random entries.
- **But it is NOT robust yet.** The BTC full-sample edge is **fee-fragile** (breakeven at a realistic 50% taker mix) and **time-concentrated** (one fold carries it; a losing regime in late-2025; a 5.5-month dry spell). Recent regime + ETH look favorable; older BTC does not.
- **Small samples** (OOS n=34, ETH n=89) mean magnitudes are uncertain.

**Not a live green-light.** This is a promising-but-fragile research edge. Before trusting capital: broaden to **many instruments + multiple years/regimes**, use **equal-trade-count walk-forward**, and require robustness to a **realistic maker/taker mix** — then, only if it survives, the PRD §27 **shadow-mode** gate. All rules remain `proposed`.
