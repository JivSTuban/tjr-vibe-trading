# Ambiguities — Lesson 14 (Fair Value Gaps Pt 1)

- **Day-number in ASR is wrong** — TJR says "16 or 15 maybe." Manifest is authoritative: this is Day 14. (Recorded in Miami, second take after computer overheated.)
- **FVG detection mechanics deferred.** This lesson is conceptual; "how to spot them" is explicitly two days out (lesson 16, FVG Pt 2). Do NOT finalize a 3-candle / gap-boundary detection rule from this lesson.
- **FVG minimum size / displacement threshold** undefined ("big candle" is qualitative).
- **Fill definition** undefined: does a FVG "get filled" on a touch of the near edge, 50% (equilibrium), or full fill? Needed for r02.
- **Confirming BOS timeframe** for the FVG-fill continuation entry not fixed.
- **Confluence scoring**: "more confirmations = higher confluence" — no explicit count-to-confidence or confidence-to-risk mapping (ties to lesson 13's 1->3% dial).
- **Synonym set confirmed**: fair value gap = imbalance = liquidity void (TJR prefers "liquidity void").
- **Role clarity (resolve early):** FVG is a retracement TARGET + SECONDARY entry; the sweep+BOS chain is the PRIMARY bias/entry. Ensure the automated state machine does not fire on a bare FVG.
