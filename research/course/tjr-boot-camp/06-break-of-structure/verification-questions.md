# Verification Questions — Lesson 06 (Break of Structure) — owner: Jiv

These must be resolved before implementing a BOS detector; BOS is the confirmation primitive the whole strategy rides on.

1. **Body-close gate — exact semantics.** BOS = candle CLOSE beyond the most-recent swing (never a wick). Confirm: strict inequality (close > swing_high / close < swing_low), or is touch/equal enough? Any minimum penetration distance (ticks/pips/%) or minimum body size? (TJR gives none — [07:54, 13:17].)

2. **BOS vs CHoCH/MSS naming.** TJR uses BOS = MSS = trend shift and always shows REVERSALS. Do we (a) label ALL close-through events "BOS" like him, or (b) split them into SMC-style continuation-BOS vs reversal-CHoCH internally? This drives how liquidity trades (Lesson 08: sweep -> opposite BOS -> entry) reference the event. [01:15, 11:45]

3. **Swing-point algorithm.** Do we detect swings as literal 2-candle patterns (up-then-down / down-then-up, wick-extreme) as stated [02:15], or as larger structural pivots (N-bar fractal) matching his drawn examples? These give very different swing sets and BOS counts. Which does he actually trade?

4. **Timeframe scoping.** On which timeframe(s) is a BOS evaluated for the auto-trader? Is it a fixed TF, or multi-TF? He references daily/weekly/monthly/4H/15m without fixing one [21:05, 22:41].

5. **HTF alignment — gate or weight?** Is a lower-TF BOS that opposes the higher-TF trend (a "retracement" [22:47]) forbidden as a signal, or merely down-weighted? Which TF pair defines "dominant"? (monthly > weekly > daily stated qualitatively.)

6. **Most-recent-swing bookkeeping.** How is "most recent" resolved when swings cluster? When is a forming swing 'locked' vs still able to migrate ("move the high to there" [21:19])? Need deterministic swing-confirmation logic.

7. **Sweep vs BOS boundary.** A wick beyond a swing with no close = liquidity sweep [23:58]. Is there any cap on how far a wick may exceed the swing before we reconsider? And how does the sweep-then-BOS entry sequence from Lesson 08 consume this event stream?

8. **Consolidation suppression.** How do we algorithmically detect "no trend / market has no clue" [19:43] to suppress BOS signals? Inherit trend classification from Lesson 04 — confirm the exact rule and its consolidation threshold.

9. **Doji / neutral candles.** How to assign direction to a doji when building 2-candle swings and when testing the close? Undefined by TJR.

10. **Cross-lesson consistency.** Confirm this BOS definition (body-close, most-recent swing, TF-relative) is exactly what Lessons 04 (trends) and 08+ (liquidity, entries) assume, so the confirmation primitive is shared and not redefined downstream.
