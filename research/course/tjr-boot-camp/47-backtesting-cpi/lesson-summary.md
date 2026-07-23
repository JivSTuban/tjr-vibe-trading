# Lesson 47 — Backtesting CPI (live hindsight markup on a CPI day)

## What TJR teaches

A live-on-Zoom **hindsight/"aim-bot" backtest** across four instruments on a **CPI
news day** they chose not to trade. Method: mark out lines at market open, then walk
each instrument in hindsight explaining how it *could* have been traded and — mostly —
why he'd have avoided it [00:02–00:51]. The recurring lesson: **don't trade CPI days.**

### S&P 500 [01:03–06:01]
- Pre-market: **weekly bullish, daily bullish, 4H bullish, 1H bullish** — "permabullish on every single time frame." Came into a daily order block and rose; 4H BOS up; 1H bullish continuation. Few real draws on liquidity besides a 15m high [01:03–01:41].
- CPI released → price ripped, made an imbalance, drew toward it, then fell after market open, filled an order block, rallied into the imbalance, then **5m BOS up** off a candle. "Something you probably could have entered long off of" because 4H/1H/daily bullish [02:25–02:38].
- **Why he'd avoid it:** on CPI "most of the time the move has already been made." The CPI candle itself was a **27-point move**; the tradeable moves afterward were only ~**4-point** and ~**12-point** — "just that one CPI candle is usually the majority of the move." Also, a 5m BOS to the downside into an order block was **short-lived — just an hourly-timeframe retrace** [02:41–04:10]. Net: probably no trade; if any, a long off the 5m break, with equilibrium as extra confluence [04:10–04:23].
- Teaching aside — **retrace rule:** a 15m BOS against an hourly uptrend is usually an hourly retrace; a 5m BOS against a 15m uptrend is usually a 15m retrace; an hourly BOS against a 4H is usually a 4H retrace. "Higher timeframes hold higher power" [04:36–05:57].

### GBP/JPY (GJ) [06:01–09:32]
- **Bearish daily bias** (first bearish weekly candle, BOS down on daily); retracing on the weekly. Weekly retracement tools: an FVG and equilibrium (co-located) that price can draw toward [06:37–07:16]. 4H and 1H both still bearish — "every single thing is telling us bearish, including the weekly because we're retracing down into those areas" [07:31–07:38].
- Marked Asian-session and London-session high/low. London high got pushed into during New York session (barely — "valid or not is up to you"). Got a **BOS to the downside**; you can **short purely off that or wait for price to react off the order block** off that candle, **stop above**, target previous draws (order block above unhit, resting liquidity, or use the daily low as start of a new FVG) [08:35–09:17]. "That's how I probably would have traded GJ."

### Gold [09:32–12:31]
- Bearish weekly; bearish daily but "kind of not really anymore" (likely to close above and break daily structure within ~3 hours) — bearish until it closes above the swing high [10:11–10:52]. 4H was bullish pre-market; 1H not really bullish. **Conflicting biases** (bearish weekly, bearish→uncertain daily, bullish 4H, bearish 1H) → "you probably don't want to be trading under those conditions." Forex session strategy did work (London lows pushed into → BOS), but the BOS was **right during CPI** so not ideal [10:56–12:26]. Would have avoided.

### GBP/USD (GU) [12:31–14:57]
- "Shitty price action" day, no clean London high (trend-line traders profited during lunch). Price took London-session lows → BOS up → rallied into Asian-session highs → took liquidity → fell → filled imbalance → pushed higher [13:05–14:04]. **Bullish daily, bullish weekly** — GU had already reached the previously-stated target (top of the imbalance) that he'd been calling. But **4H bullish while 1H bearish**, and the reaction point had **no FVG, no order block, no equilibrium** — "not a good spot to be trading in." Would have avoided [14:04–14:57].

### Verdict [14:57–15:34]
Gold and GU: avoided. GJ: probably avoided. S&P: maybe could have caught something. Overall the day demonstrates **trading during CPI is not the smartest — super low-volatility move after the news candle, and you're trading way later into the session than you need to be.** Next-day plan: hop on Zoom for PPI, possibly make it a boot-camp video on charting during news to build confidence (this becomes lessons 48/49).

## Codex interpretation

- This is a **worked "when-not-to-trade" dataset** on a CPI day, reinforcing lessons 43/44/46. Machine value: labeled examples of setups that pass or fail the filter stack.
- **News-move exhaustion heuristic:** on CPI/PPI, the release candle captures most of the day's displacement (here 27-pt release vs. 4-pt / 12-pt residual moves); post-news follow-through is low-volatility. Encode as a strong penalty on entries after a same-day high-impact release.
- **Multi-TF alignment as the filter:** the instruments he'd trade had all TFs aligned (S&P) or a clean HTF-aligned sweep+BOS+OB (GJ); the ones he avoided had *conflicting* biases across TFs (gold: bearish weekly/bullish 4H/bearish 1H; GU: bullish 4H/bearish 1H) OR no building block at the reaction point (GU). Rule: require TF alignment AND a building-block reaction zone.
- **Retrace rule (formalized):** a BOS on TF_n against the trend of TF_(n+1) is by default a retrace of TF_(n+1), not a reversal — unless a liquidity sweep / change of market structure says otherwise. Consistent with lessons 43, 44, 49.
- **GJ short template** is the cleanest tradeable idea: HTF-aligned bearish + session-liquidity sweep (London high into NY) + BOS down + optional OB reaction, stop above the OB/sweep, target prior draws.
