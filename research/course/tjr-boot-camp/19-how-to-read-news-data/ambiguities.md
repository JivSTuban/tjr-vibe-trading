# Ambiguities — Lesson 19 (How to Read News Data)

## Undefined thresholds / missing numbers

### 1. T_before (minutes BEFORE a release to stop opening trades) — CONFIDENCE LOW
TJR never states an explicit "don't open a trade within N minutes before high-impact news." His only related remark is a warning at [24:17]: "you don't want to get caught taking a trade and the next thing you know news comes out five minutes later it stops you out." That implies avoiding new entries in the minutes leading into a release, but no fixed buffer is given. **Human must set T_before (e.g. 5, 10, or 15 min) — this is a gap, confidence low.**

### 2. T_after (post-release wait) — CONFIDENCE MEDIUM
He gives a RANGE, not a single number: "15 or 20 minutes" [05:46], "15, 20, 30 minutes" [10:17], and a Friday example where he waits from 10:00 release to ~10:30 (30 min) [08:47]. Proposed rules use 30 min as a conservative default. Confirm the intended default.

### 3. "Drastically affected" / "large wicks" — UNQUANTIFIED
[06:20] The trigger to abort ("if it makes a big move / large wicks, don't trade") has no numeric definition — no ATR multiple, pip count, or range percentile. A displacement threshold must be defined to make r04 testable.

### 4. "De-risk" / "risk less" amount — UNQUANTIFIED
[06:43] and [08:36] he says reduce risk / de-risk on heavy-news days but gives no percentage. r05 assumes "halve default" as a placeholder — confirm.

### 5. Number of red folders that flags a "low probability day"
[08:36] "three red folders = terrible probability day"; the exact count that should trigger session-level de-risk is inferred (r05 uses >=2). Confirm the threshold.

### 6. Session vs full-day scope of the hard block
[07:29] "those four I do not trade whatsoever" and [23:02] "sleep in, live to trade another day" imply the whole trading day is skipped when CPI/PPI/FOMC/NFP is present. Confirm the block covers the full RTH session and not just the release window.

## Timezone
Forex Factory auto-localizes to the user's timezone [04:11]. TJR's example times (8:30 / 8:45 / 8:50 release; 9:30 market open, 10:00 news) are consistent with **US Eastern Time** (US CPI/PPI release at 8:30 ET; NYSE open 9:30 ET) but he never explicitly names the timezone. **Assume US Eastern for his examples; the engine should treat calendar times in the account/data timezone. Confirm.**

## ASR corrections (garble -> canonical)
The ASR was clean on the key acronyms — all four release names came through correctly:
- "CPI" -> CPI (correct in ASR)
- "PPI" -> PPI (correct)
- "fomc" -> FOMC (lowercased by ASR; canonical FOMC) [07:06], [07:20], [08:31], [23:02]
- "NFP / non-farm payroll / non-farm employment" -> NFP / Non-Farm Payroll (correct) [07:22]
- "dxy" -> DXY (US Dollar Index) [13:04]
- "GJ" / "GU" / "EU" -> GBP/JPY, GBP/USD, EUR/USD (his shorthand) [08:06], [13:23]
- "SPX / S P 500" -> S&P 500 / SPX (correct)
- "USC" -> USD (ASR mis-hears "USD" as "USC" repeatedly, e.g. [12:24], [22:26]) — canonical USD
- "NCD" -> NZD (New Zealand dollar) at [03:20] — ASR garble, context "do I trade NZD? no"
- "Chinese yen" -> Chinese yuan/CNY at [03:00] — TJR said "yen" but meant the Chinese currency (CNY); minor speaker slip, non-blocking
- "unprobable / unprobleable" -> improbable / low-probability (TJR's own coinage, repeated)
- "buys" (at [11:41] "should be your buys for the day") -> bias — ASR homophone; he means news BIAS not buys

## Releases he did NOT explicitly name (do not assume)
He named ONLY the four: CPI, PPI, FOMC, NFP. He referenced "consumer sentiment" [09:16] and "Bureau of Labor Statistics" [11:14] in passing but did NOT list retail sales, jobless claims, GDP, PMI, or the unemployment rate as avoid-events. Do not add them to the hard-block set from this lesson — capture only if a later lesson names them.
