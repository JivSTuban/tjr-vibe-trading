# Boot Camp Day 49: Daily Bias / Backtesting + $9k Loss SPX Trade Recap — Lesson Summary

Primary topic: example (live daily-bias walkthrough + losing SPX trade recap + backtesting reflection)

## What TJR teaches

**Format.** Combines daily bias (multi-pair, top-down) with a live trade, then a recap of how the bias played out and what could have been done better [00:02]. High-impact news (prelim consumer sentiment) came out 30 min after the market open, so no trading until then [01:07].

### Multi-timeframe bias, pair by pair
- **S&P 500 (SPX):** bullish on daily, weekly, 4H, and 1H — full alignment [01:07]. He marks bullish building blocks in line with the bullish sentiment: bullish order block, 15m order blocks, a bullish FVG, and a 15m low as confluence [01:41]. Notes he's been preferring **hourly building blocks over 15m building blocks on the S&P** lately — works better [02:34]. He believes SPX is overbought and a retracement is likely, "but can we go against daily bias? No" [02:52].
- **Key teaching quote:** "Your goal should be to lose trades based on high-timeframe reversals, not based off of execution errors." The best loss is: you traded within the daily bias but the daily bias itself shifted market structure that day [03:11].
- **GBPJPY (GJ):** retracing up into a bearish 4H order block; bullish 4H/1H but bearish daily → conflicted, so odds of taking a trade are low. He needs **at least the daily AND the 4H in confluence** before trading; a 4H BOS requires a 1H BOS first [04:03].
- **Gold:** bearish weekly, bullish daily → trade the daily (want bullish confirmation). Needs daily to break structure back down to confirm weekly continuation before shorting [05:28]. Spotted a 1H bullish setup: BOS up + liquidity sweep at a London low, in confluence with his Forex strategy — a takeable trade waiting only on a **5m break of structure** [06:33]. Notes **news affects Forex more than SPX** lately [08:34].
- **GBPUSD (GU):** very bullish daily+weekly but 4H just broke structure down → likely daily retracement, won't trade. "Don't go against your daily bias… take a trade off high-timeframe bias in line with low-timeframe confirmation" [11:49].

### Trading philosophy asides
- Defends taking news days off and low trade frequency: "less days in the market, higher chance of probability"; the market "is built to beat you," so don't trade on days you're likely to get beat [13:11]. Best traders take ~10 trades/month, big wins and small losses [14:26].
- **Retracements are the hardest thing to trade** — you can't know which building block price will draw to, so you map every building block and act on the *reaction*, trying to catch the *extension*, not the move down [15:19]. Extensions/legs-in-trend are where volume and volatility go — "clean higher highs and higher lows"; retracements are "doji doji doji," choppy, no volatility [16:34].

### The losing trade recap (SPX)
- Setup as seen: bullish daily/4H/1H/15m. Confluences to enter: price continued up, then a **liquidity sweep**, which "wasn't necessarily enough" [19:44]. Waited for a **break of structure up** (didn't enter off the BOS alone — wanted more), then waited for price to retrace **back into equilibrium** and show a **strong rejection**, closing strong — that candle was the entry [19:55]. Stop just below the wick of that area [20:12].
- **Outcome:** price moved up close to TP1, never hit it, came back down and stopped him out. **Lost $9.5k that day** [21:25].
- **What could have been done better:** wait for the **higher-timeframe building blocks he'd marked out** to get hit before executing — the sweep he used was **lower-timeframe liquidity**, not the HTF liquidity sweep. "Don't settle for anything less just because price is taking forever to move" [21:39].
- Declined a revenge/second trade — no reason to add risk after making back last week's losses and then losing $9.5k [21:13]. "I'm going to stick to my plan because I am a smart trader" [24:32].
- Bias was ultimately **correct** (price came into the marked order block, filled the FVG and rallied) — "it was the execution that failed" [28:07].

## Codex interpretation (explicitly inferred — NOT verbatim rules)

- Reinforces a **confluence-of-timeframes gate**: enter only when daily bias AND at least the next-lower structural timeframe agree; require nested BOS (4H BOS presupposes 1H BOS).
- Distinguishes **HTF liquidity sweep** (valid entry trigger) from **LTF liquidity sweep** (insufficient) — the scorer should weight the timeframe of the swept liquidity, not just the presence of a sweep.
- Entry sequence observed here: HTF-bias-aligned → **liquidity sweep of HTF liquidity → BOS → retrace to equilibrium → strong rejection candle close** → enter; SL below the rejection wick.
- **Loss taxonomy** is machine-relevant: label losses as "bias-invalidation" (acceptable) vs "execution-error" (avoidable); a risk/journaling engine should track this ratio.
- Numeric anchors: instrument SPX; a single-day loss of **$9.5k**; per-lesson risk figures otherwise unstated. Instrument-agnostic thresholds (what counts as "strong rejection", "close to TP1") are not defined.
