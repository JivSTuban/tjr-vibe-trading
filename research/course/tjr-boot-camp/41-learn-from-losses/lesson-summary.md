# Lesson 41 — Learn from Losses (loss handling & adaptation)

## What TJR teaches

Psychology/process lesson on responding to a losing streak. Core message: **make small tweaks, never overhaul the strategy.**

**Never change the strategy** [00:58–01:13]: "Definitely don't change your strategy because you've proven to yourself that it works... there's no reason to change it." The strategy doesn't get "patched" — that doesn't happen [03:45–03:50].

**Change confluences / instrument, not strategy** [01:16–01:41]: What you tweak instead: your confluences, or the pair you're trading if it isn't trading well. Example: two months ago S&P wasn't trading well (choppy, no bias, stopping him out) → he switched to **Forex** and had a **100K week**. "One small little tweak boom, that got me right back on track."

**Journal your trades to find the pattern** [02:43–02:52]: This is why journaling matters — understand WHY you're losing and spot the repeating pattern.

**His current tweak** [02:52–03:35]: He noticed he was entering on just a low-timeframe **liquidity sweep + break of structure** with **no extra confluence to enter**, and getting stopped out even though price then went his way. Fix: only take entries that ALSO have a building-block entry confluence:
- liquidity sweep → BOS → **order block entry**, or
- liquidity sweep → BOS → **fair value gap entry**, or
- liquidity sweep → BOS → order block + FVG + **equilibrium entry**.
Adding entry confluence gives better R:R and winning trades vs bare sweep+BOS.

**Bias was right, executions were off** [07:15–07:39]: In the losing trades, "every single bias was correct, it was just the small little executions." Market analysis wasn't wrong; price still fulfilled his bias each day. Fix = be more patient, add more confluence.

**Don't revenge-trade** [04:25–04:44]: "The worst thing you can do on a losing streak is continuously try and make back your money — that will put you in a terrible position." He trusts the money comes back next week/month.

**Definition of a losing streak** [08:14–08:23]: Two losing days is NOT a streak. He'd consider **two or three losing weeks** an actual losing streak. On just two losses, "that's normal" — still journal both.

**Adapt to the market, don't fight it** [09:02–10:01, 09:26–09:59]: "Market does not have to follow anything you say." Stop acting on what you THINK the market should do; act on what the market IS giving you. If you get a HTF break of structure to the downside while your bias was bullish, **adapt and switch** — if you hold the wrong bias in a bearish HTF trend you'll continuously get stopped out.

**Process** [07:34–08:00, 08:41–08:53]: Analyze losses, narrow down the repeating mistake, "chop off" each mistake so you become accurate/robotic. Also review WINS: why did I win, how could I have gotten a better R:R / better trade.

## Codex interpretation

- Not a numeric-rule lesson, but yields concrete **process guardrails**:
  - **No revenge trading:** after a loss, do not increase frequency/size to recover. (Complements a per-day loss cap — number not given here.)
  - **Entry-confluence requirement:** bare `sweep + BOS` is insufficient; require an additional building-block entry (OB, FVG, or equilibrium) before executing. This is a machine-encodable entry gate that *tightens* the L30-33 execution logic.
  - **Adaptive bias override:** an HTF BOS against current bias should flip/suspend the bias rather than being ignored — consistent with L36's timeframe ladder (HTF holds higher power).
  - **Journaling / labeling requirement:** every trade (win and loss) is logged with why + how-to-improve. Supports a feedback dataset for the scorer.
- "Losing streak = 2-3 losing weeks" gives a rough threshold for a strategy-review trigger, distinct from a per-trade loss.
