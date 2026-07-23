# Verification Questions — Lesson 52 (owner: Jiv)

1. Operationalize the post-loss stop (r01): does the engine stop after ONE loss, or after N losses, and is the boundary the trading session or the full day?
2. Set the daily-loss dollar/percent cap (if any) that should also trigger the stop, or confirm the trigger is purely "a losing trade closed."
3. Confirm the max-trades-per-session cadence to enforce the "don't over-trade after a win" guardrail (align with lesson 17's ~1 trade/day).
4. Define the rolling evaluation windows (e.g. weekly, monthly, yearly) and the minimum sample size before the engine adjusts confidence/sizing (r04).
5. Confirm the journaling schema for the mandatory post-loss recap (r03) and that it should share the loss-taxonomy field from lesson 50.
