# Lesson 17 — Verification Questions (owner: Jiv)

1. **Max trades/day:** Should `tjr-patience-r02` be a HARD cap of 1 trade/day for the beginner profile, or a soft/configurable default? TJR says "I take one trade a day and I call it good" [10:04] as personal cadence, not an explicit mandate.

2. **Checklist gate ownership:** The sequence liquidity sweep → BOS → FVG fill → reaction → entry [03:36] appears here without timeframes. Which technical lesson defines the canonical timeframes for each step so `tjr-patience-r01` can be fully specified? (Likely an execution/entry-model lesson.)

3. **Confirmation candles:** Do we encode `tjr-patience-r05` (wait 1–2 candles for volume/volatility) as an enforced requirement, or fold it into the "reaction" step of r01 to avoid double-counting?

4. **News blackout:** `tjr-patience-r03` has no window/impact tier. Do we defer entirely to a future news lesson, or apply a placeholder blackout (e.g. ±X min around high-impact events) pending that lesson?

5. **Confluence minimum:** `tjr-patience-r06` rejects single-confluence entries but gives no count. What is the authoritative minimum confluence / score threshold, and from which lesson?

6. **No-trade default:** Confirm the engine's default state is NO-TRADE and that absence of a qualifying setup can never produce a fallback entry (`tjr-patience-r04`).
