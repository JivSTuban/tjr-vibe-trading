# Boot Camp Day 22: Order Blocks pt.2 — Lesson Summary

**Video:** https://youtu.be/RQSVIKddFHI · **Duration:** ~26:00 (manifest duration_s=1559 ≈ 26 min) · **Primary topic:** concept (core technical)

This lesson is **part 2 of a multi-part Order Blocks thread**. Part 1 (~Day 20/21) "pretty much just described" the concept verbally (no charts). This lesson applies the OB definition to live charts across multiple timeframes. Part 3 ("Order Blocks day three") is promised **"in two days"** (Day 24) [25:45].

---

## What TJR teaches

### 1. Recap — definition of an Order Block [00:33–03:07]
An **order block (OB)** is *"the move prior to the liquidity sweep, or the move that causes the liquidity sweep... and then prior to the break of structure"* [01:33]. It is **the whole move/leg** (not a single candle) that occurs **before** the break of structure (BOS) that flips direction.

- **Why it matters:** The OB is *"where orders were able to get filled"* — where price filled orders in order to make the break of structure [02:03–02:17].
- **Bearish OB (sell-side setup):** In an **uptrend**, price rallies up, sweeps liquidity, then breaks structure to the downside. The **up move** (leg) prior to the BOS-down is the order block [01:52–02:32]. When price retraces back up into that price range on bullish momentum, "they" fill more orders there (because orders were filled there previously) and push price lower [02:19–02:34].
- **Bullish OB (buy-side setup):** In a **downtrend**, the **down move** (leg) that swept liquidity prior to the BOS-up is the order block [02:36–03:04]. When bearish momentum comes back down into that price range, orders get filled again and price is pushed back up in the intended direction.
- Restated at close [22:23]: the OB is "the move down or the move up prior to the break of structure / prior to the **market structure shift** that changes the direction, because that move is where the orders are getting filled."

**ASR/jargon note:** TJR says "rally" loosely for both up- and down-legs (e.g. "big rally down" [08:56]) — normalize to "leg/move." "Braking/breaker structure" = break of structure (BOS). "MSS/market structure shift" is used interchangeably with BOS here [22:27].

### 2. OBs manifest on MULTIPLE timeframes [07:03–08:12]
*"Order blocks can be represented on several timeframes, but you have to understand it's the whole move."* [07:03] Worked example: on the 4h a single candle can be "relatively precise" as the OB [07:53], but the **entire move** may be larger. A big HTF order block "gives you a big price range to deal with" [08:07].

### 3. The CRITICAL rule — match your timeframe [08:12–10:42]
*"That's why we can scale down... it depends what timeframe you're playing off of."* [08:12]

- **Stop-loss placement must match the timeframe of the BOS/OB you are playing.** If the move was a **4-hour break of structure**, the whole OB spans "several hourly candles" [09:26]. If you then see only an **hourly BOS** off that HTF OB and keep your **stop loss super tight** to the hourly, *"you're gonna get stopped out."* [09:42]
- *"Understand what timeframe you're playing off of."* [09:47] A 4h move requires the stop "all the way up here" (wide, above the HTF OB) [09:56].
- Trade-off: wide stop, but you can then **target previous areas of liquidity on higher timeframes** [09:57–10:05], yielding large R:R.
- Warning: *"they can mess you up big time if you can't understand that."* [10:39]

### 4. Multi-timeframe scaling / entry logic [08:29–13:00, examples]
Top-down process TJR demonstrates repeatedly:
1. Identify the OB and BOS on a **higher timeframe** (Daily / 4h) → establishes direction & the retracement price range.
2. **Scale down** progressively (4h → 1h → 15m, even 5m/1m) to get "very very precise" [12:43] with the entry.
3. Wait for price to draw back / retrace **into the order block price range**.
4. **Entry = break of structure** in the trade direction on the lower timeframe: BOS to the downside for shorts, BOS to the upside for longs [09:08–09:15].
5. On the lower TF, monitor swing highs (for longs) or lows (for shorts): "this high nothing, this high nothing... this high something — we broke structure — entry" [13:16–13:26].
6. **Session gating:** wait for the session to open before acting. Explicit: "when is New York session open, 9:30, mark that off" [12:53–13:04]; and "this is right during London session so we're gonna wait for London session to open first" [16:20].

### 5. Targets & take-profits [13:38–14:22, 21:18]
Targets = **previous areas of liquidity** (higher-TF) and imbalances/FVGs.
- Worked GBPUSD/daily example: TP1 = nearer liquidity/high, **TP2 = within the imbalance, ~50% of it** [13:44], TP3 = higher highs (destroyed). "Confirming a daily BOS = changing directions" so it was "a daily play" [13:50].
- One example: *"pretty much a one-to-twelve risk-reward ratio"* [14:19] achievable by patiently entering off the 15m for a daily play. Alternative less-exact entry: enter off the **hourly** BOS ("that's probably better than getting as exact as the 15-minute for a daily play") [14:33–15:34].
- Stop-loss placement options given [23:23]: stop "either above here or above the order block itself if you want to play safe."

### 6. Psychology — patience [14:33, 32:00 region]
The hard part is patience: you must wait for the HTF BOS, then wait for price to return into the OB, then wait on the lower TF for the confirming BOS. *"Would you really have been patient enough to wait...?"* [15:11]. TJR reasons: if a plain liquidity-sweep + BOS entry doesn't give good R:R, wait for the OB retracement to get "a potentially way better risk-reward ratio... and make a lot more money and be patient" [25:15–25:32].

### 7. Homework [21:49, 24:00]
Find **5 examples of order blocks across 3 different timeframes** on any pairs you trade (4h/1h/15m/5m/1m — timeframe/pair doesn't matter). Goal: recognize OBs in real time without needing to draw them.

---

## Codex interpretation (inference toward machine rules — NOT TJR's words)

- **OB definition (machine):** An OB is the contiguous impulsive leg immediately preceding the BOS/MSS that flips local trend. Bullish OB = the last down-leg before an up-BOS; bearish OB = the last up-leg before a down-BOS. The OB is a **price range** (leg high→low), not one candle. Confidence high on definition; low on exact leg-boundary rule (TJR waffles between "the candle" and "the entire move").
- **Timeframe-coherence invariant (safety-critical):** SL distance must be sized to the timeframe on which the OB/BOS was identified, NOT the (smaller) entry-confirmation timeframe. Codify: `SL_reference_TF == OB_detection_TF`. Placing SL on the entry TF while trading a HTF OB is an explicit failure mode ("you're gonna get stopped out").
- **Nested-structure entry (machine):** (a) detect HTF OB + direction; (b) require price retrace INTO OB range; (c) require confirming BOS on entry TF (Ne.g. 15m) in HTF direction; (d) require session-open gate (London or NY) before entry; (e) SL beyond HTF OB / structure; (f) TP ladder at successive higher-TF liquidity pools + FVG midpoints.
- **Session gate:** NY open cited as **9:30** (ET implied; timezone NOT stated) — treat as parameter requiring confirmation. London open time not given numerically.
- **TP2 = 50% of the imbalance/FVG (equilibrium of the gap)** is a concrete, codifiable target.
- These are inferences; nearly all require human confirmation before coding.
