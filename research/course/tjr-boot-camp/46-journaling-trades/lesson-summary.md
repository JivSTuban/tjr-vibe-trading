# Lesson 46 — Journaling Trades

## What TJR teaches

A concrete **trade-journal schema**. Goal: "cover everything and anything that could
possibly affect the trade / how you traded, so you know every single component" — like
reading analytics for social media, but for trades [00:53–01:04]. He records in
**columns**: pair, session, confluences, risk — then writes out full thoughts [02:36–03:02].

**Fields to log per trade:**

1. **Pair** [02:03] — which instrument. "Ideally you're only trading one pair because you're not profitable yet." Delete the rest of your watchlist; get really good at one pair (e.g. S&P, GJ, gold) [02:08–02:34].
2. **Session** [03:12] — New York or London, **not Asian**. Rationale: he won't wait an hour for 5 pips of movement; trade the most optimal time with the most volatility and volume — either wake up early for New York or stay up late for London [03:14–03:52].
3. **Confluences** [03:55] — every reason you entered: e.g. liquidity sweep + break of structure; liquidity sweep + BOS + FVG; liquidity sweep + BOS + order block entry. ALSO write the HTF context: what daily / 4H / 1H / 15m market structure was telling you and whether you were going along with it. Which building blocks on the 15m / 1H / 4H you took the position off of. "Write down every single reason that convinced you this was a good trade" [03:55–04:36].
4. **Risk** [04:34] — "Ideally it's 1 to 3%. If it's anything more, you're immediately doing something wrong. If it's anything less, that's completely fine. Ideally just 1% per trade" — or a set calculated lot size, or calculate it every time [04:36–05:52].
5. **Did you follow your plan?** [06:12] — write "yes, I followed my plan because I took the trade off a liquidity sweep, BOS, order block entry, waited for confluence/reaction, and everything was in line with my daily bias." Writing it drills that it works. If you *didn't* follow the plan, write what you skipped — and odds are you lost, another reminder to follow the plan [06:12–06:54].
6. **Emotions** [06:55] — what did you feel and *why*: scared to enter, overconfident, greedy (kept extending TP instead of taking profit at reaction areas), fearful due to low confidence, over-risked. Write the emotion, then the cause. Recognizing the emotion next time cues the right action (e.g. "maybe it's time to take profits") [06:55–08:00].
7. **How can you improve?** [08:02] — on wins it's harder but still do it ("I won, but I could have done this better" makes wins better and losses more minimal). On losses it's easy: "should have waited for more confirmation," "went against my daily bias," "over-risked / got emotional and cut before stop loss was hit," "placed stop loss in the wrong area," "should have taken profits at building blocks I didn't mark" [08:02–09:17].

**Why it works** [09:17–11:48]: writing it down (not just mentally noting) puts the lesson in your head; you re-read the week and spot patterns ("I took a liquidity sweep + BOS while only the 1H was bullish but all higher TFs were bearish and lost every one — now I know not to do that"). He ties it to the live example: last week he only took *liquidity sweep + BOS* and lost every trade; this week he waited for *liquidity sweep + BOS + order-block/FVG entry* for more confirmation, which avoided a loss and made money (he's in a live S&P trade during filming, about to hit TP3) [09:34–10:22]. Closing: 99% lose in this market, so a mediocre effort gets mediocre results — journaling is part of going "balls to the wall."

## Codex interpretation

- This lesson is the **journal data schema** for the self-improving loop referenced in 44/45/41. Machine encoding: a structured record per trade with fields — `instrument`, `session`, `confluences[]` (building-block sequence), `htf_context` (D/4H/1H/15m structure + alignment bool), `risk_pct`, `plan_followed` (bool + deviations), `emotions[]` (label + cause), `improvements[]`, `outcome`.
- **Concrete risk constraint (rare hard number):** risk **1%–3% per trade, target 1%**; >3% = "immediately doing something wrong." This is a direct risk-engine input.
- **Session filter:** allow New York and London sessions; exclude Asian by default. Feeds a session gate (needs exact session clock/timezone confirmation).
- **Confidence-building confirmation ladder:** liquidity sweep + BOS alone = weaker (lost every trade last week); adding an order-block or FVG *entry* = the confirmation that turned it profitable. This upgrades the entry-quality model: require a building-block reaction/entry after the sweep+BOS, not sweep+BOS alone (see also lessons 47, 49).
- **One-instrument focus** while unprofitable — a portfolio/watchlist constraint, not a permanent rule.
