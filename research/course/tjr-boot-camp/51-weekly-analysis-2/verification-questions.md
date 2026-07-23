# Verification Questions — Lesson 51 (owner: Jiv)

1. Which economic-calendar impact rating (e.g. ForexFactory red/orange/yellow) should map to TJR's "major" (blackout) vs "minor" (trade after open)?
2. Confirm the currency-avoidance rule: on a high-impact release, exclude ALL pairs containing that currency for the day. How do we treat SPX/indices relative to USD releases?
3. What blackout window (minutes before/after release) operationalizes "wait for news"? Is it per-release or a single global window?
4. Define the canonical "draw on liquidity" set for weekly targets (session highs/lows, swing highs/lows, equal highs/lows, all-time highs).
5. Set a minimum building-block overlap count/tolerance for a "high-confluence retracement zone" (r03).
6. For the weekly scale-out (concept), specify partial-close fractions at intervening liquidity vs the final HTF equilibrium target.
7. Confirm "price over fundamentals" means the engine must never let a macro signal override a structural bias.
