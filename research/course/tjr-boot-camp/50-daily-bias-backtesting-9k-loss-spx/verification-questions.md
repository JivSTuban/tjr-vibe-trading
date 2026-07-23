# Verification Questions — Lesson 50 (owner: Jiv)

1. For the "HTF liquidity sweep" requirement (r03), which exact timeframes count as HTF for the swept liquidity on (a) indices like SPX and (b) Forex pairs?
2. Quantify "strong rejection closing strong" (r04): minimum body %, close within top/bottom X% of range, and on which timeframe is the rejection candle read?
3. Confirm the retrace target for r04 is the 50% equilibrium of the impulse leg (not restated in this lesson).
4. Should the "1H BOS precedes 4H BOS" nesting rule (r02) generalize to all timeframe pairs (e.g. 5m precedes 15m)? What lookback window bounds "already broke"?
5. Set the numeric daily-loss stop and/or max-trades-per-day that operationalizes "no second trade after the loss" (r06). Is the scope the session or the whole calendar day?
6. Is the "1H building blocks > 15m on SPX" preference (concept) instrument-specific, or should the scorer apply an instrument-tunable building-block timeframe weight?
7. Confirm the loss taxonomy (bias-invalidation vs execution-error) should be a tracked journaling field feeding a confidence/de-risk mechanism.
8. This day's SPX trade was a LOSS but the bias was correct — for the training dataset, should it be labeled a "correct bias / bad execution" negative example (useful) or excluded?
