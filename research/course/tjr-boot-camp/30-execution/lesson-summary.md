# Boot Camp Day 30: Execution — Lesson Summary

Also titled by TJR "Putting the Pieces Together part one" [00:34]. No charts in this lesson [00:26]; it is a conceptual/notes lesson defining the building blocks and then stacking them into four ranked entry models. TJR repeatedly stresses this is the execution portion of the trading plan discussed "yesterday" (Day 29) and must be written down as homework [00:57], [07:01], [07:08].

---

## What TJR teaches

### The five building blocks [01:07]
TJR lists the five tools/building blocks of the strategy:
1. Liquidity sweep
2. Break of structure (BOS)
3. Order block (OB)
4. Fair value gap (FVG)
5. Equilibrium

### What each building block tells us about the market
- **Liquidity sweep** [01:26]: shows the *potential* for orders to get filled — it just means a high or a low getting taken out. TJR is explicit: at this stage "we don't know whether it's confirmed yet" [01:36].
- **Break of structure** [01:41]: gives *confirmation* that orders were filled; we see a market structure shift. Example [01:48]: if we're in an uptrend and we see a liquidity sweep and then a break of structure to the downside, "it's pretty safe to say the smart money orders got filled and we're going to go in the opposite direction."
- **Order block** [02:03]: the price range where orders were filled — "that boom, that move up that caused the liquidity sweep where orders were able to get filled within that price range," and then price drops because of it.
- **Fair value gap** [02:18]: the price range with a *lack of liquidity* — nobody going in the opposite direction of the market. Usually the big imbalance candle (big candle up or down) with no counteracting orders inside it [02:30].
- **Equilibrium** [02:42]: "finding that discounted price between highs and lows."

### The four entry models (ranked by risk) [03:03]
TJR presents four ways to enter, stated in order, and later ranks them: model 1 is the safest, models 2 and 3 are "kind of equal," and model 4 (the full stack) is described as most safe / foolproof for beginners. NOTE: TJR's risk labeling is internally contradictory in the transcript (see ambiguities.md).

**Model 1 — Liquidity sweep + Break of structure (entry on the BOS)** [03:15]
- Logic: orders had the potential to fill off a high or low (sweep), then were confirmed filled by the break of structure (we can literally see market structure shifting) → enter [03:20].
- TJR notes this entry is "going to be the top of the move" [03:53] — i.e. entering right at the extreme.

**Model 2 — Liquidity sweep + BOS + Order block (entry at the OB)** [03:54]
- Used when "we don't like the risk to reward" that the BOS entry gives us [04:01].
- The order block is described as "our first retracement tool that we always look for" [04:05].
- Sequence: sweep → BOS confirms orders filled → wait/be patient → price retraces into the previous order block (the price range where orders were filled in that move up) → enter at the order block for an optimal entry [04:14]–[04:37].
- **Stop loss placement: "stops above the highs."** [04:39]

**Model 3 — Liquidity sweep + BOS + Fair value gap (entry at the FVG)** [04:42]
- These do not have to be simultaneous: you can see a sweep, a BOS, miss the order block entry, price trends lower, then see a fair value gap that you enter off of [04:49]–[04:58].
- Logic: sweep = potential fill, BOS = confirmed fill, then wait for the price range where there was a lack of liquidity *in the opposite direction of our bias* [05:03]–[05:12].
- Bullish worked example [05:15]: if bullish and we see a bullish fair value gap get filled, that means there is a lack of liquidity to the downside within that price range (against our bias); we wait for that price range to get hit and either react off it or just get hit for us to enter [05:27]–[05:31].

**Model 4 — Liquidity sweep + BOS + (FVG or OB) + Equilibrium/discount (ultimate Confluence)** [05:34]
- Adds equilibrium on top: enter only when the OB/FVG level is also within a *discount* [05:40]–[05:45].
- TJR calls it "ultimate Confluence… a foolproof plan to enter if you are a beginner" [05:48].
- Full sequence [06:23]: orders had potential to fill (sweep) → confirmed filled (BOS) → wait for the price range with either an order block or a fair value gap (where price filled orders previously OR where there was a lack of liquidity) → confirm that level is within a discount → enter [06:23]–[06:47].

### Homework / process instructions
- Write everything down; this is the execution part of your trading plan [00:57], [07:01], [07:08].
- In your execution plan you must *choose which one* of these models you want to use [07:12].
- Understand *why* the market is moving and why you take trades off these levels — not "it's bouncing off the floor" or "bouncing off the EMAs that cross" [07:17]–[07:28].
- If you don't understand the building blocks, re-watch the boot camp videos and TJR's older solo YouTube videos on each building block [07:37]–[07:57].
- Teaser: "Putting the Pieces Together part two" (chart examples of each model) comes after tomorrow [07:37]–[08:07].
- Closing philosophy: strategy "isn't the biggest part of trading… but if you don't know how to execute that's a big issue," and the bigger issue is executing without emotional control / being robotic [08:14]–[08:32].

---

## Codex interpretation

The lesson defines a single directional entry sequence (illustrated bearish, i.e. after a bullish sweep of a high → bearish reversal; the bullish mirror is stated for the FVG case). The machine-readable core is a 4-tier confluence ladder over the same primitives:

1. Detect **liquidity sweep** (prior swing high/low taken out) — *setup trigger, unconfirmed*.
2. Detect **break of structure** in the opposite direction — *confirmation trigger*. Model 1 enters here (at the extreme / top of move; worst R:R but earliest).
3. Optionally require a **retracement into an OB** (Model 2, SL above the swing high for a short / below the swing low for a long) or **into an FVG** (Model 3, the counter-bias imbalance).
4. Optionally add an **equilibrium/discount filter** (price below 50% of the leg for longs / above 50% for shorts) → Model 4 "ultimate Confluence."

Only ONE hard numeric parameter is stated: **SL "above the highs"** for the order-block entry [04:39] (interpreted: for a short entry, SL just above the swept swing high; the long mirror would be SL below the swept swing low — TJR only states the short/above case). NO risk %, R:R target, session/kill-zone time, timeframe, or max-trades number is given in this lesson. TP is never specified. The equilibrium/discount reference (50%) comes from prior lessons, not restated numerically here — treat as codex_interpretation, requires confirmation.

The risk ordering TJR states is ambiguous/contradictory (he calls Model 1 "most risky" via "the higher up you get on this list the more risky," yet also calls Model 4 "most safe / foolproof"). See ambiguities.md. Do not hard-code a risk ranking from this lesson.
