# Verification Questions — Lesson 22 (Order Blocks pt.2)
Owner: Jiv

## OB definition
1. Is the OB zone the **full leg** (leg high→low) preceding the BOS, or just the **last opposing candle** before displacement? TJR says both. Which do we codify?
2. Where does the OB **leg start** — from the prior swing point, from the first displacement candle, or from the sweep candle?
3. Are **MSS** and **BOS** the same trigger in TJR's system, or distinct? (He says "break of structure / market structure shift" interchangeably at [22:27].)

## Timeframe-coherence rule (safety-critical)
4. Confirm the invariant: **SL reference TF must equal the OB/BOS detection TF** (SL_reference_TF == OB_detection_TF). Is this an absolute hard gate or a soft warning?
5. For a HTF OB, is the safe SL always **beyond the HTF OB boundary**, or can it sit at the LTF entry-structure once price is inside the OB? (TJR shows both.)
6. What HTF→entry-TF mappings are permitted? (Daily OB entered on 15m AND 1h were both shown.) Do we allow any lower TF, or fix a ladder (e.g. Daily→4h→1h→15m)?

## Sessions
7. NY open "9:30" — confirm **timezone = America/New_York**. Is pre-market entry always blocked?
8. What is the **London open time** (not stated)? Is the session gate global or per-instrument/per-pair?

## Entry / targets
9. Entry = **confirming LTF BOS in the HTF direction after price taps the OB** — confirm this exact sequence and that it's a candle-**close** break (not wick).
10. TP2 = **50% of the imbalance/FVG** — confirm equilibrium-of-gap rule. What are the TP1 and TP3 rules precisely (nearest liquidity vs specific swing)?
11. What **position-size split** across TP1/TP2/TP3?
12. Which **liquidity pools** qualify as targets — all prior swing highs/lows, or only unmitigated ones?

## Risk / patience
13. Is there a **minimum R:R threshold** below which we skip the immediate sweep+BOS and wait for the OB retrace? (1:12 cited as a good example, not a floor.)
14. Does the "be patient" guardrail imply a **one-setup rule** or a max-trades cap? (Not stated this lesson.)

## Cross-lesson
15. This is **part 2 of 3**. Part 1 (~Day 20/21) gave the verbal OB description; Part 3 = **Day 24** ("order blocks day three in two days"). Ensure the OB definition, sweep definition, and "regular structure" are reconciled across all three parts before coding.
