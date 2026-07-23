# Lesson 36 — Daily Bias pt. 3 (recap of multi-timeframe top-down workflow)

## What TJR teaches

This is a **recap lesson** consolidating the daily-bias / top-down process from prior lessons, applied live to S&P and GBP/USD ("gu") charts.

**Higher timeframe holds higher power** [00:53]. Whatever the higher timeframe is doing dictates where the market ultimately moves. A lower-timeframe move against the HTF is just a retrace.

**The retrace/expansion ladder** [07:44–08:01]: he chains the timeframes so each lower one is a retrace of the next higher one:
- 15m break of structure = 1h retrace
- 1h break of structure = 4h retrace
- 4h break of structure = daily retrace
- daily break of structure = weekly retrace
- (and weekly BOS into monthly, etc.)

So a 15m BOS to the downside inside a bullish HTF is NOT a bias flip — it is a 1h retrace [07:44]. He warns: "stop getting trapped into the low timeframe bias" [10:18]. A 1m BOS could just be a 5m retrace [09:29].

**Weekly context example** [00:33–01:08]: if daily breaks structure down but the weekly is in an uptrend, odds are it's a weekly retrace — use retracement tools (Fib/retracement) to find where price wants to draw to. Ideally price comes to at least **equilibrium (50%)** or fills the fair value gap before continuation [01:17–01:25].

**The workflow** [05:30–07:39]:
1. Weekly → understand the macro (retrace vs expansion), where draws on liquidity are.
2. Daily → determine daily bias / market structure (e.g. daily BOS up = look for buys).
3. Scale down 4h → 1h: confirm same direction ("even better for long positions").
4. Use **building blocks** (order block, FVG/imbalance, liquidity) to mark **high-confluence areas** on 1h/4h.
5. 15m / 5m → map more high-confluence areas (LTF confluence) and **execute** when price reaches a HTF confluence AND gives a low-timeframe confirmation (liquidity sweep + 5m break of structure) [07:22–07:39].

**Confluence stacking** [00:32:59–00:37:00 approx / 07:33]: daily bullish + weekly bullish + 4h bullish + 1h bullish + 15m "execute" = take the trade. When all biases align you take the **extension** (big leg), not the retracement (small leg) [09:02–09:21]. "Personally I'm taking the extension every single day."

**No-reaction rule** [09:43–10:12]: he pre-maps confluence areas during his Zoom call. If price enters a marked area and gives a reaction, execute. If it enters and gives NO reaction / doesn't give the move wanted, treat it "like it was never there" — discard that area, don't execute.

**Order block validity example** [06:52]: a down candle is an order block because it swept lows, caused a rally higher, and orders were filled there.

## Codex interpretation

- The retrace/expansion ladder is a **rigid nesting rule** that could be machine-encoded: `LTF_BOS_against_HTF_bias => classify as retrace of (LTF+1), NOT a bias flip`. This is a scorer/guard input: suppress reversal signals on a timeframe when they contradict the timeframe two levels up.
- "Take the extension, not the retracement" = **only trade in the direction of aligned HTF bias**; never counter-trend on LTF noise.
- "Give a reaction or it's discarded" is a concrete **entry gate**: a confluence zone only arms an entry if price shows a confirming reaction (sweep + LTF MSS) on arrival; otherwise the zone is invalidated for that visit. This is inference — TJR does not define "reaction" numerically (see ambiguities).
- No new numeric risk parameters here; this lesson is conceptual/process. Session times, R:R, and lot math are NOT covered.
