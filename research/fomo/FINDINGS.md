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

---

# Addendum, 2026-09-17 evening — the conviction formula (v2)

Written after Jiv reported the live radars were surfacing coins nobody was
buying, and asked for the leaderboard's own method, citing starcatcher444's
ALLINU thesis (a dozen posts over five days, accumulating through drawdown,
"consider my supply locked").

## What was broken

`fomo_radar` v1 gated on **thesis earliness**: a token had to be inside its
first ~10 theses ever. That effect is real and monotonic (above), but it is
**operationally unreachable** — we join a token's social timeline at rank ~500.

Proof, from the live database: between 01:13 and 10:38 UTC the harvester
recorded ALLINU theses carrying positions of **$328k, $206k, $202k and $111k at
+742%, +606%, +593% and +1483%** on a token with a deep market. It fired
**zero alerts**, because every one of those theses was past rank 10.
4,177 items, 13 tokens, 0 alerts. This is instance **7** of the
unreachable-signal bug class.

Separately, `memecoin_radar` was the source of the untradeable coins: across its
44 upside alerts, **peak liquidity medianed $3,257** (p75 $3,419) — the
bonding-curve floor. All 44 passed the flow-evidence check, median peak buy
count 82. Buys are not a market.

## The formula, measured

Re-cut the same 20,337-thesis harvest with **one row per (author, token) pair**
instead of per thesis. That de-duplication is essential: fomo attaches the
author's *current* position and PnL to every one of their historical theses, so
a handle with 34 theses contributed 34 identical outcomes and inflated n by
~3.4x. The per-thesis version of the headline read +209.9%; per pair it is
+63.4%.

Restricted to features knowable when a thesis is posted:

| gate | n | median | win | p25 | >+100% |
|---|---|---|---|---|---|
| baseline (all pairs) | 2,361 | +10.9% | 57.1% | −23.7% | 28.0% |
| conviction ≥3 theses | 797 | +30.8% | 63.0% | −18.5% | 35.6% |
| conviction ≥3 + early half | 622 | +52.6% | 67.4% | −16.0% | 41.0% |
| **conviction ≥6 + early half** | 299 | **+68.3%** | **71.6%** | −9.0% | 45.2% |
| conviction ≥12 + early half | 112 | +79.4% | 73.2% | −8.4% | 46.4% |
| conviction ≥6 + early + leaderboard | 45 | +57.6% | **75.6%** | **−1.9%** | 40.0% |

Cross-tabbed, the strongest cell is **12+ theses whose first landed in the
token's early deciles: +99% median, 78% win, n=91**. That is the starcatcher
pattern, and it is the thing to copy.

## Four things that overturn earlier choices

1. **Repeat posting by one handle is the signal, not noise.** v1 explicitly
   discounted it ("one handle three times in four minutes is not
   confirmation"). Per pair: 1 thesis 53.5% win → 12+ 67.2%.
2. **Cadence is a GATE, not a dial.** Within the already-qualified population,
   thesis count rank-correlates **rho=−0.002** with the author's own PnL. Past
   the floor, posting more is not further evidence. Earliness is the real
   differentiator (**rho=−0.189**; earliest 10% +166.6%/85.0% win vs 30–50%
   +68.3%/75.5%).
3. **Crowding is NOT lagging here** — checked specifically, because that is what
   sank the leaderboard-holdings idea. Cluster size rank-correlates **+0.283**
   with the author's own PnL, capital **+0.281**, leaderboard count **+0.225**.
   An apparent tier inversion in the first replay was n=2 and n=4 buckets.
4. **"Developer backed" has no support.** Seven dev theses exist in 20,337
   (three author-token pairs), median **−40.1%**, zero winners. Not modelled.
   Jiv asked for it; the data cannot carry it.

**The leaderboard lifts, it must never gate.** On-leaderboard authors median
+53.6% / 73.0% win vs +9.4% / 56.2% off it — a real effect. But
**starcatcher444 was not in the 24h top-150** while running the ALLINU thesis,
because that board ranks *realized* PnL and a conviction holder has not sold.
Requiring leaderboard membership would have missed the archetype that prompted
the work.

## Replay of the v2 gate over all 50 harvested tokens

29 of 50 alert (14 CONVICTION / 11 HOT / 4 WATCH). On the outcome proxy:

* **alerted tokens: +71.6% median · silent tokens: −16.2%** — the gate separates.
* **Within the alerted set the score does NOT rank outcome**: rho=−0.146, and
  the top half by score medianed +51% against +121% for the bottom half.

So tiers rank **evidence, not expected return**, and the code and the alert
footer both say so. A higher tier means more independent conviction behind the
call; it is not a claim that it pays more. Settling that needs the forward log
with labelled outcomes. n=29, so this is weak evidence rather than proof of
inversion — but nowhere near enough to sell a tier as a return ranking.

## Still not validated

**Zero labelled outcomes.** Every number here is measured on a
survivorship-biased sample (trending tokens only), where the baseline itself is
+10.9% median / 57% win — a level no random token pool reaches. And reverse
causality is live: people post more when a position is winning, so cadence is
partly an *effect* of the run. Requiring the author's first thesis to be early
constrains that; it does not remove it.
