# Verification Questions — Lesson 33 (Execution pt.3)

owner: Jiv

These must be answered before any rule here is promoted from `proposed` to active in the
automated system. Each maps to an ambiguity.

1. **FVG fill depth:** For entry, does price need to fully fill the FVG, reach its 50%, or
   just tap the near edge? (ref [07:04], [10:46])

2. **Equilibrium/FVG "match" tolerance:** What price-band overlap counts as equilibrium
   "matching perfectly" with the FVG? Define a numeric tolerance. (ref [15:00])

3. **Measurement direction:** Confirm equilibrium is drawn across the impulse leg (swing
   high to swing low for a down leg / low to high for an up leg) — which end is anchor 0%?
   (ref [19:54]/[20:13])

4. **Confirmation gate:** Is a lower-timeframe BOS confirmation mandatory, or optional when
   confluence is already high? (ref [07:26], [09:44])

5. **Timeframe pairing:** What is the intended setup-TF -> confirmation-TF mapping (fixed
   ratio, or discretionary)? Which TF defines "structure" for BOS? (ref [06:55], [22:45])

6. **Confluence minimum:** Is there a minimum confluence count required to take a trade, or
   is it purely a confidence weight? (ref [22:56])

7. **Stop loss:** Deferred here — confirm SL rules come from lesson 30/32 or a later lesson,
   and do NOT encode SL from lesson 33. (ref [07:35])

8. **Take-profit:** Which liquidity pool is TP1 when multiple exist? Runner logic? (deferred
   — confirm source lesson) (ref [10:02], [18:02])

9. **Daily-bias filter:** Hard-reject counter-bias setups, or downweight them? How is daily
   bias computed (next lesson)? (ref [23:36])

10. **News avoidance:** Define the event list (Powell/FOMC, CPI, PPI, NFP?) and the
    suppression window around each. (ref [06:48])

11. **Short-side symmetry:** Confirm the model inverts 1:1 for shorts (sweep highs -> BOS
    down -> bearish FVG/OB -> target lows). (ref [09:13])
