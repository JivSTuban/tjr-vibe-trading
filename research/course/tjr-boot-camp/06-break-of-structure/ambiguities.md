# Ambiguities — Lesson 06 (Break of Structure)

## RESOLVED in this lesson (unusually explicit — good)
- **Body close vs wick: RESOLVED.** A BOS requires a candle BODY CLOSE beyond the swing; a wick alone is explicitly NOT a BOS. TJR states it, repeats it, and dictates "write that down" twice [07:54, 12:45, 13:17]. This is the clearest rule in the whole lesson — code it as a hard gate. (confidence: high)
- **Which swing qualifies: the MOST RECENT one.** Only the most-recent swing high (in a downtrend) or swing low (in an uptrend) is armed; older swings are discarded [09:04, 27:26, 31:29]. (confidence: high)
- **Direction to watch: RESOLVED.** Uptrend -> watch lows; downtrend -> watch highs [14:59, 15:22]. (confidence: high)

## STILL AMBIGUOUS — flag for the coder

- **BOS vs MSS/CHoCH terminology.** TJR uses "break of structure" and "market structure shift" as SYNONYMS here, and every example is a REVERSAL (uptrend->downtrend or vice-versa). Standard SMC reserves BOS for *continuation* (break in trend direction) and CHoCH/MSS for *reversal*. His "BOS to the downside from an uptrend" is functionally a CHoCH. **Do NOT assume his BOS = SMC continuation-BOS.** Confirm the intended semantics before naming detector events. (confidence: low on cross-mapping)

- **Swing-point definition: literal 2-candle vs structural.** TJR defines a high/low as a strict 2-candle pattern (up-then-down / down-then-up) with the swing price = extreme wick [02:15-04:45]. But his drawn chart examples appear to use larger eyeballed structural swings, not literal adjacent-candle pairs. A literal 2-candle detector will massively over-generate swings and fire spurious BOS. Confirm which he actually trades from. (confidence: low)

- **Timeframe of the confirming candle.** BOS is timeframe-relative; he references daily, weekly, monthly, 4H, 15m [05:43, 21:05, 22:07, 22:41]. He says "wait for the daily to close above" in one example [21:05] but never fixes a canonical BOS timeframe. The detector needs an explicit timeframe parameter. (confidence: low)

- **HTF alignment: hard gate or weight?** "Daily BOS while weekly bullish = retracement" [22:47]. Is HTF agreement a REQUIRED filter (never act on a counter-HTF BOS) or a confidence downgrade? He gives the hierarchy (monthly > weekly > daily) but no concrete gating rule. (confidence: low)

- **Penetration threshold.** Any close beyond the swing appears to count; no minimum distance (ticks/pips/%) or minimum body size is given. A close 1 tick beyond = same as a decisive close? Undefined. (confidence: low)

- **Strict-greater vs equal at the swing price.** "Above a high" / "below a low" — behavior at exact equality is unspecified. Assume strict; confirm. (confidence: low)

- **Doji / equal open-close candle direction.** The 2-candle swing definition depends on candle color (up vs down). A doji has no clear direction. Undefined. (confidence: low)

- **Swing migration timing.** "If the next candle is down we'll move the high to there" [21:19] — a forming swing can migrate until confirmed. The confirmation-of-swing condition (when is a swing 'locked') is not formalized. (confidence: low)

- **Consolidation detection.** He shows consolidation yields no BOS [19:43] but gives no algorithmic threshold for 'no trend / market has no clue'. Trend classification is inherited from Lesson 04, not restated. (confidence: low)

## JARGON / ASR notes
- "GU" = GBPUSD [22:51-22:57]. "GJ" = GBPJPY [27:41].
- "schminck" [11:50] is an ASR/filler artifact for "then" — ignore.
- "jizz"/"jits"/"jets" (TJR's greeting) does not appear notably here but is his verbal signature elsewhere.
- "MSS" (market structure shift) and "CHoCH" (change of character) are treated as the same thing as BOS in this lesson; the SMC distinction is NOT drawn — see the BOS-vs-MSS ambiguity above.
- Liquidity sweep is named but its mechanics are explicitly deferred to Lesson 08 [26:15].
