# Ambiguities — Day 28 (Equilibrium pt.2)

## Premium/discount wording tangle (resolve to canonical)
- At `[02:54]`–`[03:07]` TJR says "smart money never buys in a premium, **never shorts in a premium; they always buy and [short] in a discount**." Taken literally that says both buys AND shorts happen in the discount, which is muddled. **Canonical resolution (consistent with the whole lesson + Day 26): longs are entered FROM the discount (below 0.5); shorts are entered FROM the premium (above 0.5).** Banks BUY cheap (discount) and SELL expensive (premium). The "short in a discount" phrasing likely conflates "the short's TARGET is the discount" with "the short's ENTRY is the premium." Confirm before coding the zone gate. (Note this also cleans up the Day 26 [07:00] slip.)

## Load-bearing gaps
- **Reference-swing detection.** Day 28 clarifies WHICH swing (the current-trend impulse leg, re-drawn on each new high/low), but a machine still needs an explicit **swing/fractal size** and a rule for the leg boundary (structure-break leg vs most recent pivot). `[18:23]`
- **"At equilibrium" tolerance.** The OB/FVG must be "at" / "within" equilibrium `[03:38]`, `[14:18]` but how close to 0.5 (a band? +/- what %?) is undefined.
- **Second fib level (0.618 / "64 mark").** `[07:47]` TJR ties the popular **50% and ~61.8%** to equilibrium, but his shown Gann/fib settings only expose **0 / 0.5 / 1** `[04:03]`. Unclear whether 0.618 is an actionable level or just illustrative (no OTE 0.62/0.705/0.79 detail given).
- **Entry timeframe for the confirming BOS** is not fixed — 4h, 1h, and 15m are all used depending on the HTF `[13:52]`, `[15:49]`. Cross-ref Day 22 timeframe-coherence.
- **Walked trade lacks prices.** The real Discord short `[14:56]` gives direction/structure and "4 TPs, hit 3" but no entry/SL/TP levels or date -> not dataset-usable.

## ASR corrections (non-obvious)
- "equal equilibrium / equilibria" -> **equilibrium**.
- "gan box / Gan box" -> **Gann box**.
- "the 64 mark" -> **~61.8% (0.618) fib level**.
- "order [__] / order Cox" -> **order block**.
- "in Balance / imbalance / fat ass imbalance / rally Gap" -> **fair value gap (FVG) / imbalance**.
- "liquidity Suite" -> **liquidity sweep**; "regular structure / breaker structure / breakup structure" -> **break of structure (BOS)**.
- "Long John vomit / bling blob / chow chow chop" -> filler for "go long / price reacts / price chops."

## Roadmap note
- `[19:04]`: TJR decides **no Equilibrium pt3**; next is the **"putting everything together" 3-part series** (step-by-step text plan first), interleaved with psychology videos. Teased later topics: Forex strategy, **session opens**, **stop-loss placement**, **take-profit placement** -- these will supply the numbers still missing (SL/TP/session times).
