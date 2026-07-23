# Lesson 42 — How to Backtest (backtesting method)

## What TJR teaches

TJR's backtesting philosophy, given as "what I know, not what you want."

**Bar replay is NOT his preferred method** [01:12–01:24, 02:51]. Reasons:
1. **Locked to one timeframe / no live multi-TF data** [01:47–02:47]: On bar replay, if you set it on the 15m and then switch up to daily/4h/1h to read HTF bias, it shows the **full completed HTF candle** (future information), not the in-progress candle at that moment. So you can't do a proper top-down read — you're effectively stuck to one timeframe, and can't adapt bias to HTF the way live trading requires [04:10–04:18].
2. **Lagging / not live data** [06:39–06:47]: bar replay "is lagging bro, it's nothing in comparison to a live moving market."
3. **No emotions** [06:56–07:47]: In bar replay candles print bar-by-bar (bam, bam). In live trading a forming candle ticks up/down/up/down creating wicks that "scare you" / cause emotion. The **psychology only comes out in live trading**, so bar replay under-tests the hardest part.
4. **Worse win rate expected on bar replay** [04:28–04:36]: because you can't read daily bias properly, "you're probably going to get a worse win rate on bar replay than in live markets."

**His preferred backtest = "target practice" / "Aimbot practice" on a full chart** [02:51–03:18, 04:50–05:32]:
- Don't use bar replay. Scroll back to a **random day** on a full chart, pick a start point, and analyze **top-down**.
- Just **spot examples of your strategy**: liquidity sweep → break of structure → order block → find an entry → scale down 4h → 1h for more confluences.
- Repeat the building-block drills (order block day, FVG day, liquidity sweep day, break of structure day) over and over until spotting them becomes **robotic/instant** [05:17–05:27, 08:32–08:42].
- Whatever helps you learn/develop your skill is what's "correct" — it's individual [03:53–03:58].

**Weekend routine (if you can't trade live)** [07:57–08:25]: Go back over the **previous week, every single day**, find **one or two good trades** you could have taken on a pair, and mark all your building blocks throughout those days (liquidity sweep, break of structure, where market is going). Envision it. This makes live spotting easier.

**Validate strategy through LIVE / DEMO, not bar replay** [04:36–04:48, 09:44–10:00]: "The best way to test your strategy is through live market." If you want to backtest properly, **live-test on demo** using your strategy. Judge your trading ability purely off live markets. If not profitable yet → demo or a "baby live account."

**Backtest vs psychology** [08:47–09:03]: Target-practice backtesting builds strategy/building-block recognition; what it's *missing* is the headspace/psychology, which only live trading develops. Once you can spot setups live AND have the psychology, "you should be profitable"; if not, chip away at the small mistakes.

## Codex interpretation

- **For the automated engine, TJR's guidance implies the validation harness should use *live/replayed tick data that respects the point-in-time state of every timeframe* — NOT a naive bar-replay that leaks completed HTF candles.** His #1 complaint (bar replay shows the full HTF candle) is exactly a **look-ahead-bias** warning. Machine translation: the backtest must reconstruct each timeframe's *as-of* (partial) candle at the simulated timestamp; never feed a completed higher-TF candle whose close is in the simulated future.
- **Multi-timeframe top-down must be preserved in backtest:** the sim must expose daily/4h/1h/15m/5m states consistent to the same moment so bias can be read (and adapted) correctly. A single-timeframe replay is invalid.
- **Metric caveat:** TJR expects bar-replay win rate to understate live win rate; conversely, a look-ahead-leaking backtest would OVERstate. For a safety-critical engine, the takeaway is: eliminate look-ahead, expect backtest metrics to differ from live, and treat demo/forward-testing as the real validation gate.
- **Human/psychology component is out of scope for the automated engine** — but the lesson confirms strategy-recognition (building-block detection) can be validated on historical data, while execution-under-emotion cannot; for an automated system emotion is a non-factor, which arguably makes disciplined backtesting MORE valid than for a human.
- No numeric parameters (no %, R:R, session times) in this lesson — it is methodology only.
