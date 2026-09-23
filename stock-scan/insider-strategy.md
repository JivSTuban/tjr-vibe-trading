# Small-Cap Insider-Buy Strategy — research + spec (2026-08-06)

Deep-research verdict for a proposed `/stock-scan insider` mode. Grounded in REPL. Cited, adversarially verified (19/25 claims confirmed, 6 killed as overreaches).

## Verdict (honest)
Insider-buy-led small-cap selection has a **REAL but MODEST, cost-fragile edge** — not pure survivorship hindsight, but far weaker than "70–80% alpha" implies, and the raw signal must be heavily filtered to be tradeable. **Insider buys are a confirmation layer, NOT a 2x predictor. Catalysts drive the 2x.**

## The REPL reality check (your example CONTRADICTS the thesis)
- REPL = **Replimune**, pre-revenue oncolytic-immunotherapy biotech. Value = single binary asset (RP1 melanoma).
- The ~2x (+127–133%, Jul 31 2026) was an **FDA AdCom 10-3 vote** ahead of the Aug-2 PDUFA — a **catalyst**, not insider buying.
- Before the move, insiders were **SELLING** (CCO Sarchi −12,000 sh @ $9.24, Jun 1; a 6-exec sell cluster May 20). The one April "Form-4 cluster" coincided with a **−75% CRASH** on a second CRL.
- Takeaway: **the catalyst did all the work; the insider filings were noise or bearish.** A pure insider-buy screen would NOT have caught REPL.

## What actually has an edge (the evidence)
1. **Trade type is everything.** >50% of insider trades are calendar-timed "routine" liquidity trades with ~zero predictive power. ALL alpha is in the **"opportunistic" open-market P purchases** — ~82bps/mo in the seminal Cohen-Malloy-Pomorski (2012, JoF), but **decayed to ~0.3–0.4%/mo** in 2008–2024 replications. The *mechanism* is robust; the *payoff* shrank.
2. **Slightly STRONGER in the smaller-cap half** (0.80%/mo small vs 0.55%/mo large, opportunistic buys). Routine buys insignificant in both.
3. **Alpha does NOT fully dissipate before retail can act — in genuine microcaps.** Zhao/Stanford microcap preprint (arXiv 2602.06198): 17,237 open-market P buys, $30M–$500M cap, 2018–2024. XGBoost on Form-4 features → **out-of-sample AUC 0.70**, return measured strictly from **t+1 (after disclosure)**. Plausibly because thin coverage / wide spreads slow incorporation. BUT: precision **0.38** (~2 false positives per winner); best-bucket 6.3% CAR erodes to **~3.3% net of a 2% spread + 1% impact**; single unrefereed preprint, one OOS year. **Treat as hypothesis to backtest, not law.**
4. **Momentum = confirmation, not falling-knife** (low confidence, 2-1 vote): buys disclosed *after* a >10% run outperformed post-decline buys. Backtest before trusting; may be a mechanical artifact.

## STRATEGY SPEC — `/stock-scan insider` mode
**Discovery filters (hard):**
- Major-exchange only (NYSE/Nasdaq, **no OTC**) · price **≥ $5** (dodge penny/pump universe)
- Market cap **~$50M–$2B** (small/micro where the edge lives, above nano manipulation zone)
- Min avg dollar-volume / float liquidity (executable, bounded spread) · **current/complete SEC filings**

**Insider-buy gate (primary signal, hard-gated):**
- **Open-market purchases only** — Form-4 code **`P`**. Exclude grants, option exercises, ALL sells.
- Prefer a **CLUSTER** (≥2 distinct insiders buying in a short window) — the higher-conviction subset.
- Weight **C-suite (CEO/CFO) > directors**; weight **buy-size relative to salary**.
- Bias toward **"opportunistic"** (non-routine, non-calendar) buyers — routine = ~zero alpha.

**Catalyst confirmation (REQUIRED, independent of the filing):**
- Must have an identifiable near-term driver: biotech data/FDA (AdCom/PDUFA/BLA), earnings surprise/PEAD + rising estimates, contract win, or short-squeeze setup. **REPL proves catalysts, not filings, drive 2x.**
- Momentum (buy after >10% run / near highs) = confirmation, not a knife entry.

**Anti-knife / anti-pump gates (disqualify pre-entry):**
- Dilution / at-the-market offering / toxic convertible / going-concern flag.
- Pump-and-dump promotion pattern; opaque or stale filings.

**Sizing + invalidation:**
- **Small / defined-risk** (thin liquidity + binary biotech = fat tails). Size for full-loss tolerance.
- Hard stop below the insider's avg buy price OR below the pre-catalyst base.
- **Catalyst failure (CRL / miss / lost contract) = immediate exit.**

## Open questions (backtest before trusting)
1. Does the ~3.3% net edge survive real execution + the ~2-day Form-4 filing lag at t+1 entry?
2. Is momentum-confirmation genuine or a mechanical artifact of the 10%-CAR target?
3. Does insider-cluster + catalyst beat **catalyst-alone**? (REPL suggests the catalyst may do all the work.)
4. What's the right "opportunistic vs routine" classifier for microcaps, computable free from EDGAR?

## Sources (primary)
- Cohen, Malloy, Pomorski, "Decoding Inside Information," J. Finance 67(3), 2012 — NBER w16454
- Zhao, "Insider Purchase Signals in Microcap Equities," arXiv 2602.06198 (Feb 2026)
- SEC / Cornell LII "Microcap Stock: A Guide for Investors" (pump-and-dump gating)
- SEC EDGAR CIK 1737953 (REPL Form-4s), 8-K exhibit tm2619037d1
