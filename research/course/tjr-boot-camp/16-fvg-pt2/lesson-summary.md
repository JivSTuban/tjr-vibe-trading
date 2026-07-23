# Lesson 16 — Fair Value Gaps Part 2 (Identifying FVGs)

Source: https://youtu.be/S1kY3Fw6JUQ | duration 760s | transcript: en-orig-asr

TJR frames this as the middle of a 3-part FVG thread: Part 1 (prior) introduced the concept, this Part 2 covers **identifying** FVGs and previews trade usage, and "day three" (lesson 18) covers **taking trades** by combining FVGs with liquidity sweeps / breaker structure. [01:14]

---

## What TJR teaches

### Definition / recap [01:57]–[03:10]
- Fair value gap (FVG) = **liquidity void** = **imbalance**. All three terms are used interchangeably. [01:59]
- It is "literally where there is a **lack of liquidity**, meaning there are **no resting orders in the opposite direction** of wherever price wants to go." [02:03]
- Mechanism: price draws back down into that liquidity void / imbalance where there are no resting orders; then "we can place more orders" and the market **reacts / moves** because there was a lack of liquidity in that area. [02:11]–[02:26]
- Restated: "no resting sell orders / no resting buy orders in the opposite direction of wherever the price is trending." [02:56]
- This makes FVGs a **retracement tool** — it helps you find trades off retracements. [03:03]–[03:10]

### FVGs are NOT reversals [03:22]
- "Fair value gaps are **not** reversals ... not used for reversals." [03:22]
- In an uptrend (higher highs / higher lows) you look for **bullish FVGs** for **retracement + continuation**, not bearish FVGs to turn price around. [03:30]–[03:56]
- "Fair value gaps and equilibrium are used for **continuations and retracements**." [04:05]

### Identification — three-candle pattern [04:12]–[04:34]
- FVG / imbalance = a **three-candle pattern**.
  - Candle 1: has a wick ("shrink"). [04:19]
  - Candle 2: the candle that **creates the imbalance** — "super full" (large body, displacement). [04:22]
  - Candle 3: has a wick. [04:30]
- How you know there's no resistance in the gap: **through the wicks** — the middle (candle 2 body) is not covered by candle 1 and candle 3 wicks. [05:07]–[05:10]

### Measuring the box [05:19]–[05:42]
- **Bullish FVG**: measured from the **top of the first candle's wick** to the **bottom of the third candle's wick**. [05:23]–[05:33]
- **Bearish FVG**: measured from the **bottom of the first candle's wick** to the **top of the third candle's wick**. [06:45]–[06:59]
- Draw a rectangle / box over that range, then **wait for price to fill** and **wait for price to react**. [05:36]–[05:47]

### Worked chart references (instrument/timeframe unnamed)
- Bullish example [05:56]–[06:28]: breaker structure confirms bullish → massive up candle with no wicks filling the gap → price draws into it, "chop chop chop," break structure, rally.
- Bearish example [06:41]–[07:15]: break of structure confirms bearish bias → looking for retracements → price retraces into the bearish FVG, "chop chop chop fill drop," continues lower.

### CRITICAL rule — do not execute purely off the FVG being hit [07:57]–[08:41]
- "The issue I have ... is when people execute purely off of just the fair value gap **getting hit** and **without a reaction**." [07:57]–[08:02]
- Instead: **wait for a reaction**, OR **scale down to a lower timeframe** and look for a **breaker structure / change in market structure shift (MSS) / break of structure (BOS)**, OR a simple reaction candle (bullish/bearish in your intended direction). Let that be your **confirmation to enter**. [08:04]–[08:20]
- FVGs are **everywhere on the chart** — be **patient**; "not all of them are going to work." Wait for confirmation / a smaller-timeframe break of structure. [08:22]–[08:41]

### Invalid FVG (already filled) [09:44]–[10:44]
- If candle 1's and candle 3's **wicks already overlap / fill** candle 2's body → **NOT a valid FVG**, because price already came within that area and **filled the liquidity void**. [09:44]–[10:24]
- "These wicks show resting orders" — proving there is no lack of liquidity there; it's been filled. [10:28]–[10:40]

### Execution preview [11:38]–[12:09]
- Identify the FVG, see price rally/draw into it, **scale down to the lower timeframe**, see a break of structure → "that's how we can execute." (Full execution is deferred to the next lesson.) [11:55]–[12:09]

### Homework [08:49]–[10:44], [12:11]–[12:24]
1. On your chosen (one) trading pair, **identify 10 fair value gaps** and write a **hypothetical trade plan** for each (e.g. "stop above previous high, target previous lows"). [08:49]–[09:31]
2. Also **identify non-valid FVGs** (ones where the void is already filled) so you can distinguish real vs. fake. [10:41]–[12:24]

---

## Codex interpretation (inference toward machine rules — NOT TJR's words)

- **Valid bullish FVG (3-candle):** `candle1.high < candle3.low` → gap box = [candle1.high, candle3.low]. If `candle1.high >= candle3.low` the gap is filled → invalid. (TJR describes this as "wicks do not fill the second candle's body"; the standard SMC formalization uses candle-1 high vs candle-3 low. Flagged in ambiguities — TJR says "top of first wick to bottom of third wick," which matches candle1.high→candle3.low.)
- **Valid bearish FVG (3-candle):** `candle1.low > candle3.high` → gap box = [candle3.high, candle1.low].
- **Displacement gate (candle 2):** TJR calls candle 2 "super full" / "massive." No numeric threshold given (body size, ATR multiple) → ambiguity.
- **Entry gate:** treat FVG fill as a *trigger*, not an *entry*. Require a lower-timeframe BOS/MSS or reaction candle inside/after the fill before entering. Neither the confirmation timeframe nor what magnitude of "reaction" qualifies is specified → ambiguity.
- **Bias filter:** only take FVGs aligned with HTF trend (bullish FVGs in uptrend, bearish in downtrend). FVGs are continuation/retracement only, never counter-trend reversal.
