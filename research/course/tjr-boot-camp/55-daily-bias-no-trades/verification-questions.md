# Verification Questions — Lesson 55 (owner: Jiv)

1. Pin the 30-minute-high-sweep precondition (r03): which 30m swing high/low must be swept (most recent, session-specific, which session), and does it apply to every 4X-strat entry?
2. Define "high-timeframe building block" for the required-tap gate (r01): 1H, 4H, or both? Which block types (order block, FVG, liquidity)?
3. Set the numeric New York session-end cutoff (and timezone) after which no new entries open (r05).
4. News correlation (r06): should the engine TRADE the correlation-derived bias, or only AVOID the affected pairs (TJR does the latter here)?
5. Confirm the 1H-confirmation gate for conflicted pairs (r02) is the same rule as lessons 50/53's timeframe-agreement requirement.
6. For the dataset: should these four labeled SKIPS be ingested as negative/no-signal examples (each tagged with the specific failed gate)?
