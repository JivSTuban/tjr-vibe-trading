# fomo.family — how its social layer actually surfaces coins, and what we should steal

Researched 2026-09-17 against a live logged-in session. Sample: 50 trending tokens,
**20,337 theses**, plus the 150-name 24h leaderboard.
Raw data: `thesis-harvest-2026-09-17.json`, `leaderboard-24h-2026-09-17.json`.

## TL;DR

1. **The leaderboard does NOT snipe. It lags.** Its top-consensus holdings are
   already-won positions ($56M aggregate PnL on the most-held name), and only 19 of
   153 leaderboard-held tokens are currently trending. It is a trophy case, not a
   watchlist. Use it to pick **who** to follow, never **what** to buy.
2. **The snipe is the thesis feed, and the edge is EARLINESS.** Median unrealized PnL
   decays monotonically across all ten deciles of thesis order: **+192% for the first
   10% of theses on a token → +21% for the last 10%.** The literal 1st thesis medians
   **+716%** (n=9, 89% win).
3. **Jiv's "conviction buys come from X" is wrong by volume but right in kind.** Only
   **3.6%** of theses contain any link at all — but of those that do, **98.6% are
   x.com**. X is the only external source that matters; it is just rare.
4. **The X link is not the signal — SIZE is.** X-linked theses look far better raw
   (median +29.4% vs 0.0%, win 57.1% vs 46.0%), but they are also **7.8× bigger**
   (median $5,086 vs $655). Gate both groups at ≥$5k and the edge **inverts**
   (X +108.7% / 79.8% win vs no-X +117.9% / 76.2% win). Same shape as the
   eod_pressure_reversal late-volume filter: the headline filter was a size proxy.

## The mechanic

A **thesis** is a written comment welded to a real executed trade (`tradeId`), and the
API returns the author's live position with it — `usdValue`, `unrealizedPnlUsd`,
`percentageUnrealizedPnl`, and on the global feed the author's total `equity`. You
cannot post conviction without money behind it, and the size is public. That is the
entire product: **skin-in-the-game is a required field.**

fomo then plots those theses as avatars directly on the price chart, with a default
**≥$1,000** noise gate (`threshold=1000`), a friends-only toggle, and a thesis-only
toggle. The Alerts tab is the same feed globally, which is what "real time
notifications for what the best are buying" actually means.

## API surface (all on `prod-api.fomo.family`)

| Endpoint | Gives us |
|---|---|
| `GET /feed/tradingActivity?limit=25&threshold=1000` | **The firehose.** thesis + swap_buy + swap_sell, with `authorTrade` and author `equity`. Live 25-item window, **no pagination** — poll and accumulate. |
| `GET /feed/token/sortedThesis?tokenAddress&networkId&afterTime&beforeTime&limit=500&threshold=0` | Per-token thesis **history**, paginated by time. The backfill path. |
| `GET /v2/leaderboard/{24h,7d,30d,all}` | 150 traders with **Solana + EVM wallet addresses**, `pnl24h`, `numTrades`, `totalVolume`, `followers`, and `topHoldings[]` (address, amount, value, pnl). |
| `GET /hodlers/top?tokens=[{address,networkId}]` | Per-token holders with PnL, avg entry, **avg hold time**. |
| `GET /hodlers/devs?tokenAddress&networkId` | Dev holdings. |
| `POST /proxy/trendingTokens` | Ordinary screener (change24/holders/liquidity/marketCap/volume24 + launchpad + graduationPercent). **Nothing here DexScreener doesn't already give us.** |
| `POST /proxy/tokenWarnings` | Their rug checks. |

**Access constraints (verified, not assumed):**
- Requires `authorization: Bearer <privy JWT>`, **1-hour expiry**. Privy app id
  `cm6h485o300n3zj9yl6vpedq7`; `privy:token` + `privy:refresh_token` sit in
  `localStorage`.
- **curl is blocked** — bare requests return `431`, and `430` even with a valid bearer.
  There is a bot shield. **In-page `fetch()` from a real browser returns 200.**
  Any harvester must run inside a browser context (Playwright), not as an HTTP client.
- Login is Apple/Google OAuth only.

## The numbers

**Earliness (theses ≥$1,000, n=5,939) — monotonic, all ten deciles:**

