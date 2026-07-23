# Lesson 37 — Ambiguities

- **Near vs far edge of a building block as the TP price.** He variously says "top of this order block," "bottom of this order block," "within here," and "base of this order block." The exact price to place the TP (near edge, far edge, or midpoint of an OB/FVG) is not standardized. A human must fix the convention per building-block type and trade direction.
- **1:1 floor — hard reject or soft flag?** He calls minimum 1:1 "the goal," not an absolute rule. Unclear whether a setup below 1:1 to first target should be rejected outright or merely deprioritized.
- **R:R measurement basis.** The 1:1..1:5 range is stated for "first take profit," but with scale-out across 3-4 TPs the blended R:R differs. Need to confirm whether the risk engine scores on first-TP R:R or blended.
- **"Draw on liquidity" detection.** He points at chart features ("this high, drawing liquidity") without an algorithmic definition. Programmatic identification of a "draw on liquidity" target must be specified by a human.
- **How many TPs is canonical.** 3-4 stated as his habit but explicitly "not necessary" and user-configurable.
- **ASR notes:** "breaker structure" = break of structure (BOS); "for value gap" / "for Value Gap" = fair value gap (FVG); "four hour order [__]" (07:48) = four hour order block; "one to five on 4K trade on BDS on GDK" (06:04) is garbled ASR — appears to reference example R:R on trades but the instruments ("BDS", "GDK", "4K") are corrupted/unclear.
