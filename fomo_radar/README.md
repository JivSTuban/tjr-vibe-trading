# fomo_radar

Harvests fomo.family's social layer and turns it into one signal: **who wrote a
money-backed thesis on a token, and how early.**

Notifier with optional execution-proposal staging. Real order submission is
disabled; no signing or keys beyond the existing read-only session.

Full research writeup, including every number quoted here:
[`research/fomo/FINDINGS.md`](../research/fomo/FINDINGS.md).

## Why this exists

`memecoin_radar` scores launches from DexScreener transaction counts. PRD Phase 2
(the smart-wallet leaderboard) was blocked because wallet-level data had no free
source. fomo's leaderboard hands over **150 Solana addresses ranked by realized
PnL**, free, which unblocks it — and its thesis feed adds something the radar has
no equivalent of: a written, timestamped, size-verified conviction record.

## What the signal is

A **thesis** on fomo is a comment welded to a real executed trade. The API
returns the author's live position alongside it, so conviction is money-backed by
construction and the size is public.

The signal looks for a **conviction cluster**: one or more authors who committed
EARLY to a token and have kept posting theses on it since, on a token that has a
live market. Measured over 20,337 theses, re-cut as **one row per (author,
token) pair** (see `conviction.py` and `research/fomo/FINDINGS.md`):

| gate (all knowable at post time) | n | median | win | p25 |
|---|---|---|---|---|
| baseline (all pairs) | 2,361 | +10.9% | 57.1% | −23.7% |
| conviction ≥3 theses + early half | 622 | +52.6% | 67.4% | −16.0% |
| **conviction ≥6 + early half** | 299 | **+68.3%** | **71.6%** | −9.0% |
| conviction ≥6 + early + leaderboard | 45 | +57.6% | **75.6%** | **−1.9%** |

The strongest cell is 12+ theses whose first landed in the token's early
deciles: **+99% median, 78% win**.

- **Conviction cadence is a GATE, not a dial.** Past the floor, thesis count
  rank-correlates **rho=−0.002** with the author's own PnL. Only the extreme
  tail (30+) gets a step.
- **Earliness is the differentiator**, and it is *relative to the token's own
  timeline*, not to when we started watching — which is what makes v2 able to
  fire at all. rho=−0.189; earliest 10% medians +166.6% (85.0% win).
- **A live market is a hard gate.** No liquidity, no 1h volume, no recent
  trades, no alert — whatever the social score says. Absent market data fails
  the gate rather than being scored as zero.
- **The leaderboard lifts, never gates.** On-board authors median +53.6% / 73.0%
  win vs +9.4% / 56.2%. But starcatcher444 ran the ALLINU thesis this design is
  built from while *absent* from the 24h top-150, because that board ranks
  realized PnL and a conviction holder has not sold.
- **Not modelled: the dev flag.** 7 dev theses in 20,337, median −40.1%, zero
  winners.
- **Tiers rank EVIDENCE, not expected return.** Replaying all 50 tokens, the
  gate separates cleanly (+71.6% alerted vs −16.2% silent) but within the
  alerted set the score does not order the outcome (rho=−0.146, n=29). A higher
  tier means more independent conviction behind the call, nothing more.

### What v1 got wrong

