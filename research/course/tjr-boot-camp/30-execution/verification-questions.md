# Verification Questions — Lesson 30 (Execution)
owner: Jiv

1. **Risk ranking (blocker):** Which model is actually safest vs riskiest?
   The transcript contradicts itself ([05:50]–[06:11] vs "foolproof for beginners"
   at [05:48]). Confirm the intended order before any system uses model choice.

2. **Stop loss for longs:** TJR only says "stops above the highs" for the short
   OB entry [04:39]. Confirm the long mirror is "stops below the lows," and
   confirm SL placement for Model 1 (BOS entry) and Model 3 (FVG entry).

3. **Take profit:** No TP given anywhere. Where does TP come from — a fixed R:R,
   opposing liquidity, or a later lesson? Needed before any model is live.

4. **R:R decision threshold:** Model 2 is used "when we don't like the R:R" of
   Model 1 [04:01]. What numeric R:R triggers escalating from Model 1 → Model 2?

5. **Equilibrium range:** For Model 4's discount filter, which swing high/low
   pair defines the equilibrium/50%? (Not specified in this lesson.)

6. **Entry precision:** Within an OB or FVG, do we enter at the proximal edge,
   50%, or on close inside the zone? For Model 3, do we use "react off it" or
   "just get hit" — and how is a reaction detected programmatically?

7. **BOS definition/timeframe:** What timeframe and structure definition confirms
   the break of structure? (Referenced as prior-lesson knowledge, not restated.)

8. **Model commitment:** [07:12] says choose ONE model. For the automated system,
   should we implement a single configured model, or allow all four with
   priority (Model 4 → 3/2 → 1)?
