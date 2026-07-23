# Ambiguities — Lesson 22 (Order Blocks pt.2)

## Undefined thresholds / parameters
1. **OB leg boundary.** TJR alternates between "this candle" [00:59, 07:53] and "it's the whole move / the entire move" [03:03, 07:15]. No rule for where the OB leg starts (from the prior swing? from the displacement candle? full leg high→low?). Blocks a deterministic OB-zone definition.
2. **Stop-loss offset.** "Put your stop all the way up here" [09:56] and "stop either under here or underneath here, doesn't really matter" [23:23] — no numeric buffer (ticks/pips/ATR) beyond the OB.
3. **HTF→LTF mapping.** "It depends what timeframe you're playing off of" [08:19] — no fixed pairing of detection TF to entry TF. Daily play used 15m or 1h entries interchangeably [14:33].
4. **Min R:R threshold.** A 1:12 R:R is cited as achievable [14:19] but not as a floor; the patience/"better R:R" rule [25:15] gives no numeric minimum.
5. **TP position-size split.** TP1/TP2/TP3 levels described but no scale-out percentages given.
6. **Which liquidity qualifies as a target.** "Previous areas of liquidity" — no rule distinguishing mitigated vs unmitigated pools, or which swings count.

## Session / timezone
7. **NY open = "9:30"** [13:00] — timezone not stated (ET assumed). **London open time not given numerically** [16:20]. Whether the session gate is global or per-pair is unstated.

## ASR corruptions normalized (verify none are mis-mapped)
- "braking structure" / "breaker structure" / "rank of structure" → **break of structure (BOS)** (throughout).
- "the market Market Market structure shift" [22:27] → **market structure shift (MSS)** — TJR uses MSS and BOS interchangeably here; confirm they mean the same trigger in this system.
- "big rally down" [08:56], "rally down" → **down-move / down-leg** (TJR uses "rally" for both directions; normalize by BOS direction, not the word).
- "GJ" / "GBP JPY" [18:32] → **GBPJPY**.
- "TP 3B" [14:10] → likely **TP3 (variant B)**, an alternative TP3 at higher highs — confirm.
- "fair value Gap" / "imbalance" used interchangeably [17:03, 13:44].
- "1300" [17:47] → likely a **13:00 session time** reference (garbled); low confidence.

## Conceptual gaps to resolve before coding
8. The lesson never numerically defines what counts as a valid **liquidity sweep** vs an ordinary wick — assumed from prior lessons (part 1 / liquidity lessons).
9. "Regular structure" [08:58, 18:15] is used but not defined here (assumed continuation structure).
10. Direction confirmation: a **daily BOS = "changing directions"** [13:50] is treated as bias flip — confirm this is the bias rule vs lower-TF BOS being only entry triggers.
