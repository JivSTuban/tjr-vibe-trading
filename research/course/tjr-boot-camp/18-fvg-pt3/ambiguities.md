# Ambiguities — Lesson 18 (FVG Part 3)

Points a human (Jiv) must resolve before coding the entry model. Confidence tags per item.

## 1. Entry precision inside the FVG — UNDEFINED (confidence: low)
TJR never states WHERE inside the FVG the entry occurs (edge / 50% equilibrium / full fill). The trigger is the **lower-timeframe break of structure AFTER price enters the FVG**, so the effective entry price is the LTF BOS candle close, not a fixed FVG level. But how deep price must penetrate the FVG before a valid BOS counts is unspecified. In the gold TP discussion he lists "start / 50 / end of the imbalance" but that is for TARGETS, not entries. → Needs a rule decision on minimum FVG penetration.

## 2. Risk-to-reward threshold — UNDEFINED (confidence: low)
He says a raw FVG-tap entry "doesn't give us a good risk reward" and that he waits for a better trade [5:30–5:36], implying a minimum R:R filter — but gives NO number. No stated min R:R, no max risk %, no lot-size math anywhere in this lesson. → Threshold must come from another lesson or human input.

## 3. Timeframe pairing — CONTEXTUAL, not fixed (confidence: medium)
Three different chains shown: 15m→5m→1m (SP500), 15m→5m (GJ, +1h reference), 4h→15m (gold), daily→1h→15m. There is no single canonical bias-TF / entry-TF ratio. Likely a ratio relationship ("scale down a couple steps") rather than fixed values. → Define allowed pairings.

## 4. Which HTF defines "bias" — CONTEXTUAL (confidence: medium)
Bias is variously taken from daily BOS, 4h BOS, 1h BOS, 15m BOS depending on the chart. Need a rule for which timeframe is authoritative for directional bias.

## 5. "Market open" session/timezone — UNSPECIFIED here (confidence: medium)
"Only trade off/after market open" [3:15] — but the specific open time, session (RTH vs futures open), and timezone are not given in this lesson. Note: he trades SP500 (index) and FX (GJ, GBPUSD, gold), which have different opens. → Resolve per-instrument session.

## 6. Number of required confirmations — VAGUE (confidence: low)
He references "two confirmations" (HTF BOS + trend shift) [3:56], and lists alternative confirmations (order block, sweep-then-BOS, break of structure) as interchangeable [16:03–16:13]. Minimum count and which combinations are mandatory vs optional is not pinned down.

## 7. Partial FVG fill handling — NOT COVERED HERE
He invalidates fully-traded-through FVGs [9:45] but partial-fill / 50%-mitigation behavior is not addressed in this lesson (likely covered in FVG Part 2 = lesson 16). Cross-check lesson 16.

## ASR corrections applied (canonical terms)
- "liquidity Suite / liquidity sleep / liquidity slee" → **liquidity sweep**
- "breaker structure / breakup structure / brake structure / Road structure" → **break of structure (BOS)**
- "for Value Gap / fair value Gap" → **fair value gap (FVG)** / imbalance
- "trench Trend shift" → **trend shift**
- "GJ" → **GBPJPY**; "GBP USD" → **GBPUSD**
- "50 of the imbalance" → **50% / equilibrium of the imbalance**
- Redacted profanity `[\h__\h]` in ASR ignored (filler).
