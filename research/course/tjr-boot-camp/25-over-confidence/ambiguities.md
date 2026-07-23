# Ambiguities — Day 25 (Over Confidence)

- **Trade cap: "day" vs "session"** `[04:40]`. TJR says "one to two trades a day, one is best." If the strategy trades both London and New York sessions, is the cap per calendar day or per session? Not stated. Assume **per day** until a later session/strategy lesson clarifies.
- **"First trade near market open" has no clock** `[04:16]`. He cites price+time theory and "market open" as the high-probability window but gives **no exact time, timezone, or session name** in this lesson. Do not hard-code an open time from here — pull it from the dedicated session/kill-zone lesson.
- **"Volume dies out" after the first trade** `[04:53]` is qualitative — no volume threshold, no candle count. Not directly measurable.
- **News blackout list/window undefined** `[16:13]–[18:34]`. The *stance* is clear ("I don't trade news"; "don't trade tomorrow/Thursday" for Powell). But there is **no general list** of which events (only Powell/Fed-chair here; CPI/PPI/NFP are inferred), **no window** (how long before/after), and **no timezone**. Coding a news guardrail requires a dedicated news lesson.
- **No explicit per-trade risk %** `[10:00]`. He repeatedly says "don't over-risk / don't over-leverage" and references a "5K account" losing "a couple grand" as a *bad* example, but never states a prescribed risk %. Do NOT invent one.
- **"Proven profitability" (demo gate) is unquantified** `[11:54]`. No sample size or win-rate threshold for when you may scale up or go live.

## ASR corrections / notes
- "unfucking profitable" `[06:37]` = "you're NOT profitable" (ASR mangled the negation).
- "probable" is used loosely for "profitable" in places `[10:00]` (context makes it clear he means profitable).
- "white labeled ICT Strat / Silver Bullet" `[14:40]` came through — TJR argues ICT's "Silver Bullet" is just a fair value gap; used as an example of chasing a "new Holy Grail" being an overconfidence/overtrading trap, NOT a taught setup.
- "Federal chairman Powell" `[16:33]` = Fed Chair Jerome Powell (FOMC / Fed speech = high-impact news).
