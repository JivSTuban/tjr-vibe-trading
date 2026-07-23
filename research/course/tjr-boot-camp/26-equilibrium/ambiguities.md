# Ambiguities — Day 26 (Equilibrium)

## ⚠️ Verbal slip (must resolve before coding)
- At `[07:00]`–`[07:23]` TJR says price **above the 50% mark "is considered a DISCOUNT to go short."** This is a **misspeak.** Above 50% = **PREMIUM** (expensive) = correct zone to **short/sell**; below 50% = **DISCOUNT** (cheap) = zone to **buy/long**. His intent is unambiguous from the rest of the lesson (Doritos analogy, "banks buy on sale," "they wouldn't want to enter within a premium because it's expensive"). **Canonical mapping to use: above 50 = premium = sell; below 50 = discount = buy.** Do not let the ASR/transcript word "discount" at [07:00] corrupt the rule.

## Load-bearing gaps for coding
- **Reference swing is undefined.** `[07:53]` TJR says "a swing high to a swing low or a swing low to a swing high" but never specifies WHICH swing: which timeframe, which leg (the impulse leg that broke structure? the full HTF range? the most recent swing?). The equilibrium level is meaningless without this. **This is the #1 gap** — the on-chart lesson (Day 28) should define it. Do NOT finalize the equilibrium rule from Day 26 alone.
- **"Reaction off" a level** `[09:49]` — no definition (candle close beyond? rejection wick? engulfing?). Needed for the FVG/OB entry trigger.
- **No sub-levels beyond 50%** are given here (no premium/discount depth like fib 0.62/0.705/0.79 OTE). Day 28 may add them.
- **"Bad risk reward"** `[13:59]` for skipping a BOS entry is not quantified (no min R:R stated in this lesson; see Day 22 / risk lessons).
- **FVG-in-discount overlap** `[10:03]` — must the FVG be fully inside the discount, or is partial overlap enough? Undefined.

## Scope note
- This is explicitly the **VERBAL EXPLANATION** video. TJR says the chart application ("a bunch of examples") comes "in two days" = **Day 28 (Equilibrium pt.2)**. No walked trade examples with prices here (only a recent trade referenced verbally, no levels). examples.yaml is skipped.

## ASR corrections (non-obvious)
- "equal lip / equally room / equal equilibrium" -> **equilibrium**.
- "order Cox / order [__]" -> **order block**.
- "liquidity Suite / breakthrough structure" -> **liquidity sweep / break of structure**.
- "in Balance / imbalance" -> **fair value gap (FVG) / imbalance**.
- "50 Mark" -> **50% level (equilibrium)**.
- Heavy unrelated banter (drugs, business partner, Discord promo, school-play video) fills ~half the runtime; none is trading content.
