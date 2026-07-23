# Ambiguities — Lesson 29: Trading Plan

Items that are vague, self-set, deferred, or garbled. All require confirmation before use in an automated system.

## Self-set / illustrative numbers (not firm rules)
- **$100/day risk** [09:32] — TJR's personal example, explicitly a placeholder for "the monetary value you're willing to risk." Not a prescribed amount.
- **5-point spike within a 5-minute candle** news threshold [12:55]–[13:17] — TJR explicitly says "this is just like me saying this randomly... you determine this yourself because I don't even know." Instrument-dependent, user-defined.
- **~2 weeks** backtest window for validating a confluence [17:13] — a rough guideline ("like two weeks"), not a statistical sample-size spec.
- **Three set lot sizes (high / regular / low risk)** [07:16] — TJR's personal system; the actual lot values and how he cycles them are deferred to "a whole separate video / next psychology day" [07:26].

## Deferred to next lesson ("putting it all together")
- Precise mechanics of **entry confluences** — how liquidity sweep, break of structure, FVG, and order block are defined, on what timeframes, and how they're combined [16:55]–[17:04], [21:07]. TJR says the confluence section is "difficult to write down right now" and will be covered next lesson.
- How **daily bias** is actually determined [18:04] — stated as a requirement but derivation method not given here.

## Under-specified rules needing external data / confirmation
- **Session clock times & timezone** — TJR names "NYSE open, first hour and a half" [11:15] but gives no explicit clock time or timezone. Needs mapping (NYSE cash open ~09:30 ET → first 90 min = 09:30–11:00 ET) — confirm.
- **US bank holiday** gate [19:57] — requires an external holiday calendar for the traded instrument.
- **Risk percent** for calculated lot sizing [07:31] — the calculator inputs are named but no default % is given in this lesson.
- **"De-risk" on two trades** [08:41] — assumed to mean splitting the daily risk budget so combined = one trade's risk; not explicitly defined.
- **"Profitable" threshold** for adding a second instrument [16:26] — not quantified.

## Jargon / ASR notes (canonical mappings applied)
- "liquidity sweet" / "liquidity Suite" → **liquidity sweep** [17:13], [18:38].
- "sweet break of structure" → **sweep + break of structure (BOS)** [17:34].
- "fair value Gap" → **Fair Value Gap (FVG)** [17:38].
- "GJ" → **GBP/JPY**; "GU" / "gu" → **GBP/USD** [15:39]–[16:12] (TJR uses these abbreviations himself).
- "4X pair" / "34x pairs" → **forex (FX) pair(s)** [13:45], [15:09].
- "scent lot / law size" → **set lot size / lot size** (ASR corruption) [07:05], [07:31].
- "us 30" → **US30 (Dow)** [13:43].
- "fomc" → **FOMC**; "NF NFP" → **NFP** [11:42].