v1 gated on *absolute* thesis rank (inside a token's first ~10 theses ever).
Real and monotonic, but unreachable: we join a timeline at rank ~500. It watched
ALLINU take positions of $328k/$206k/$202k at +742%/+606%/+593% over 17 hours
and alerted **nothing** — 4,177 items, 13 tokens, 0 alerts. It also discounted
repeat posting by one handle as "not confirmation", which is backwards, and had
no concept of whether the token was tradeable.

> ⚠️ The research sample is 50 **trending** tokens, so those PnL *levels* are
> survivorship-biased and meaningless in absolute terms — the baseline alone is
> +10.9% median / 57% win. What survives is the *ordering*, because both sides of
> every comparison share the bias. Reverse causality is also live: people post
> more when winning, so cadence is partly an effect of the run. That is why this
> harvester records every candidate including the ones that die — the rejects are
> the base rate. **Zero outcomes are labelled yet.**

## No LLM, on purpose

Every scored feature is structural. The one content feature that was tested (the
X link) turned out to be a size proxy that inverts. Raw thesis text **is** stored
so the question can be answered later against labelled outcomes, but nothing
scores off it today.

## Access constraints (verified, not assumed)

- Auth is a Privy `Bearer` JWT, **1-hour life**. The refresh token is
  **reusable and not rotated**, so one stored secret is enough and there is no
  browser login state to maintain or migrate.
- **Plain HTTP clients are blocked.** With one valid token held constant:
  `curl` → 430, `node fetch` → 430, headless Chromium → request never leaves,
  **headed Chromium → 200**. The edge fingerprints the client, not the
  credentials. Both 430 and 431 return `{"error":"unauthorized"}`, which makes a
  fingerprint rejection look exactly like a bad token.
- Therefore the harvester keeps a **headed** Chromium open and issues every
  request from inside a `fomo.family` page. `headless=True` is accepted by the
  config and will not work.
- `/feed/tradingActivity` is a **25-item window with no pagination** —
  `limit`, `offset`, `page`, `cursor` and `beforeTime` all return the same
  newest 25. Anything that scrolls off between polls is gone. Poll and persist.
- `/v2/leaderboard/{window}` supports **24h, 7d, 30d only**. `all`, `alltime`,
  `all-time`, `lifetime`, `allTime`, `total` all 404.

## Run it

```bash
# never posts; writes to a scratch DB
PYTHONPATH=. RADAR_DB_PATH=/tmp/fomo.sqlite3 \
  uv run python -m fomo_radar.run --dry-run --duration 120

# live
PYTHONPATH=. uv run python -m fomo_radar.run

# label alerted tokens into fomo_outcomes (re-runnable; --report writes nothing)
PYTHONPATH=. uv run python -m fomo_radar.label
PYTHONPATH=. uv run python -m fomo_radar.label --report

# tests + lint (network-free)
PYTHONPATH=. uv run --extra dev pytest fomo_radar/tests -q
uv run --extra dev ruff check fomo_radar --select F,E9
```

### Credentials

| Secret | Env | Keychain |
|---|---|---|
| Privy refresh token | `FOMO_REFRESH_TOKEN` | `fomo-privy-refresh` / `refresh-token` |
| Discord webhook | `FOMO_DISCORD_WEBHOOK` (falls back to `RADAR_DISCORD_WEBHOOK`) | `radar-discord-webhook` / `webhook` |
| Database | `RADAR_DB_PATH` | — (defaults to the radar's DB) |

To refresh a dead token: sign in to fomo.family in a browser, read
`localStorage['privy:refresh_token']`, and re-store it. The daemon **stops
loudly** on `AuthError` rather than running blind.

## Storage

Shares `memecoin_radar`'s SQLite file so the join is local. New tables are
prefixed `fomo_`; the shared `wallets` table is also populated from the
leaderboard, which is what PRD Phase 2 reads.

| Table | Holds |
|---|---|
| `fomo_feed_items` | every feed item, theses **and** plain swaps (the base rate) |
| `fomo_tokens` | per-token ordering facts the signal is computed from |
| `fomo_leaderboard` | 150 traders × 3 windows, with wallet addresses |
| `fomo_leaderboard_holdings` | what they held at capture time |
| `fomo_alerts` | what we fired and why |
| `fomo_price_snapshots` | forward prices for alerted tokens, aged from the alert |
| `fomo_outcomes` | one labelled outcome per alerted token |
| `wallets` | shared with the radar — the smart-money address set |

## ENTER NOW: the only thing that gets notified

A tier says a token is **interesting**. A notification claims **money should
move right now**, which is a strictly higher bar, and conflating the two is how
the radar ended up posting trophies. `entry_gate` in `signal.py` decides the
second question, and only an ENTER NOW is delivered. Three conditions, all
required, on top of every hard gate `evaluate` already applied:

| Gate | Default | Why |
|---|---|---|
| `entry_max_rank` | 20 | The measured edge decays hard past it: rank 0 median +715.6%, 1-4 +151.2%, 5-19 +122.9%, then 20-99 collapses to +50.3%. |
| `entry_max_thesis_age_s` | 1800 (30m) | **The gate that did not exist before.** Measured over the 14 recorded alerts, 11 fired on a thesis that was hours old (median ~9h, worst 3.5 days). An alert about a 9-hour-old thesis is a report. |
| `entry_max_round_trip_pct` | 0.06 at $500 | From `fill.py`. A pool where getting in and out costs more than 6% is not tradeable at this size, whatever the signal says. |

Refused alerts are **recorded, not dropped**, with `fomo_alerts.suppressed_reason`
set and forward prices still tracked. They are the control group: without them
there is no way to discover the gate is throwing away winners, and an
unfalsifiable gate is how this project repeatedly shipped a signal that could not
fire. `delivered = 0` with a NULL `suppressed_reason` still means delivery
broke, which is a different thing and stays visible.

Replaying the gate over the 14 recorded alerts, **none** would have been
notified: CATE and AGI on rank (502 and 492 theses deep, the trophies), eleven on
staleness, and GTA6 only because no liquidity was ever recorded for it. Most of
the staleness comes from one backlog dry-run sweep rather than steady-state
operation, so this is **not** proof the gate is unreachable; it is also not proof
it fires. The suppression log is how that gets settled, and `discovery.py` now
reports how many candidates it skipped as stale so a quiet radar can explain
itself.

**Settled 2026-09-17: the gate does fire, once the input reaches it.** The first
live run refused everything for a reason nothing recorded — 22 of 22 socially
early candidates were dropped as stale *before* the gate, so the suppression log
stayed empty and read as "nothing was refused". The cause was `liquid_launches`
taking the top 40 candidates `ORDER BY liq DESC`, and liquidity is
ANTI-correlated with being socially early: 164 mints cleared the $15k floor,
only the 40 fattest were ever asked about, and their newest theses were 6-135
HOURS old. Three of the four mints that actually hit the fresh-and-early window
ranked 41st, 79th and 112nd and were never asked — two of them sitting at thesis
rank 0. Removing the truncation, retiring mints already past rank 20 (15 of the
40 checked, so 37.5% of every sweep's budget bought a known answer), and
rotating strictly by least-recently-checked took the candidate pool from 40
tokens with a $410k liquidity floor to 144 with a $15k floor. Within 13 minutes
two candidates reached the gate, one at **thesis #1**, refused on execution cost
(7.5% round trip against a 6% cap). That is the gate working, not starving.

## Paper fills: what a bot would actually have got

`fill.py` + `paper.py` answer the only question that matters before automating
buys: **does the signal survive its own execution costs?** Every return figure
elsewhere in this project is mid-price to mid-price. No position opens there.

`fill.py` is a constant-product AMM cost model. The key fact is that
DexScreener's `liquidity_usd` counts **both** sides of the pool, so the quote
reserve is half of it, and impact scales with trade size against that half. A
flat bps constant of the sort a CEX backtester uses is off by orders of
magnitude here. Measured round-trip drag at a $500 position:

| Pool depth | Round trip cost |
|---|---|
| $5k | 29.8% |
| **$15k** (the signal's own liquidity floor) | **13.5%** |
| $30k | 8.1% |
| $100k | 4.0% |
| $500k | 2.5% |

That is the hurdle before the strategy has earned a cent.

`paper.py` walks each alert's forward price series with a causal exit rule
(stop / take-profit / trailing / time stop), pays the cost model on both sides,
and reports gross next to net, plus how many trades **flip from green to red on
costs alone**. It also sweeps entry latency, which answers "is sub-minute
execution worth building" with a number rather than an opinion.

```bash
python -m fomo_radar.paper hurdle --size 500    # cost of a round trip by pool depth
python -m fomo_radar.paper report --size 500    # full run over delivered alerts
python -m fomo_radar.paper sizes                # net result by position size
python -m fomo_radar.paper trades               # per-trade detail
```

Two biases are structural and are reported rather than hidden. The snapshot
ladder has seven points, so between them the price is unobserved: **stops are
flattered** (an adverse wick that recovers is invisible) and **targets are
penalised** (a favourable spike that retraces is too). Every trade carries
`max_unobserved_gap_s`; a result whose exits all land across a multi-hour blind
gap is not a result. The fix is a denser ladder, not a cleverer exit rule.

## Expected volume

Replaying all 50 harvested tokens through v2, **29 alert** — 14 CONVICTION,
11 HOT, 4 WATCH. The 21 silent ones are mostly "no conviction author" (200-300
authors posted, none committed early and stayed), with a few blocked on
liquidity.

Live, the harvester sees on the order of 13 new tokens a day in its feed window,
and each token can alert at most once per tier, so expect a handful of alerts a
day rather than a silent channel. That is a deliberate change from v1, which
alerted **zero** times in 17 hours while real money was piling into a token it
was watching.

`fomo_alerts` plus the `delivered` flag is still how you tell "nothing
qualified" from "delivery broke", and a conviction cluster blocked by a hard gate
is logged with its reason rather than dropped silently.

## Known gaps

- **Still nothing validated, and the first 12 outcomes were mostly the WRONG
  INSTRUMENT.** `fomo_outcomes` has rows, but **8 of the first 12 were tokenised
  real-world assets**, not meme coins: MSFTX, GLDX, CRCLX, SPYX, GOOGLX, SPCXx,
  EURC, tOpenAI. Those track an underlying, so a "+0.5% median 1h return"
  measured across them describes an equity tracker and says nothing about this
  radar's thesis. fomo lists them beside meme coins and they had quietly become
  the majority of what got alerted on. `max_price_usd` now rejects them (every
  genuine meme coin observed was <= $0.47, every wrapped asset >= $1.14).
  Re-label after a day of clean collection before quoting any number.
- **An alert with no market cap could never be labelled.** `label_one` measures
  returns off `market_cap_usd`, so a zero there makes the outcome unknowable
  forever. The delivered $AMD alert (2026-09-17 14:52) recorded mcap $0 against
  $66,212 of liquidity. `require_known_market_cap` now blocks it. This is NOT a
  cap floor: a low cap is the point.
- **There is no floor on conviction capital, and it shows.** That same $AMD
  alert fired on **$9.20** of total conviction across five authors holding $5,
  $4, $0, $0 and $0. Nothing in `SignalConfig` gates the cluster's total size,
  only individual `min_thesis_usd`. Deliberately NOT fixed by guessing a
  number: the 27 recorded alerts range from $0.00 to $939M of conviction with no
  clean separation, and inventing a threshold off 27 rows is how this project
  shipped its withdrawn v2. It needs labelled outcomes first.
- **69% of tradeable price series are pair-flip corrupt** and cannot be
  repaired. `pick_primary` was fixed at the source on 2026-09-17, but rows
  written before that may mix pairs. Every consumer must screen with
  `memecoin_radar.backtest.is_pair_flip`; `label.py` does, and it drops ~6 of
  every 18 alerted tokens for this reason. The first labeller run, written
  before the screen existed, reported a fabricated **+18,605%** for NVDAX on a
  price that moved 0.4%.
- **The discovery rotation is the binding constraint on the freshness rule.**
  `candidates / MAX_CHECKS_PER_SWEEP * DISCOVERY_TICK_S` must stay under
  `entry_max_thesis_age_s` or a thesis can go stale before its mint is polled.
  At 144 candidates, 12 checks a sweep and a 120s tick that is 24 minutes
  against a 30-minute window. If the candidate count grows, this breaks
  silently — the symptom is `dropped STALE pre-gate` climbing back to 100%.
- **The paper-fill model is calibrated for graduated AMM pairs.** Pre-graduation
  pump.fun bonding curves use virtual reserves, so the 50/50 split behind
  `quote_share` is a guess on the curve. `priority_fee_sol` and `fail_rate` are
  documented guesses too; calibrate them against real fills before trusting a
  net figure to two decimal places.
- **No entry mark exists on alerts fired before the age-0 snapshot shipped.**
  The tracking ladder starts at +5m, so older alerts are paper-traded from a
  price five minutes stale. `paper.py` reports `entry_age_actual_s` so this is
  visible rather than assumed away.
- **Tiers are not a return ranking.** The gate separates (+71.6% alerted vs
  −16.2% silent on the outcome proxy) but the score does not order outcomes
  within the alerted set (rho=−0.146, n=29). Do not read CONVICTION as
  "this one pays more".
- **Reverse causality is unresolved.** Cadence is knowable at post time, but
  people post more when a position is already winning. The early-first-thesis
  requirement constrains this without eliminating it; only labelled forward
  outcomes settle it.
- Solana is the only chain the radar cares about, but the feed is multi-chain and
  everything is recorded. Filter downstream.

## Execution staging

See [EXECUTION.md](EXECUTION.md) for the opt-in ENTER NOW proposal journal,
20% stop / 10% target lifecycle, verified onlinejobs-browser MCP connection,
and isolated Playwright tests. Real-money submission remains unavailable.
