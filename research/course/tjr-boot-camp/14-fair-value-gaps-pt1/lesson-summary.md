# Lesson 14 — Fair Value Gaps Pt 1

(ASR header misstates the day as "16 or 15 maybe" — manifest confirms Day 14. Recorded in Miami, second take after his computer overheated.)

## What TJR teaches

Part 1 of the FVG series (also split into ~3 parts like liquidity, for absorption) [00:46-01:07]. Today is conceptual only — what FVGs are, why we use them, how to understand them; **how to SPOT them is deferred two days** [00:30-00:34, 08:14-08:18].

**Definition — synonyms.** Fair value gap = liquidity void = imbalance. "All of those are pretty much the same thing" — TJR prefers "liquidity void" [02:00-02:09]. A FVG is the **opposite of liquidity**: whereas a liquidity pool is where orders reside/get targeted, a FVG is "a void, a price range where there are no contradicting orders" [02:23-02:29].

**How it forms.** A big move up happens *because* there are no sell orders through that price range — that empty range IS the imbalance/FVG [02:32-02:41]. Mirror to the downside: a sharp drop with no hesitation = a liquidity void because there are no resting BUY orders throughout that drop. If there WERE resting buy orders, price would pull up / go down slower but still fill them; the absence produces the big candle [02:43-03:07]. Signature: FVGs usually appear as a **big candle** (up or down) because nothing stops price from travelling that far [05:31-05:50].

**Why it's useful — retracements.** In a trend (higher highs / higher lows), retracements draw back INTO the areas where liquidity was absent [03:15-03:32]. Once price returns into the void, market makers can execute orders there (they know it's an emptiness of liquidity and price will move their way) [03:32-03:45]. Key usage statement: **"Fair value gaps are used for retracements. I don't use fair value gaps for entries necessarily. I use liquidity sweeps to understand where the market's going, and then I use fair value gaps to figure out where price wants to draw to, or for a secondary entry"** [03:58-04:18].

**How it plugs into the setup.** Price in an uptrend draws back down → find a liquidity void → see a reaction off it OR a break of structure on a lower timeframe → execute, because you know there's a lack of opposing orders in that range and the trend is up [04:20-04:51]. He contrasts (again) with support/resistance "hit a ceiling" reasoning as nonsensical [05:10-05:19, 08:05-08:12].

**Building-block philosophy** [06:46-07:52]: FVG, liquidity, order block, etc. are interchangeable *execution pieces* — "one size fits all," tradeable on any timeframe and any pair / any financial market, because it's how price moves. More confirmations = higher confluence. He notes swing trades (multi-day) vs scalping are both possible with the same concepts.

**The canonical combined chain he restates** [06:02-06:21, 06:31-06:46]: liquidity sweep → break of structure → trend forming → fair value gap noticed → FVG gets filled → lower-timeframe break of structure → enter.

**Homework** [08:18-08:41]: none on charts — just "do something productive": watch, take notes, then go do something hard/uncomfortable (gym, run). Growth comes from discomfort.

## Codex interpretation

- **FVG / imbalance / liquidity void = strict synonyms** in the engine.
- **FVG = a 3-candle-style price range left unfilled by an impulsive move** (no opposing orders): a bullish FVG below current price in an uptrend, bearish FVG above in a downtrend. (Exact 3-candle detection rule deferred to "how to spot" lesson — do NOT finalize detection here.)
- **Role separation (important for the state machine):**
  - Liquidity sweep = directional/bias trigger ("where the market's going").
  - FVG = **retracement target / draw-to zone**, and a **secondary (not primary) entry** location. TJR explicitly does NOT use FVG as his primary entry.
  - Primary entry still comes from the sweep→BOS chain (lessons 08/12).
- **Entry via FVG (secondary):** when price retraces into an HTF FVG and prints an LTF break of structure (continuation), enter in the trend direction. This is a continuation-into-void entry, distinct from the reversal-at-sweep entry.
- **Timeframe/instrument agnostic** — same detection logic across all TFs and markets.
- Full FVG detection mechanics (gap boundaries, minimum size, mitigation/fill %) are UNSPECIFIED here — deferred to Pt 2 (lesson 16).
