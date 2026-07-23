# Verification Questions — Lesson 18 (FVG Part 3)

Owner: Jiv. Resolve before encoding the entry model.

1. **Entry level:** Is the entry ALWAYS the lower-timeframe BOS candle close after the FVG fill, or can it be a limit at the FVG edge/50%? (TJR only demonstrates the BOS-close entry; [4:27].)

2. **Minimum FVG penetration:** How far into the FVG must price trade before a valid LTF BOS counts as the trigger? (Undefined in lesson.)

3. **R:R filter:** What is the minimum risk-to-reward that makes a setup "good enough" to take? He rejects raw-tap entries for "not a good risk reward" [5:30] but gives no number. Is there a hard floor (e.g. 1:2, 1:3)?

4. **Timeframe mapping:** Should the bias-TF / structure-TF / entry-TF be fixed per instrument, or a relative "scale down 1–2 steps" rule? (SP500 used 15m→5m→1m; gold used 4h→15m.)

5. **Authoritative bias TF:** Which timeframe defines directional bias — daily, 4h, or 1h — and does it change by instrument/asset class?

6. **Market open session:** For each traded instrument (SP500 index, GBPJPY, GBPUSD, gold), what is the exact "market open" time + timezone that gates entries? [3:15]

7. **Confirmation count:** Is HTF-BOS + LTF-BOS the minimum, or is a liquidity sweep strictly mandatory too? Are order block / sweep-within-imbalance interchangeable OR additive confirmations? [16:03]

8. **Stop buffer:** How much beyond the swept wick should the SL sit (ticks/pips/ATR)? [7:14]

9. **TP selection:** When multiple liquidity pools exist, which is TP1 vs the runner, and what fraction is scaled at each? Confirm remainder→break-even after TP1 [4:43].

10. **FVG dual role:** Confirm the code should treat FVG as (a) a draw-on-liquidity/retracement magnet AND (b) a confirmation zone — and NEVER as a standalone entry signal [15:56]. Any exception?
