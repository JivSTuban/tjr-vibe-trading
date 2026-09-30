# Small-Cap Insider-Buy Strategy — research + spec (2026-08-06)

Deep-research verdict for a proposed `/stock-scan insider` mode. Grounded in REPL. Cited, adversarially verified (19/25 claims confirmed, 6 killed as overreaches).

## Verdict (honest)
Insider-buy-led small-cap selection has a **REAL but MODEST, cost-fragile edge** — not pure survivorship hindsight, but far weaker than "70–80% alpha" implies, and the raw signal must be heavily filtered to be tradeable. **Insider buys are a confirmation layer, NOT a 2x predictor. Catalysts drive the 2x.**

> **CORRECTIONS 2026-09-30** from `docs/research/INSIDER_CATALYST_AI_REVIEW.md`. Three items below
> were built on evidence that has since been withdrawn or refuted. Read the annotations before
> relying on points 1, 3, 4 or the momentum rule in the spec.
> - **The "buy after a >10% run" momentum rule rests on a WITHDRAWN result.** arXiv 2602.06198 v2
>   (Appendix E) formally withdraws v1's run-up headline: it does not replicate (0.2-point gap,
>   t=0.17). The 6.3% best-bucket figure in point 3 is that same withdrawn number.
> - **v2's own net verdict is negative.** Break-even round trip 5.2% against a 5.2% gross edge;
>   net of 3% the interval includes zero; trimming 56 trades above +50% cuts the mean to 1.6%;
>   3.27 of the 6.9-point gradient lands in the first session after filing (an overnight gap a
>   manual PH trader cannot take), and the reachable days 2-30 drift has t=1.70.
> - **"Decayed to ~0.3-0.4%/mo in 2008-2024" was refuted 0-3** in adversarial verification.
>   Treat it as unverified, not as fact.

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
- **Earnings-beat gate is now code** (2026-10-01): `engines/public_beat.mjs TICKER:DATE` returns BEAT / NO_BEAT / UNKNOWN for "a positive surprise public within the 90 days before the cluster" (the exact definition the re-test measured; tests in `engines/public_beat.test.mjs`). The older 25-day lookback in `universe_catalyst.mjs` would have missed 12 of the 24 proven cases. UNKNOWN (failed or empty feed) never means no beat.
- Must have an identifiable near-term driver: biotech data/FDA (AdCom/PDUFA/BLA), earnings surprise/PEAD + rising estimates, contract win, or short-squeeze setup. **REPL proves catalysts, not filings, drive 2x.**
- Momentum (buy after >10% run / near highs) = confirmation, not a knife entry. **WITHDRAWN 2026-09-30: this rule came from arXiv 2602.06198 v1, whose run-up result v2 formally withdrew (does not replicate, t=0.17). Do not use a prior run-up as confirmation.**

**Anti-knife / anti-pump gates (disqualify pre-entry):**
- Dilution / at-the-market offering / toxic convertible / going-concern flag. **Enforced by code, not prose** (2026-09-30): `engines/veto_extract.mjs` reads every 8-K / 8-K/A / 6-K in the last 90 days with exhibits, has a model label each event with a verbatim quote, verifies the quote exists in the filing, then has a second model (Haiku by default, tagged SAME-FAMILY; Codex is opt-in via `--p2 codex`) re-grade it. A form-name filter cannot do this (GME's 55.5M-share note exchange and RWT's $205M convertible never touched S-1/S-3/424B). Fail-closed: an unverifiable quote, an unread filing or a truncated filing list is `unknown`, never clear; if pass 2 is down a verified VETO stays a provisional veto. **Replayed 2026-10-01 on 23 historical insider + beat events (`backtesting/insider_cluster/VETO_REPLAY.md`): the 5 equity-raise vetoes had a +5.2% median and included two winners (+55%, +72%), so ordinary equity raises are a presumption the DD weighs, not a binding veto; other veto classes are untested and stay binding.** Known limits: no materiality test (a routine REIT ATM vetoes, e.g. ADC's $686M forward equity), 90-day window only, and a financial-statement period total (a cash-flow line) is a CAVEAT because it carries no event date. Tests: `engines/veto_extract.test.mjs`.
- Pump-and-dump promotion pattern; opaque or stale filings.

**Sizing + invalidation:**
- **Small / defined-risk** (thin liquidity + binary biotech = fat tails). Size for full-loss tolerance.
- Hard stop below the insider's avg buy price OR below the pre-catalyst base.
- **Catalyst failure (CRL / miss / lost contract) = immediate exit.**

## Open questions (backtest before trusting)
1. Does the ~3.3% net edge survive real execution + the ~2-day Form-4 filing lag at t+1 entry?
   **ANSWERED 2026-09-30: no.** v2 puts break-even cost at 5.2% vs 5.2% gross, and the part a t+1 buyer can reach has t=1.70 (t=1.23 above $5).
2. Is momentum-confirmation genuine or a mechanical artifact of the 10%-CAR target?
   **ANSWERED 2026-09-30: withdrawn by its own author** (v2 Appendix E, t=0.17).
3. Does insider-cluster + catalyst beat **catalyst-alone**? (REPL suggests the catalyst may do all the work.)
   **ANSWERED 2026-09-30, CORRECTED 2026-10-01 to NOT ESTABLISHED** (`backtesting/insider_cluster/RETEST_N39.md`): on matured trades only, insider + a public beat is +5.23% median (n=23) against catalyst-alone +3.25% (n=221), a +1.99pp difference with a 90% CI of [-3.48, +6.81] that fails the pre-committed 3pp rule. The first reading ("yes, narrowly", +3.54pp) used trades with no full 60-day window. The robust parts are the beat requirement and the refuse below. First reading, for the record: Corrected (real announcement date, t+2 open, ex-microcap, 150 bps): cluster + a beat already public = +4.79% median, n=24, vs catalyst-alone +1.26%. The ~3.5pp added value is not significant at 90% and fails if the top two winners are dropped. Cluster WITHOUT a catalyst = -3.04% median, 41% hit: never trade it.
4. What's the right "opportunistic vs routine" classifier for microcaps, computable free from EDGAR?
   **ANSWERED 2026-09-30:** Cohen-Malloy-Pomorski exactly: needs a trade in each of the 3 prior years; routine = same calendar month 3+ consecutive years; everyone else opportunistic; labels set at year start. Free from EDGAR Form 4 XML (2003+), but needs per-insider history keyed by reporting-owner CIK, which openinsider cannot supply. Only 36% of purchases qualify as opportunistic.

## Sources (primary)
- Cohen, Malloy, Pomorski, "Decoding Inside Information," J. Finance 67(3), 2012 — NBER w16454
- Zhao, "Insider Purchase Signals in Microcap Equities," arXiv 2602.06198 (Feb 2026)
- SEC / Cornell LII "Microcap Stock: A Guide for Investors" (pump-and-dump gating)
- SEC EDGAR CIK 1737953 (REPL Form-4s), 8-K exhibit tm2619037d1
