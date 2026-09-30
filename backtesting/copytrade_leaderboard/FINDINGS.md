# Copy-trading the fomo leaderboard: no measurable edge, and underpowered

**Verdict: NOT PROVEN, leaning negative. Do not trade this.**
Run: `uv run python backtesting/copytrade_leaderboard/study.py <radar.sqlite3>`

## The strategy tested

Jiv, 2026-09-17: *"buy when someone influential buys, sell when they sell, or
sell after a 50% gain."*

The exit half was already answered before this study. `../memecoin_exit_policy`
tested +50% TP against ten alternatives over 5,610 launches: every policy lost,
all eleven landed within ~$100 of each other, and the median trade WAS the
round-trip cost. Its conclusion was that the exit is not the lever, the entry
is. So this study tests the **entry**.

## Where the signal comes from, and the trap in it

`fomo_leaderboard_holdings` snapshots the top-150 traders by realized PnL, with
each trader's **top three** positions. Diffing captures reconstructs their
trades for free.

The hazard is that `api.leaderboard`'s own docstring warns the list is LAGGING:
a position enters someone's top three partly **because it appreciated**, since
value = amount x price. Treating "a token appeared in their holdings" as a buy
would select winners after they had won, which is the bug this repo shipped
twice already.

What defuses it: the table stores `human_amount` separately from `price`, and
token **quantity** only changes when the trader actually transacts. So only
amount changes count as events, and a token's first sighting is discarded
because with no prior row a fresh buy is indistinguishable from appreciation.

## Result

Two runs, the second after the collection fix below went live.

**Run 1** (10 rounds, 4h01m, 09:59-14:00 UTC): 30 buys, 39 sells, 22 completed.
**Run 2** (15 rounds, 4h39m, 09:59-14:38 UTC): 35 buys, 50 sells, 26 completed.

Gross, before costs. **The control shares the survivorship bias, so only the GAP
is evidence:**

| arm | n | median | mean | win% | best |
|---|---|---|---|---|---|
| COPY buy, exit when they sell | 26 | +0.82% | +0.19% | 57.7% | +30.9% |
| COPY buy, +50% TP | 26 | +0.33% | +0.24% | 53.8% | +30.9% |
| COPY buy, hold to last snapshot | 26 | +0.33% | +0.24% | 53.8% | +30.9% |
| **CONTROL: they held, no trade** | **6,255** | **+2.09%** | **+5.25%** | **60.9%** |

Run 1 for comparison: copy-and-hold +0.30% median / 50.0% win against a control
of +0.31% median / 52.0% win.

**The buy event carries no detectable information, and run 2 has it losing to
the control on every measure.** Copying the trade did worse than simply holding
whatever those traders already held. In run 1 the two arms were
indistinguishable; adding four events flipped the sign of the gap, which is
itself the tell that 22-26 observations decide nothing.

The +50% TP arm is identical to hold-to-last because **no trade ever reached
+50%** inside the window. Best outcome in 26 trades was +30.9%.

One caveat specific to run 2: the amount-change dedupe means flat observations
are now written on a 15-minute heartbeat rather than every poll, so the control
group's composition changed between runs. Its absolute level is not comparable
across runs; only each run's internal arm-vs-control gap is.

## Costs kill it at every size

Net of the real round trip (`fomo_radar.fill`), liquidity fixed at $50k:

| position | median | mean | win% | fixed fee as % of position |
|---|---|---|---|---|
| $1 | -62.91% | -62.38% | 0.0% | 80.0% |
| $10 | -10.24% | -8.95% | 18.2% | 8.0% |
| $50 | -3.83% | -2.44% | 18.2% | 1.6% |
| $100 | **-3.34%** | -1.95% | 18.2% | 0.8% |
| $500 | -5.59% | -4.23% | 18.2% | 0.2% |
| $2,000 | -15.12% | -13.90% | 13.6% | 0.0% |

**$1 trades cannot test anything.** The priority fee plus tip is 0.002 SOL per
transaction, about $0.40 a leg and $0.80 a round trip, so a $1 position pays 80%
in fixed cost before impact and the coin must roughly double to break even. The
cost curve is U-shaped: fixed fees dominate below ~$50, price impact dominates
above ~$500, and the floor near $100 still loses. A gross median of +0.3% has
nothing to pay a round trip with.

## Why this is not yet a verdict

- **n=26 completed trades.** Underpowered. It does not show an edge; it also
  cannot prove one is absent. The arm-vs-control gap changed SIGN between run 1
  and run 2 on four extra events, which is what that sample size buys you.
- **4h39m of data, one session.** No regime coverage at all.
- **Horizon truncated** at the last snapshot, which is why nothing hit +50%.
- **We see only each trader's top 3 positions**, so most of their buys are
  invisible, and the ones we see are biased toward large positions.
- **Detection lag was 4-100 minutes (median 13)** purely because the process
  kept restarting. See below: production was far worse.

## The thing that actually blocked this, now fixed

`leaderboard_interval_s` was **6 hours**. The dense snapshots analysed above
were an accident of restarts. In steady state a copy-trade signal would have
been detected **up to 6 hours late**, which is fatal to a strategy whose whole
premise is speed, and it also meant the tape accumulated about one usable event
per poll.

Changed to **60s** (2026-09-17). Cost is 3 API calls a minute, since holdings
come embedded in the leaderboard response, against the ~60-in-a-burst that
tripped a real Cloudflare 429. Naively that would write **264 MB/day** (1,320
rows a round at 139 bytes/row, measured), so `store.record_leaderboard` now
writes a holdings row only when the **quantity** changed, plus a 15-minute
heartbeat to keep a coarse price series.

Verified live after deploy: polls now land **once a minute** (previously gaps of
25-100 minutes), and steady-state writes are **17-25 rows a minute against
~435 skipped as unchanged per window**, versus 1,319-1,327 rows per capture
before. That is a ~98% reduction, or about **23 MB/day** including the heartbeat
sweep. No `fomo_*` table has a retention policy yet, so this needs a prune
before it runs for months.

At ~9 genuine buys an hour that is roughly **200 events a day**, so a week of
collection gives ~1,400 events: enough to settle this properly instead of
guessing from 26.

**Unverified assumption:** whether fomo's holdings payload actually updates
faster than a few minutes server-side. If it is cached, polling at 60s buys
sample size but not speed. Re-run this study after a day of collection and check
whether observed detection lags actually fall to ~1 minute.

## What would change the answer

1. **Re-run on a week of 60s data** (~1,400 events). This is the only honest
   next step.
2. **Condition on the buy, not just its existence.** Size of the amount
   increase, the trader's own PnL rank, whether several traders buy the same
   token within one window. n=26 cannot support any of these without
   overfitting.
3. **Test the sell side separately.** 50 genuine sells were observed and never
   evaluated as a short or as an exit signal on its own merits.
4. **Add a prune for `fomo_leaderboard_holdings`** before this collects for
   months at 23 MB/day.
