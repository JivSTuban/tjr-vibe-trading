# Lesson 37 — Taking Profits (TP placement rules)

## What TJR teaches

This is the dedicated **take-profit / exit** lesson. Earlier execution lessons deferred SL/TP/R:R specifics to here; below is every exit and R:R number stated.

**Core rule: TP goes at your building blocks** [01:49–02:19]. Take profits are placed at building blocks (order block, FVG/imbalance, liquidity draw) — "our areas where price is likely going to react off of or where price could fill orders." These are **price magnets** [08:09, 10:42].

**Timeframe for TP** [03:39–05:27]: Set TPs based on the **execution timeframe** you're on, or **one higher timeframe** than execution.
- First take profit = the **one-higher-timeframe draw on liquidity** [03:39, 04:35].
- Remaining take profits = building blocks on the execution timeframe [04:40].
- Example: entering on 5m → scale up to 15m, find the first draw on liquidity in trade direction = TP1 [03:52–04:08].

**Don't set TPs off one-minute confluences** [09:26–09:34]: "higher timeframe holds higher power." If you entered off a 5m BOS + 1m entry, target the 5m order block (not 1m confluences).

**Number of TPs** [04:21–04:33]: TJR usually sets 3–4 take profits. Not strictly necessary — put your chosen count in your trading plan. Example plan: 3 TPs where TP1 = one-higher-timeframe draw on liquidity, rest = building blocks.

**R:R targets (the exact numbers)** [05:52–06:04, 06:39–06:44]:
- First take profit is usually **minimum 1:1** ("that's kind of the goal") [06:39].
- Realistic first-TP R:R for beginners: **1:1, 1:1.5, 1:2, 1:3, 1:4, 1:5** [05:57–06:04]. He explicitly says most beginners will NOT get a 1:10 on first TP [05:52].
- Higher R:R (e.g. targeting 4h liquidity) is possible only "if you want to stay in the trade that long and genuinely think it's going to get up there" [04:52–05:00].

**Multi-TP walkthrough (S&P, 4h entry)** [06:16–07:14]:
- Enter off 4h breaker structure up / FVG fill, stop underneath.
- TP1 = ~1:1, matched to a high draw-on-liquidity.
- TP2 = next draw on liquidity (skip the order block that "envelops this high already").
- TP3 = another draw on liquidity higher up.

**Multi-TP walkthrough (Forex)** [07:21–08:07]:
- Liquidity sweep → breaker structure up → enter, ideally want 1:1 minimum.
- TP1 = top of the imbalance within.
- TP2 = base of a 4h order block.
- TP3 = 1h order block.
- TP4 = liquidity all the way up.

**Real trade (Friday, closed break-even)** [08:35–10:07]:
- Entered off a 5m break of structure + 1m order block entry. Stop slightly above entry high.
- TP1 = the 5m order block (because entered off 5m BOS + 1m entry → target 5m, not 1m).
- TP2 = under the second draw of liquidity.
- Additional TPs: scaled up to 15m → FVG = another TP.
- Outcome: closed break-even because "price was taking forever."

**Priority hierarchy of skills** [05:33–05:43]: Daily bias (biggest) > execution > stop loss > **taking profits (least of your worries)**. If execution is good, price goes in your favor and TP is easy.

## Codex interpretation

- **TP1 target = min 1:1**, and beginner-realistic ceiling on first TP ~1:5. Encode `R:R_TP1 >= 1.0` as a floor; a scorer can reject setups whose nearest valid building-block target gives < 1:1.
- **TP ladder generator (machine rule):** for an entry on timeframe X, TP1 = nearest draw-on-liquidity on timeframe X+1 in trade direction; TP2..TPn = successive building blocks (imbalance top, OB base, next liquidity) on X. Cap at 3–4 TPs.
- **Timeframe guard:** never derive a TP from a timeframe lower than the execution timeframe. Targets must come from execution TF or higher.
- "Price magnets" = building blocks are the machine target set: {order block edges, FVG/imbalance top+bottom, liquidity pools, liquidity void}. Price is expected to draw toward these.
- These are the canonical exit inputs the risk engine needs; combine with Lesson 38 (SL = invalidation) to compute R:R.
