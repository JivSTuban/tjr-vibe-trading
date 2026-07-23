# Verification Questions — Lesson 20 (Order Blocks) — owner: Jiv

1. **OB unit:** Should the OB be marked as a SINGLE candle (last opposing candle
   before displacement, per standard SMC) or as the WHOLE initiating leg that
   TJR describes ("that move up that causes the liquidity sweep")? — Confirm
   against Day 2 (how-to-spot) lesson before coding detection.

2. **Zone boundaries:** For the OB rectangle, use body (open→close), full candle
   (high→low incl. wick), or the full leg's high→low? TJR never says. Which does
   Day 2 use?

3. **Mitigation:** Define "used up." Is an OB invalidated after one touch/entry,
   after price fully trades through it, or does it persist until the next trend
   shift? Not defined in Day 1.

4. **Entry confirmation:** Does entering off an OB require LTF confirmation
   (e.g., CHoCH/MSS on lower TF, candle close inside), or is a limit at the OB
   edge acceptable? Not specified here.

5. **Stop / target:** Confirm SL placement (beyond OB high/low? beyond wick?)
   and TP/RR — none stated in this lesson. Which later lesson supplies these?

6. **One-OB-per-trend:** Confirm the machine definition of "trend" and "trend
   shift" this rule relies on (from the liquidity-sweep / BOS lessons).

7. **Timeframe:** For live trading, which timeframe's OB do we take as the entry
   POI, and how does it interact with HTF bias? (Deferred to Day 3.)

8. **Priority ranking:** Confirm the retracement POI priority OB > FVG >
   equilibrium is applied literally in the engine as a tie-breaker/selection
   order.

9. **News guardrail:** What concrete no-trade window (minutes before/after PPI,
   FOMC, CPI, NFP) should the risk engine enforce, given TJR only illustrates it?
