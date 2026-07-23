# Boot Camp Day 24: Order Blocks pt.3 — Summary

**Primary topic:** concept (technical) — final part of the 3-part Order Blocks series.
**Transcript source:** YouTube auto-captions (en-orig ASR), ~28 min. First ~6:30 is off-topic banter; technical content starts ~07:00. ASR heavily corrupts "order block" (rendered "order cox / cocky blocky / order [__]"), all normalized below.

## What TJR teaches

**OB definition recap** `[07:20]–[08:16]`: An order block is **the leg up or the leg down PRIOR to the break of structure** (to the upside or downside) — i.e. the price range where all the orders got filled, which is "pretty much the move that causes the liquidity sweep." The liquidity sweep happens → orders get filled → price breaks structure (a **market structure shift**). When price later returns to that range, market makers/banks who filled orders there before fill again and push price in the intended direction.

**HOW TO LABEL / BOX AN ORDER BLOCK** — the new material of this lesson `[09:19]–[12:16]`:
- **Method 1 (beginner-recommended):** box off the **entire move** — the whole leg down prior to the up-move (bullish OB) or whole leg up prior to the down-move (bearish OB). Explicitly recommended for beginners: "don't try to be a pro at something you suck at… mark out the entire leg" `[25:19]–[25:56]`.
- **Method 2 (TJR's own preferred):** box off **only the WICK of the candle — from the wick tip down to the START of the body.** Rationale `[10:38]–[11:49]`: a big box "looks bad," he can visualize it anyway, and — the key market observation — price **often taps just the wick area, OR taps just the BASE OF THE BODY (where the body starts) as the reaction point.** "Touch the base of the body… that's usually the reaction point for this." He labels wick-tip → body-start.
- **Best when paired with a liquidity sweep** `[09:52]`: "it's almost always best when we see a liquidity sweep as well." A liquidity sweep + leg + BOS is the highest-quality OB.

**Entry & targets** `[12:54]–[13:45]`, `[16:44]–[18:11]`:
- Wait for price to draw back (retrace) into the OB, wait for **confirmation = a break of structure / MSS in the trade direction** (he shows a **15-minute BOS** as confirmation to enter), then enter. Optionally enter on a lower-timeframe OB or FVG *inside* the HTF OB for a tighter stop / "crazy RR."
- **Retracement entry tools** (what you wait for price to fill into) `[16:47]–[16:59]`: **fair value gap (imbalance)** and **order block** — "and order block off the first retracement in equilibrium, which we haven't gotten yet" (forward reference — equilibrium is the next lesson). Right now "we're limited to FVG and order block."
- **Targets:** previous areas of liquidity on higher timeframes. **Order blocks can also be used AS take-profit targets** `[13:39]–[13:45]`: "I sometimes use order blocks as take profit."
- **Stops:** "wherever you want" `[17:59]` — placement tied to the timeframe you're playing (consistent with Day 22's timeframe-coherence rule).

**Multi-timeframe / bias alignment** `[15:57]–[21:20]`:
- Scale down through timeframes: e.g. daily/4h BOS sets bullish bias → on the hourly you wait for **any bullish confirmation** (a BOS) → enter off the OB/FVG. "Especially if it's in line with our daily and our weekly bias, that only means price is going to go higher." A **daily bias shift** happens when structure breaks with a big move. He shows daily OB, 4h BOS, hourly OB, 15m entry all nested.
- **Heuristic** `[23:48]`: "If you see a liquidity sweep and then a leg higher, you should ASSUME there's going to be an order block there."

Walks multiple live examples (Gold, GBP pairs/GBPJPY, others) reinforcing: liquidity sweep → leg → BOS → retrace into OB/FVG → confirmation BOS → enter → target prior liquidity.

Closes: next lesson is **Equilibrium** `[27:04]`, and a later **"putting everything together"** series (~3 videos) will assemble the full strategy `[13:46]`.

## Codex interpretation (labeled inference toward machine rules)

- **OB detection primitive:** OB = the contiguous displacement leg immediately preceding a BOS/MSS. Bullish OB = last down-leg before an up-BOS; bearish OB = last up-leg before a down-BOS. Quality gate: prefer OBs where the leg also **swept liquidity** (took out a prior high/low) before the BOS.
- **Two boxing conventions to store per OB:** (a) **full-leg zone** [leg extreme, leg origin] and (b) **wick zone** [wick tip, body start]. TJR uses (b) as the *reaction/entry* zone and notes price commonly reacts at the **body-open (base of body)** level — store the body-open price as a discrete reaction level. Recommend beginners/first implementation use the full-leg zone (larger, more forgiving).
- **Entry trigger:** price retraces into the OB zone → wait for a confirming LTF BOS/MSS (he demonstrates 15m) in the HTF-bias direction → enter. This is a concrete testable rule: "enter on a 15m BOS confirming HTF bias after price fills the OB (or an FVG inside it)."
- **Nested-TF stack:** HTF (daily/4h) OB + BOS defines bias → intermediate (1h) OB/BOS → LTF (15m/lower) entry OB/FVG for tight stop. Only take LTF entries aligned with HTF+weekly bias.
- **Targets:** previous liquidity pools on higher TFs; OBs and FVGs also serve as TP levels.
- **FORWARD DEPENDENCY:** "order block off the first retracement in equilibrium" is explicitly deferred to the equilibrium lesson (Day 26/28). Do NOT finalize the retracement-entry rule until equilibrium (premium/discount, 50%) is ingested — it refines *which* retracement/OB to trust. Flagged in ambiguities.
