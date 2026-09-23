# Exit policy on memecoin launches: the exit is not the lever

Run 2026-09-17 against `market_snapshots` (5,610 pump.fun launches, 8-point
ladder to one hour) with the `fomo_radar.fill` AMM cost model at a $100 position.

## TL;DR

1. **A data bug had to be fixed before any number meant anything.** `pick_primary`
   ranked DexScreener pairs by 5-minute volume, so the selected pair flipped
   between polls and the recorded market cap jumped by orders of magnitude with
   no market move. It produced a fake +$485,868 "trade" on a $100 position.
2. **Every exit rule tested loses money**, from -$1,958 to +$29 total depending
   on how aggressively corrupt series are excluded.
3. **The choice of exit rule barely matters.** All eleven policies land within
   ~$100 of each other over 36 trades, while the average trade loses $8-10. You
   cannot fix a losing entry with a better exit.
4. **The median trade is the transaction cost and nothing else.** Median result
   is -2.4% to -3.4%; the modelled round trip at $100 is 4.93% in a $15k pool and
   2.81% in a $100k pool. The median launch does not move enough in an hour to
   pay the spread.

## The pair-flip bug

`liquidity_usd / market_cap_usd` is the share of a token sitting in its pool. For
one AMM pair it drifts slowly. Observed within single one-hour windows:

| mint | liq/mcap values seen | reading |
|---|---|---|
| `FgXkpy...` | 0.28, 0.015, 1.03 | three different pairs |
| `A7bdiY...` | 0.0156, 62.56 | a pool worth 62x the whole token |
| `pumpCm...` | 0.0013, 0.0117, 0.0000 | one row claims a $9.1 **trillion** mcap |
| `mzGEKC...` | alternates $41k ↔ $145M mcap | flips on consecutive polls |

Fixed in `memecoin_radar.sources.dexscreener.pick_primary` by ranking on
**liquidity** (a stock, moves smoothly) with volume only as a tie-break.
Regression tests in `memecoin_radar/tests/test_sources.py`.

The fix cannot repair rows already written, so `study.py` drops series whose
liq/mcap ratio is unstable. **An earlier price-based filter was not good enough**:
it caught round-trip flips and missed every one-way switch, letting through a
fake trade worth 80% of the reported total. Price alone cannot tell a real 100x
from a pair change; the ratio can.

## Results, $100 per trade, clean series only (n=36)

| policy | total P&L | mean | median | win% |
|---|---|---|---|---|
| +50% TP, no stop | -289 | -8.02 | -2.44 | 22% |
| +50% TP, -50% stop | -372 | -10.34 | -2.49 | 19% |
| +30% TP, -30% stop | -387 | -10.76 | -2.49 | 19% |
| +100% / +200% / +500% TP | -372 | -10.34 | -2.49 | 19-24% |
| no TP, -50% stop | -372 | -10.34 | -2.49 | 19% |
| trail 30% / 50% off peak | -325 / -372 | -9.04 / -10.34 | -2.49 | 19% |
| hold to end of tracking | -289 | -8.02 | -2.44 | 22% |
| sell 50% at +50%, trail rest | -372 | -10.33 | -2.49 | 19% |

Filter sensitivity, +50% TP: factor 2 → +$29 (n=26) · 3 → -$289 (n=36) ·
5 → -$812 (n=59) · 10 → -$1,484 (n=87) · 50 → -$1,958 (n=133) · none →
+$590,721 (one corrupt trade).

## A prediction that did NOT survive

Going in, the expectation was that a fixed +50% take-profit would underperform
badly by truncating the fat tail that carries all the expectancy on a
positively-skewed asset.

**The data did not show that.** +50% TP was the best or tied-best policy at every
filter setting. In the clean one-hour sample the best trade was +$89 on $100;
there were no 10x winners to cap. The fat-tail argument may still hold over days,
but **this dataset cannot test it** because tracking stops at one hour. Do not
cite the theory as though it were measured here.

## What this does NOT say

The population is ALL launches, not signal-selected ones, so the entry has no
edge by construction and the result is close to "random entry pays the spread".
It says nothing about whether the ENTER NOW gate has an edge. That remains
untested: `fomo_outcomes` is still empty.

## Copy trading

Already answered by `research/fomo/FINDINGS.md` and not re-run here: leaderboard
membership carries rho=-0.057 against outcome, turning negative once earliness is
controlled for, and 200k+ follower authors median **-8.0%** with a 45% win rate.
The leaderboard ranks REALIZED PnL, so copying it is buying trophies. Copying
specific wallets *at the moment they enter* is a different and untested idea.

## Next

Stop tuning exits. The lever is entry selection and position size, in that order.
Size is not cosmetic: the round trip is 4.93% at $100 into a $15k pool, and the
ENTER NOW gate's 6% budget is about one round trip.
