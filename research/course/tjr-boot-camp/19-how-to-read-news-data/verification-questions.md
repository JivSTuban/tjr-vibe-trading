# Verification Questions — Lesson 19 (owner: Jiv)

## News-avoidance buffers
1. **T_before:** What is the exact number of minutes before a red/orange release at which the engine should stop opening NEW entries? TJR never states one (only warns "news 5 min later stops you out"). Set 5 / 10 / 15 min?
2. **T_after:** TJR gives a 15/20/30-min range. Should the default post-release block be 30 min (conservative) or 15? Should it differ by impact tier?
3. **Displacement threshold:** How do we quantify "large wicks / drastically affected the market" that keeps the block active (e.g. release candle range > X * ATR, or > N pips)?

## Hard-block set
4. Confirm the always-avoid set is exactly {CPI, PPI, FOMC, NFP} and that FOMC includes the rate decision, statement, minutes, and press conference.
5. On a CPI/PPI/FOMC/NFP day, is the block the WHOLE trading day (his "sleep in") or only that release's session? Does it still allow his non-USD pair (GBP/JPY) when the release is USD-only?

## Heavy-news days
6. What red-folder count triggers session-level de-risk (proposed >=2)? And what is the exact reduced risk amount ("de-risk" / "risk less")?

## Bias direction
7. Confirm the engine should read Forex Factory's per-event "usual effect" text rather than a blanket actual>forecast=good rule (needed because unemployment/jobless-claims invert). TJR taught actual>forecast=good using CPI, but relies on the folder's stated effect.

## Scope / feeds
8. Is Forex Factory the canonical calendar feed, or do we substitute an API (e.g. an economic-calendar API) that mirrors its impact tiers and forecast/actual/previous fields?
9. Confirm currency mapping: gold (XAU) and S&P 500 news are driven by USD. Any other instrument->currency mappings needed?
10. Timezone: confirm calendar times are evaluated in the account/data timezone, and that his 8:30/9:30/10:00 examples are US Eastern.
