# Verification Questions — Lesson 12 (owner: Jiv)

1. Provide an operational definition of a "prominent" high/low (pivot lookback? swing that itself caused a BOS? double-top/bottom? relative to what timeframe?). This gates the entire liquidity detector.
2. Is ONE confluence (FVG OR order block) sufficient after sweep+BOS, or are multiple required?
3. TP selection: nearest untapped opposite-side prominent level, or the next MAJOR pool? How to rank when several exist?
4. Fix the HTF/LTF pairing for the two-timeframe workflow (e.g., daily/4h bias -> 5m/15m entry).
5. Confirm FVG, imbalance, and liquidity void are treated as strict synonyms in the engine.
6. Carry-over: define the sweep penetration threshold (shared with Pt 2).
