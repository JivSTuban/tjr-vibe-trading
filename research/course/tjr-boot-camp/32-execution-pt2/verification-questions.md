# Lesson 32 (Execution pt.2) — Verification Questions

**Owner: Jiv**

1. **Sweep definition:** Which lesson authoritatively defines a "liquidity sweep" (equal highs/lows vs single swing; wick-through vs close-through)? Model A/B r01/r02 depend on it.

2. **BOS confirmation:** Does break of structure require a candle CLOSE beyond the level, or is a wick-through sufficient? (Same open question flagged in Lesson 33.) Needed to code r01.

3. **Order-block boundary (r02):** Confirm the exact OB zone definition — body-only vs full candle range (incl. wick), and which candle when the displacement leg is multi-candle. Source lesson?

4. **OB entry tolerance (r04):** "Doesn't matter if it's exact — execute on the wick." What tolerance do we implement — any touch of the OB edge, a % penetration, or fill at OB 50%? TJR gives no number.

5. **Timeframe pairing:** Is there a mandated HTF-context / LTF-entry combination (e.g., 15m sweep→5m entry), or is the model applied on a single timeframe? Lesson 35 mentions 15m/1h/4h/D/W — reconcile.

6. **Model A risk:** TJR calls bare sweep+BOS the "riskiest / lowest confluence" entry [05:37]. Confirm we will NOT enable Model A standalone and will always require OB/FVG/equilibrium + daily-bias confluence (Days 33–35).

7. **Validation sample (r05):** "10 examples" is a learning drill. What is our actual minimum backtest sample per model before enabling live? (10 is almost certainly too small.)

8. **Scope confirmation (r06):** Agree this lesson gives entry triggers ONLY — SL, TP, R:R, risk %, session, and daily bias must be attached from other lessons before any backtest/live run.

9. **ASR confirmation:** Confirm "breaker structure" throughout = break of structure (BOS), not breaker block; and "molested/water block" = order block.
