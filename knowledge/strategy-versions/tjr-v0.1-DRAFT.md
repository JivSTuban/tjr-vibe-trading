# TJR Strategy — v0.1

## STATUS: DRAFT — UNAPPROVED. Requires human review before ANY coding or backtest.

- Every rule below is **status: proposed**. None is `approved`.
- This is a synthesis of what TJR *teaches* across 55 extracted lessons — NOT a validated or tradeable spec.
- Safety-critical: nothing here authorizes execution. Do not derive an A+ scorer, detector, or backtest from this document until a human confirms each stage and resolves `knowledge/conflicts/OPEN_QUESTIONS.md`.
- Citations use folder index `LNN` = `research/course/tjr-boot-camp/NN-<slug>/`. (Manifest title "Day NN-1".)
- PRD §14 A+ scorer components are mapped per stage. Total = 100; threshold A+ ≥ 90; mandatory conditions cannot be bought out by score.

---

## Pipeline overview (as TJR teaches it)

`daily bias → mark HTF building blocks → session liquidity sweep → body-close BOS/MSS → building-block entry reaction → structure stop → building-block/liquidity target → risk gate`

The exemplar of the full chain (TJR's own words, L14 `[06:02]`):
> "Liquidity sweep → break of structure → trend forming → notice a fair value gap → FVG gets filled → lower-timeframe break of structure → we're in."

---

## Stage (a) — Daily-bias determination  → PRD §14: *Higher-timeframe bias (15 pts)*

**proposed:** Run top-down analysis weekly → daily → 4H → 1H → 15m → 5m (L34 `[00:45]`). Derive bias from **daily market structure**: daily uptrend or daily BOS-up → bullish; daily downtrend or daily BOS-down → bearish (L34). **Daily is authoritative for intraday** because these are intraday not swing trades — e.g. Gold weekly-bearish/daily-bullish → "we use the daily bias because we're trying to predict daily moves" (L34 example; L50 Gold long "trade the daily even though weekly is bearish").
- **proposed:** HTF power hierarchy monthly > weekly > daily; a lower-TF BOS opposing HTF trend is a *retracement*, not a flip (L06 `[22:41]`).
- **status:** proposed. **Blocker:** bias-flip vs retracement threshold unresolved (L36↔L41) — see OPEN_QUESTIONS.

## Stage (b) — Mark HTF building blocks (OB / FVG / equilibrium)  → PRD §14: *Valid area of interest (10 pts)*

**proposed:** On the HTF, mark the draw-on-liquidity building blocks in the bias direction: **order block** (the leg that caused the last sweep/BOS, L20 `[03:10]`), **FVG/imbalance** (retracement target, L14 `[03:58]`), and **equilibrium** (50% of the reference swing; only look for longs in discount, shorts in premium, L26 `[08:13]`).
- **status:** proposed. **Blockers:** equilibrium reference-swing undefined; OB "leg vs single candle"; FVG 3-candle boundaries deferred; "prominent" high/low has no numeric formula (L12) — see OPEN_QUESTIONS.

## Stage (c) — Liquidity-sweep precondition  → PRD §14: *Liquidity sweep or event (15 pts, mandatory)*

**proposed:** Require a sweep of prominent session liquidity BEFORE any entry — session/30-min highs-lows (London, Asian), the sweep being the inducement that "liquidates" breakout traders then reverses (L08 `[04:14]`; L12 entry gate; L55 makes a **30-minute-high/low sweep a required 4X-strat component**). Exemplar: L54 GBPJPY swept London-session highs then Asian-session highs (buy-side) before the short.
- **status:** proposed. **Blocker:** sweep penetration/overshoot threshold undefined ("a couple of pips", qualitative); session clock times/timezone never stated — see OPEN_QUESTIONS.

## Stage (d) — Body-close BOS/MSS confirmation  → PRD §14: *Market-structure shift (15 pts, mandatory)*

**proposed (load-bearing):** Confirm BOS/MSS ONLY on a candle whose **CLOSE** is strictly beyond the target swing (close > swing high for up-BOS; close < swing low for down-BOS). **A wick alone is NOT a BOS** — a wick beyond a swing with no close beyond it is a liquidity sweep / fake-out (L06 `[07:54]`, `[23:58]`). Direction-conditional: in an uptrend arm the most-recent low; in a downtrend arm the most-recent high (L06 `[14:59]`).
- **proposed:** Displacement (PRD *Displacement 10 pts*) is the impulsive move producing the BOS/FVG; TJR does not quantify it — flag as gap.
- **status:** proposed. **Blockers:** strict-vs-equal at swing price; min penetration distance; BOS-vs-MSS-vs-CHoCH labeling — see OPEN_QUESTIONS.

## Stage (e) — Entry model  → PRD §14: *Fair-value gap or entry model (10 pts, mandatory)*

**proposed:** A bare **sweep + BOS is insufficient**; require a building-block reaction. Entry-tool hierarchy (L28 `[09:08]`): (1) primary = liquidity sweep + BOS/MSS; if missed → (2) first retracement = **order block** (instant entry on tap); → (3) **FVG** (enter on reaction to the fill); → (4) **equilibrium**-confirmed OB/FVG. TJR prefers a discounted/premium retracement entry into an OB/FVG over entering on the BOS when the BOS gives poor R:R (L28 `[13:55]`). FVG is a *secondary* entry only (L14 `[03:58]`). Lower-TF BOS after the fill triggers entry (L14 `[06:02]`).
- **status:** proposed. **Blocker:** "equilibrium entry — of which leg?" undefined (L41); FVG-in-discount overlap undefined (L26).

## Stage (f) — Stop-loss  → PRD §14: *Clear invalidation (5 pts, mandatory)*

**proposed:** Structure-based, NOT fixed pips. "I almost always put my stop loss above the liquidity sweep… that's where price would be invalidated" (L38 `[01:24]`). SL = just beyond the swept extreme that preceded the setup (above swept highs for shorts, below swept lows for longs) + a spread buffer (L16 `[07:14]`; L50 placed SL "just below the wick of the rejection area").
- **status:** proposed. **Blocker:** exact spread-buffer size not quantified.

## Stage (g) — Take-profit  → PRD §14: *Reward-to-risk quality (5 pts, mandatory)*

**proposed:** TP1 **minimum 1:1** R:R ("that's kind of the goal", L37 `[06:39]`). Targets = building blocks / opposite-side liquidity: order block top/bottom, FVG edge/50%/full, prior prominent highs/lows — "price magnets," NOT arbitrary point/pip targets (L37 `[08:09]`; L12 target = nearest untapped opposite-side prominent level). **Scale out** across multiple liquidity pools; **move stop to break-even** on the runner (L16 `[07:18]`; L54: took 50% at TP1, moved to BE, ~$19k realized + ~$13k floating).
- **status:** proposed. **Blocker:** near-edge vs far-edge vs midpoint of OB/FVG inconsistent; 1:1 as hard reject vs soft flag undefined.

## Stage (h) — Risk  → PRD §14: *No conflicting condition (5 pts, mandatory); Approved market session (10 pts)*

**proposed (numbers as taught — SEE CONFLICT):** L13 teaches **1–3% per trade, preferred as 1–3% per DAY** (2×1.5%, or 1×1%, or 1×3%, or 3×1% all valid; zero-setup days = 0%) (L13 `[03:42]`, `[10:56]`). L39 lot-size formula: `lot_size = round( (account_balance × risk_pct) / (SL_pips × pip_value_per_lot), 2 )`, forex granularity 0.01 (L39 `[02:14]`). De-risk tier (**0.5%**) auto-selected on high-impact-news days / bank holidays / choppy conditions; beginners trade one pair only (L39 `[13:02]`).
- **News blackout:** source = Forex Factory calendar; red=high / orange=medium / yellow=low(ignore) / gray=holiday; filter to traded currencies (GBP/USD, GBP/JPY, gold=USD, S&P=USD); de-risk or avoid around high-impact releases (L19). L50 waited for high-impact news (consumer-sentiment) 30 min after open.
- **~1 trade/day / post-loss stop / news timing** are taught as discipline (L44, L11) but **not as hard numeric rules**.
- **⚠ CONFLICT with task brief:** the brief specifies "1% normal / 0.5% de-risk / 2% forbidden-for-students." The **extracted lessons say 1–3%**, not a 1%/2% cap. The 0.5% de-risk tier IS grounded (L39). The "2% forbidden for students" and "1% normal" caps are **NOT found verbatim** in the extracts. Routed to OPEN_QUESTIONS — do not code either version until confirmed.
- **status:** proposed.

---

## Exemplar trade cross-references

- **$19k GBPJPY WIN (L54):** Full down-alignment (weekly+daily bearish) → daily BOS-down → tapped a daily OB → swept London then Asian session highs (BSL) → 5m BOS (entered off 1m break candle) → TP1 at OB below → 50% off, stop to BE → ~$19k realized. TJR: "pinpoint copy-and-paste TJR 4X strat." The canonical positive template.
- **$9k SPX LOSS (L50):** Full multi-TF bullish alignment → sweep (deemed insufficient alone) → BOS-up (not entered alone) → retrace to equilibrium → strong rejection = entry, SL below the wick → stopped out, −~$9.5k. **Bias was correct** (price later filled the marked OB/FVG and rallied); TJR labels it an **EXECUTION error, not a bias error** — he used *lower-timeframe* liquidity instead of his marked *HTF* liquidity. The canonical "right bias, wrong execution" cautionary case → motivates the mandatory HTF-liquidity precondition in Stage (c).
- **Skipped A+ setups (L53 breakeven recap; L55 no-trades):** Days where the full 4X preconditions did not line up were **skipped / broke even**, not forced. L55 introduces the 30-min-sweep precondition as the missing component. Reinforces "zero-setup days = 0% risk" and patience over frequency.
