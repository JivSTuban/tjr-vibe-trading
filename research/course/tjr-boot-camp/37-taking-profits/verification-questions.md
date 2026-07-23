# Lesson 37 — Verification Questions (owner: Jiv)

1. **TP price convention:** For each building-block type, which edge is the TP? (OB near/far edge? FVG top/bottom/mid? liquidity pool exact level?) TJR is inconsistent — pick a deterministic rule per type and direction.
2. **1:1 floor enforcement:** Should the risk engine hard-reject setups whose first valid target < 1:1, or only flag/deprioritize them?
3. **R:R scoring basis:** Score on first-TP R:R (min 1:1) or on a blended/weighted R:R across the 3-4 scale-out targets?
4. **Default TP count:** Fix the engine default (3 or 4) and the scale-out fractions per TP (TJR does not state position % per TP).
5. **"Draw on liquidity" algorithm:** Define programmatically what counts as the "one-higher-timeframe draw on liquidity" that becomes TP1.
6. Decode the garbled 06:04 line ("one to five on 4K trade on BDS on GDK") — confirm it's just example R:R references and not a distinct rule.
