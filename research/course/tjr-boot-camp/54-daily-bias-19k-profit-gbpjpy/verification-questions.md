# Verification Questions — Lesson 54 (owner: Jiv)

1. Confirm the canonical "TJR 4X strat" stack (r01): daily bias -> daily BOS + order-block mitigation -> London-highs sweep -> Asian-highs sweep -> 5m BOS -> entry. Is this the exact template to score against?
2. Does the strat require sweeping BOTH London and Asian session liquidity in sequence, or does either sweep qualify?
3. Provide the session clock times (and timezone) for London / New York / Asian / pre-market that define the liquidity levels used here.
4. Fix the machine entry timeframe: 5m per the strat, with the 1m entry treated as human discretion? Or allow a defined LTF-refinement step?
5. Confirm the management rule (r03): TP1 at the next opposing order block, close 50% at TP1, move SL to break-even on the runner. What is the runner's final TP rule?
6. Define the 15m swing-high detection (fractal size) for the SPX bias-flip rule (r04).
7. This trade lacks stated lot size / risk %, so no R-multiple is derivable — should such recaps still be included in the dataset as directional-pattern examples only?
