# Lesson 13 — Risk Management

## What TJR teaches

A discipline/risk lesson. TJR frames "the first part of risk management" as simply **how much you risk and how often you trade** [00:20-01:00, 00:57-01:00]. He distinguishes it from discipline: risk management is "phrased" as most important, but he'd say discipline / a stable headspace is the true hardest part [01:11-01:37].

**Expectation-setting.** Don't expect to make 100K in your first year — "you're going to lose money probably in your first year, probably in your second year" [02:15-02:39]. Treat losses like college tuition — you're paying for the lessons; the goal is to lose the LEAST amount of money [02:39-02:50]. Even going demo-profitable → live, there's an in-between where you lose money due to emotions [02:56-03:08].

**THE CORE NUMBERS:**
- **Risk 1–3% of your account per trade** [03:42-03:53]. Repeated: "risk one to three percent of your account size per trade" [03:49].
- **Preferred framing: risk 1–3% of your account per DAY** [10:56-11:00, 11:48-11:52]. This bundles per-trade and per-day into one cap and makes the math easy.
- Under the per-DAY cap he gives explicit allocation combinations [11:06-11:20]:
  - 2 trades at 1.5% risk each
  - 1 trade at 1% risk
  - 1 trade at 3% risk
  - 3 trades at 1% risk each
  - "Either way you're still within that threshold."
- **Some days you take zero setups → risk 0% that day.** Other days you may see two setups and "go heavier on the risk because all the biases are aligning" [11:30-11:43].

**Why 1% works (the math he states)** [05:04-06:09]:
- Risking 1% per trade means you'd have to **lose 100 trades in a row** to blow the account — which won't happen.
- Even losing **80% of the time** at 1% risk, "at the end of the year you'll still have 20% of that account left" (money saved vs blowing it in two weeks and refunding).
- He asserts you'll probably get "at least 2 out of your 10 trades" to take profit even trading badly (~20% win rate floor, "whether from luck or...").

**The over-trading trap** [06:11-06:28]: 1% per trade = 100 trades to lose everything, BUT if you take **100 trades in a day**, the account is gone in a day. Hence the daily cap. Trading is "risk on" — a risk-on marketplace/asset/job.

**Emotionless execution + real P/L swings he cites** [07:31-08:14]:
- You have to be able to make "up to 60K in a day" and be emotionless, and also lose — "I lost like 27K like two weeks ago in one trade in a day."
- "The second your emotions plug in, boom, you're [done], consider that account gone."
- Over-trading or risking more than your set amount = "when you're screwed."

**The $200K test (mindset device)** [09:11-09:44]: Would you, with $200,000 in your account, risk 20–30% per trade, risk your entire account, take 10 trades a day, or be okay losing 10 trades/day at that risk? No. "You have to treat it as if it is at that size" even when it's small — like acting the way NBA players act before you're in the NBA [09:44-10:17].

**Live to trade another day.** The whole point of 1–3%/day is survival: "all you're doing is living to trade another day... there will always be setups tomorrow. This market is not going anywhere." Stop trying to rush zero-to-100K in under a month [11:52-12:16].

**Skill before money.** New traders "want money first" and ignore the skill — so they don't get the money. Dedicate yourself to understanding how the charts move; the skill is "the glitch," an "infinite money glitch." Reading the S&P 500 / DXY correctly = "insider information" [13:44-14:44]. Over-leveraging/over-trading to dig out of a hole only digs deeper — he was personally in debt, indebted to friends, from doing exactly that [14:47-15:33].

**Homework** [04:44-05:01]: learn to calculate position/lot size for YOUR instrument. A Google search or a "lot size calculator / position size calculator" gives you how to risk 1% given your stop loss — for Forex (pip stop), Futures (2/5/10-point stop loss examples cited), or options. TJR explicitly won't explain the math ("that's your homework").

## Codex interpretation — RISK ENGINE PARAMETERS

Directly codable (all from TJR verbatim):
- **Per-trade risk: 1% min, 3% max of account equity.** Hard reject any trade sized outside [1%, 3%].
- **Per-day aggregate risk cap: 3% of account.** Enforce SUM(open+realized risk today) <= 3%. Valid daily allocations include 1x3%, 2x1.5%, 3x1%, 1x1% — any partition summing <= 3%.
- **Zero-setup days => 0% risk (no forced trades).** Trading is optional; no minimum activity.
- **Position sizing = f(account%, stop-loss distance).** Compute lot/contract/position size from the % risk and the SL distance (pips for FX, points for futures, premium/SL for options). Standard position-size formula; TJR defers the arithmetic to a calculator.
- **Implicit max-trades control:** the per-DAY cap bounds trade count at a given per-trade risk (e.g., at 1% each, max 3 trades/day to stay <= 3%). This is the machine-enforceable form of "don't over-trade."
- **Constant-fractional sizing regardless of account size** ($200K test): size off the SAME % rules even on a small account.
- **"Go heavier when biases align"** = allow up to the 3% end of the range on high-conviction, multi-confluence setups; still capped by the daily 3%.

Anecdotal / NOT parameters: $60K/day upside, $27K single-trade loss, 100K/year, "2 of 10 trades win," "lose 80%" — these are illustrative, not modeled inputs (though the 80%-loss/1%-risk => 20% account-remaining is a valid worst-case sanity check).
