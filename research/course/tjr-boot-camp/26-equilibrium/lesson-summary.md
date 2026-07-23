# Boot Camp Day 26: Equilibrium — Summary

**Primary topic:** concept (technical) — Equilibrium / Premium / Discount. **Part 1 of a 2-part thread** (pt2 = Day 28, which walks it on charts).
**Transcript source:** YouTube auto-captions (en-orig ASR), ~18 min. This is the **explanation/verbal video** (TJR says the on-chart application comes "in two days" = Day 28). First ~5 min is banter; the definition runs ~[05:09]–[11:40].

## What TJR teaches (definitions — captured precisely)

**Equilibrium** `[05:38]`, `[06:45]`, `[07:53]`:
- "Equilibrium is essentially a **retracement tool** to literally show you where big money is likely to buy again."
- Mechanically: **measure from a swing HIGH to a swing LOW (or swing low to swing high) and find the 50% mark.** "Measuring literally the high from the low and finding the 50 mark." Equilibrium = **the 50% level** of that swing range.
- He describes it as the "**break-even price**" of the range `[07:16]`.

**Premium vs Discount** `[07:00]`, `[08:13]`, `[11:18]`, and the Doritos analogy `[05:53]`–`[06:24]`, `[11:24]`:
- **Discount = below the 50% mark = cheap / "on sale" = where you look to BUY (go long).** "Anything below that 50 mark from the swing low to the swing high is going to be a **discount** for these big banks / market movers to place more orders." "It's a discount for banks to find re-entry because it's on sale — a good price to enter (long)."
- **Premium = above the 50% mark = expensive = where you look to SELL (go short).** "They wouldn't want to enter within a premium… because it's expensive. No one wants to buy a $10 bag of Doritos; they'd rather buy the $3 bag." Buyers want a **cheaper** price; sellers/shorts want a **higher** price `[06:17]`.
- **Analogy:** a bag of Doritos normally $5 — you (and the banks) want it on sale ($2–3), not marked up ($10). Banks buy at a discount, sell at a premium.

**How equilibrium is used (NOT a standalone entry)** `[08:21]`–`[08:50]`, `[09:08]`–`[10:16]`:
- TJR uses equilibrium **as a GAUGE / bias filter, not as an entry point by itself.** "I'm not the type of person to enter purely off equilibrium." It tells you *this price range is where people would want to buy* (discount) — then you find a *reason* to enter: an **order block, a fair value gap, or a break of structure while in a discount.**
- **Best pairing:** "**equilibrium + fair value gap** … honestly the perfect tools to combine." Rule of thumb: **if you find a fair value gap that is within a discounted price and you get a reaction, enter.**
- Restated **entry toolkit / hierarchy** `[09:08]`: (1) the initial **liquidity sweep + break of structure** (MSS) is the first primary entry (the liquidity sweep is the "inducement"); (2) if you miss it, the **first retracement entry = order block** (the move that caused the sweep); (3) **fair value gap** (fill imbalance + reaction); (4) **equilibrium** paired with an FVG/OB/BOS to confirm you're buying at a discount / selling at a premium.
- Live-trade note `[13:55]`–`[14:27]`: on a recent trade he did NOT enter on the break of structure ("bad risk reward") — he waited for price to retrace to the order block (instant entry when that price hits) or the fair value gap (enter on reaction). Illustrates equilibrium/discount thinking → wait for a discounted re-entry rather than chasing the BOS.

## ⚠️ Verbal-slip flag (important)
At `[07:00]`–`[07:23]` TJR says price getting **"above that 50 mark … is considered a DISCOUNT to go short."** That is a **misspeak** — above 50% is a **PREMIUM** (expensive), which is the correct zone to **short/sell**. His intent is unambiguous from context (the whole Doritos analogy, "it's above the 50 mark, it's at a good price to go short, it's on sale [for the seller]"). **Canonical mapping (use this, ignore the slipped word "discount"): above 50% = PREMIUM = sell/short zone; below 50% = DISCOUNT = buy/long zone.** Logged in ambiguities.

## Codex interpretation (labeled inference toward machine rules)

- **Equilibrium level = 50% (fib 0.5) of the reference swing** [swing high ↔ swing low]. Compute `eq = (swing_high + swing_low) / 2`.
- **Zone classification:** `price < eq → discount (long-only bias)`; `price > eq → premium (short-only bias)`. Directional gate: **only take longs when price is in discount; only take shorts when price is in premium.**
- **Reference swing selection is the key unknown** — TJR says "a swing high to a swing low / swing low to a swing high" but does NOT define *which* swing (which timeframe, which leg, whether it's the impulse leg that broke structure, or the full HTF range). This is the load-bearing gap; flagged for confirmation. The chart lesson (Day 28) should pin it down.
- **Equilibrium is a FILTER, not a trigger.** Codify as: a valid entry requires (a) price in the correct zone (discount for long / premium for short) AND (b) a concrete trigger — OB tap, FVG fill+reaction, or MSS/BOS. Highest-conviction combo per TJR: **FVG located inside a discount + reaction.**
- **Entry-tool priority for the assembled strategy:** liquidity sweep + BOS (primary) → OB (first retracement) → FVG → equilibrium-confirmed OB/FVG. This aligns with the Order Blocks lessons' deferred "order block off the first retracement in equilibrium."
- Do NOT finalize the equilibrium entry rule from this lesson alone — the on-chart mechanics (reference swing, fib settings, exact premium/discount thresholds beyond 50%) come in **Day 28 (Equilibrium pt.2)**.
