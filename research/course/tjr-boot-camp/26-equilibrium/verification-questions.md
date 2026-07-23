# Verification Questions — Day 26 (Equilibrium) — owner: Jiv

1. **CRITICAL — premium/discount mapping:** Confirm the canonical mapping (ignore TJR's [07:00] slip): **above 50% = PREMIUM = sell/short zone; below 50% = DISCOUNT = buy/long zone.** `[07:00]`, `[08:13]`, `[11:18]`
2. **Reference swing (biggest gap):** Which swing defines equilibrium — which timeframe and which leg (impulse leg that broke structure, most recent swing, or full HTF range)? `[07:53]` Not defined here; must come from Day 28. Do NOT ship an equilibrium rule until answered.
3. **Sub-levels:** Are there premium/discount depth levels beyond 50% (e.g. OTE 0.62/0.705/0.79) or is 50% the only threshold? `[06:45]` Check Day 28.
4. **Reaction definition:** What counts as a "reaction" off an FVG/OB for entry (candle close, rejection wick, engulfing)? `[09:49]`
5. **FVG-in-discount overlap:** Must the FVG be fully inside the discount zone or is partial overlap enough? `[10:03]`
6. **Directional gate strictness:** Should the system HARD-block longs in premium / shorts in discount, or only down-weight them? `[08:13]`
7. **Entry-priority reconciliation:** Confirm the tool hierarchy (sweep+BOS -> OB -> FVG -> equilibrium-confirmed) matches the deferred "OB off first retracement in equilibrium" from Order Blocks pt3 (Day 24). `[09:08]`