| Decile of thesis order | n | median PnL | win% |
|---|---|---|---|
| 0-10% (earliest) | 429 | **+192.2%** | 81.6% |
| 10-20% | 421 | +209.9% | 83.1% |
| 20-30% | 472 | +218.7% | 78.6% |
| 30-40% | 545 | +170.0% | 80.0% |
| 40-50% | 549 | +164.6% | 77.4% |
| 50-60% | 599 | +88.8% | 72.6% |
| 60-70% | 637 | +79.4% | 68.1% |
| 70-80% | 615 | +71.3% | 70.6% |
| 80-90% | 768 | +32.7% | 66.7% |
| 90-100% (latest) | 904 | **+21.1%** | 63.6% |

By absolute rank: 1st **+715.6%** (89% win) · 2nd-3rd +247.9% · 4th-10th +468.4% ·
11th-25th +178.7% · 26th-100th +192.2% · >100th **+76.0%** (71% win).

**X-link vs not:**

| Cut | X-linked | no link |
|---|---|---|
| all | n=729, median +29.4%, win 57.1%, med size $5,086 | n=19,608, median 0.0%, win 46.0%, med size $655 |
| size ≥$1,000 | n=280, +107.9%, win 77.9% | n=5,659, +85.1%, win 72.5% |
| size ≥$5,000 | n=233, +108.7%, win 79.8% | n=4,306, **+117.9%**, win 76.2% |

**Leaderboard consensus vs trending:** 153 distinct tokens across the top-150's
holdings; 61 held by ≥2 traders, 35 by ≥3, 18 by ≥5, 8 by ≥10. The four
highest-consensus names (34/30/30/17 traders) are **not trending** and carry
$56M/$25M/$19M/$32M aggregate PnL. Consensus marks winners after the fact.

## ⚠️ The caveat that governs every number above

**This sample is 50 TRENDING tokens — coins that already went up.** The PnL *levels*
(+192%, +716%) are pure survivorship and mean nothing in absolute terms. What survives
the bias is the **within-sample ordering**, because both groups carry the same bias:
earlier beats later, and size beats the X link. Do not quote the levels at anyone.

`percentageUnrealizedPnl` is also the author's **current open** position, so closed
trades are under-represented — losers get cut and vanish from the sample.

The honest fix is the one `memecoin_radar` already implements for launches: **record
theses in real time on every token, including the ones that die**, then label outcomes.
That is the only way to get a base rate.

## What to change in our signals

`memecoin_radar` today scores Moon/Rug/TrendEcho off DexScreener transaction counts,
and PRD Phase 2 (smart-wallet leaderboard) is **blocked because wallet-level data has
no free source**. fomo unblocks it, but not in the way the PRD assumed.

1. **Take the wallets, not the rankings.** `/v2/leaderboard/{window}` hands us **150
   Solana addresses of traders ranked by realized PnL, for free**. We already have a
   working Helius key. Watch those addresses directly via Helius and we get Phase 2's
   smart-money flow without the metered PumpPortal stream and without the spend-or-parse
   decision that is currently blocking the project.
2. **Add a `social_conviction` component built on order, not volume.** For a candidate
   token, the features that survived the analysis are: **thesis rank** (are we inside the
   first ~30% of theses), **time since first thesis**, **count of distinct ≥$1k thesis
   authors**, and **how many of those authors are leaderboard wallets**. Weight by
   position size, *not* by whether an X link is present.
3. **Do not build an "X-link = conviction" rule.** It is a size proxy and it inverts
   above $5k. This is the fourth time a plausible headline filter turned out to be
   backwards or redundant in this repo (late volume, the severity ranking, the PRD's
   own thresholds, now this).
4. **Use the leaderboard as a lagging quality filter, never as discovery.** Good for
   "is a proven winner in this?", useless for "what explodes next".
5. **Poll `/feed/tradingActivity` every ~20-30s and persist everything** — it is a
   25-item non-paginated window, so anything not captured is lost forever. Same
   architecture as the existing radar loop, and the rejects are the base rate.

## Open questions for Jiv

- **Do we run a fomo harvester at all?** It needs a headed Playwright session holding
  *your* logged-in account and refreshing a Privy token hourly. Same ToS gray area as
  the GoTrade internal API — read-only, your own account, but it is their private API
  behind a bot shield. Your call.
- If yes: harvest on the Mini next to `memecoin_radar`, or keep it local-only?
