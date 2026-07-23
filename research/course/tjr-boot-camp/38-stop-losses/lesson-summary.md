# Lesson 38 — Stop Losses (SL placement rules)

## What TJR teaches

Dedicated **stop-loss** lesson. SL is fundamentally the **invalidation point** of the trade.

**Core rule: SL above the liquidity sweep** (short) / below it (long) [01:24–03:08]. For a short entered off liquidity-sweep → break of structure → OB/FVG entry, put the SL **above the liquidity sweep**. Rationale [01:43–02:31]: if the bias was correct and liquidity was truly swept, price has no reason to return above that high. If price comes back above the sweep high, the sweep was invalid — not enough volume/volatility, not enough orders filled to push price in the bias direction → the trade is invalidated. "Our stop loss always has a purpose... our stop loss is essentially our invalidation area" [02:29–02:35].

**SL must be ABOVE the sweep, not right above the entry high** [03:39–03:57]. Whether entering off an FVG or an OB, the SL still belongs above the liquidity sweep — NOT immediately above the entry candle's high, because price could poke slightly higher and come back down. The invalidation is the sweep, not the entry.

**Account for spread — 0.5 point / spread buffer** [03:00–07:25, 11:11]: Never place the SL directly on the exact price level. Add a buffer — TJR suggests **at least ~0.5 points** below/above the actual level, or look up your broker's spread for that pair. If placed exactly on the level, bid/ask spread will stop you out even when price only touches the level. Their real trade used a **4-point buffer** below ("four below"). "It should not be based purely off of points or Pips, it should be based off of where price is invalidated" [11:14–11:22].

**Exception — elongated stop / bad R:R case** [01:08–01:14, 04:07–05:19]: TJR rarely uses an elongated stop. If the liquidity sweep is so far away that stopping there gives terrible R:R, he looks for another confluence (FVG or OB) inside and places the SL above THAT order block instead of above the sweep. He dislikes this because the true invalidation is still above the sweep, so price can take you out and still go your way [05:07–05:16].

**Exception — HTF trade, scale down for tighter SL** [08:12–09:25]: On a higher-timeframe trade where the sweep is very far (huge SL, bad R:R), scale into a relatively higher-execution timeframe and find a lower structure one scale below the liquidity sweep — a lower high/low under the sweep — for a tighter stop, "if you want to be extra safe." Keep risk management in mind.

**SL is driven by risk tolerance + invalidation, not fixed points** [09:26–11:22]: Two determinants: (1) where the bias is invalidated, and (2) your personal risk tolerance. Because TJR uses a **set lot size** (covered in Lesson 39), he varies lot size rather than SL distance. He de-risks (half lot size) on high-impact-news days / bank holidays.

**Real trade recap (the stopped-out trade)** [05:26–08:08]:
- Overall daily bias bullish. Entered off a break of structure / candle close.
- Considered a 5m liquidity sweep + 1m break of structure to the upside as his sweep; put SL underneath that sweep (~4 points below).
- Got "soft/wicked out" by a small move, then price moved higher (bias was ultimately correct).
- Lesson: maybe should have placed SL lower to cover; the specific execution invalidated even though daily bias was fulfilled.

**Discipline note** [12:39–12:53]: Don't trade on bank holidays (Fourth of July example) — U.S. bank holidays slow all markets. "If you trade you're literally stupid, it's a bank holiday."

## Codex interpretation

- **SL = invalidation, placed just beyond the liquidity sweep** (above for shorts, below for longs), NOT at the entry candle. Machine rule: `SL = sweep_extreme ± spread_buffer`.
- **Spread buffer** is a required additive offset: default **0.5 points** minimum, or the pair's broker spread; TJR's live example used **4 points** on S&P. Encode a configurable `spread_buffer` (per-instrument), floor 0.5 pt.
- **Elongated-stop / HTF exceptions** are R:R-optimization overrides: if `distance(entry, sweep)` produces R:R below threshold, substitute an inner OB/FVG (or a lower structure one scale down) as the SL anchor — but flag as higher-risk because true invalidation is still the sweep.
- SL distance is an OUTPUT of structure (sweep location + buffer); position size is the free variable (see Lesson 39). This is the opposite of fixed-pip stops.
- No explicit risk-% appears here (deferred to L39), but "de-risk = half lot size on news/holidays" is stated (see L39 for the 1%/2%/50% numbers).
