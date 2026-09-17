# Meme Coin Alpha Radar

Solana launch notifier and research dataset, built from `Meme_Coin_Alpha_Radar_Strategy_PRD.pdf`.
Streams every new pump.fun creation, scores it for upside and for danger separately,
compares it against a live trend set, and posts the survivors to Discord.

**It is a notifier, not a trader.** Nothing here places an order, holds a key, or signs a
transaction. PRD section 10 keeps execution out of V1 until the signal is validated against
recorded outcomes, and that is the right call given what the numbers below say.

## Run it

```bash
# Watch it work without posting anything
PYTHONPATH=. uv run python -m memecoin_radar.run --dry-run --duration 300

# Live, once a webhook is configured
PYTHONPATH=. uv run python -m memecoin_radar.run

# What has been collected so far
PYTHONPATH=. uv run python -m memecoin_radar.run --status

# Tests (network-free)
PYTHONPATH=. uv run --extra dev pytest memecoin_radar/tests -q
```

Configure the Discord webhook by environment variable or keychain:

```bash
export RADAR_DISCORD_WEBHOOK='https://discord.com/api/webhooks/...'
# or, persistently:
security add-generic-password -s radar-discord-webhook -a webhook -w '<webhook-url>'
```

Optional, unlocks the structural rug checks (mint/freeze authority, top-holder concentration):

```bash
security add-generic-password -s radar-helius -a api-key -w '<helius-key>'
```

## What the data layer actually allows

Verified live on 2026-09-17, not taken from the PRD:

| Need | Source | Reality |
|---|---|---|
| New launches | PumpPortal `subscribeNewToken` | **Free**, one websocket, ~24 launches/min (~34k/day) |
| Migrations | PumpPortal `subscribeMigration` | Free |
| Per-token trade flow | PumpPortal `subscribeTokenTrade` | **Not free.** Needs an API key plus a wallet funded with 0.02 SOL, metered 0.01 SOL per 10k messages |
| Market state | DexScreener REST | Free, no auth, 300 req/min, 30 addresses per request |
| Authorities, holders | Helius RPC | Free tier 1M credits / 10 RPS. Enough on demand, not for streaming |
| Narrative, image | IPFS via the launch `uri` | ~6.5s through Pinata; `ipfs.io` did not even resolve here |
| Delivery | Discord webhook | 5 req/5s per channel, ~30/min per webhook |

Three consequences shaped the whole build:

1. **The paid trade stream is the PRD's acceleration core**, so the free path reconstructs
   flow from DexScreener's `txns.m5` instead. That gives transaction counts, not unique
   wallets, so unique-buyer acceleration is reported as unmeasured rather than faked.
2. **Metadata is too slow to gate an alert.** It is fetched off the critical path and folded
   in at the next enrichment tick.
3. **The firehose is ~46x the channel capacity.** 34k launches/day against roughly 720
   deliverable alerts/day means the filter has to reject over 99% of launches, and the
   rate governor sheds quiet alerts before loud ones when saturated.

## How it scores

Three independent scores, never merged. A token can be exciting and dangerous at once, and
collapsing that into one number destroys the only thing worth knowing at the moment of the alert.

- **Moon** (PRD 3.1 weights): volume acceleration, buyer acceleration, liquidity, narrative,
  early-entry advantage.
- **Rug** (PRD 3.2): creator concentration, top-holder concentration, live mint/freeze
  authority, deployer history, liquidity withdrawal, creator dumping, wash-trade balance.
- **Trend Relation** (PRD 4.3): name/ticker similarity, narrative overlap, entity containment,
  social references, same-deployer, launch timing, early momentum.

### Coverage, and why it matters

Several PRD components cannot be measured in Phase 1: smart money needs the wallet
leaderboard, social and cross-platform need Phase 3, image similarity needs an embedding model.
A missing component is **excluded and the remaining weights renormalized**, never scored zero,
because scoring it zero is a silent penalty rather than a neutral one.

Each score therefore carries a `coverage` figure, shown on every alert. In Phase 1 the
measurable Moon weight sums to **0.50**, so a score means "of what could be measured, this is
how strong it looks". Coverage also gates the loud tiers: a thin score cannot shout.

This caught a real bug during the build. The coverage gates were initially set above the
achievable coverage, which made HOT and ULTRA impossible to fire. The radar would have run,
logged, recorded, and looked healthy while never escalating. `tests/test_reachability.py`
exists so that cannot happen again.

## Calibration: the PRD's thresholds do not survive contact with the distribution

Measured over 169 scored tokens at ~34 launches/min:

| PRD section 5 gate | Implied rate |
|---|---|
| `WATCH > 60` | ~256 alerts/hour |
| `HOT > 72` | ~188 alerts/hour |
| `ULTRA > 84` | ~60 alerts/hour |

Every PRD tier floods a channel that carries roughly 30/hour. The measured tail:

| Cutoff | Fires on | Rate |
|---|---|---|
| `moon > 84` | 4.14% | ~85/hour |
| `moon > 86` | 0.59% | **~12/hour** |
| `moon > 88` | none in sample | 0 |

Shipped defaults are therefore **86 / 89 / 93**, and they are **provisional**, not a result:
two samples hours apart moved p90 from 73.9 to 78.3. The scale itself is sound, since synthetic
exceptional launches score 90.7 and 94.2, so HOT and ULTRA are reachable rather than decorative.

Re-derive them from real data once the database covers enough hours:

```bash
PYTHONPATH=. uv run python -m memecoin_radar.calibrate
```

`calibrate` expresses thresholds as a target alerts-per-hour budget and refuses to emit a
cutoff the sample is too small to resolve.

## The evidence floor (learned from the first live run)

Renormalizing over available components is right in general and dangerous in one
specific case. The first live run posted this:

```
WATCH · $2LV4Ad     unnamed (2LV4Ad)
Moon 95/100 (5% evidence)     Rug 8/100 (37% evidence)
Age 18s   Market cap $3.0K   Liquidity unknown   0 buys / 0 sells
Why this fired: still ~$2,990 market cap
```

A 95 out of 100 on a token nobody had bought. Early-entry (weight 0.05) was the
only measurable component, and "market cap is small" is trivially true of every
newborn token, so renormalizing turned one trivial input into near-certainty.
Coverage gating existed but only guarded HOT and ULTRA, so WATCH published it.

Two floors now apply to every upside tier, WATCH included:

- `min_coverage_alert = 0.30`, so a score built from almost nothing cannot reach the channel.
- **Observed flow required.** An upside claim needs `volume_acceleration` or
  `unique_buyer_acceleration` to have been measured. Someone has to be buying.

RUG_WARNING is deliberately exempt: a structurally dangerous token is worth
flagging before anyone buys it.

Effect, measured live: 5 minutes, 81 launches, 2 alerts, both RUG_WARNING and
both genuine (creator holding 100% of supply, mint and freeze authority live,
top-10 at 80%). A moon-95 was present and correctly suppressed. 58 of 77 tokens
sat below the coverage floor, with median coverage 0.10, which is an honest
picture of how little is knowable about a launch that dies in its first minute.

The same class of bug bit twice more and is now pinned by tests:

- The coverage gates were first set *above* achievable Phase 1 coverage, making HOT and ULTRA impossible to fire.
- TREND_ECHO's activity floor read `buy_count`/`sol_volume`, which only the metered trade stream populates, so it could never fire on a free deployment. It now reads the DexScreener snapshot flow.

A tier that cannot fire looks exactly like a quiet market. `tests/test_reachability.py`
and `tests/test_evidence_floor.py` exist so it stays impossible to ship that silently.

## Disk retention

Unmanaged the dataset grows **~150-280 MB/day** (4.5-8 GB/month) at observed
launch rates. `retention.py` thins cold, never-alerted tokens: it drops the raw
wire blob, thins snapshots to first and last, and deletes per-age score rows.
Measured on real data: **56% saved**, and more once the full 8-snapshot schedule
has run.

It never deletes a token row. The base rate in `backtest evaluate` is computed
over every considered token, so dropping the boring ones would quietly inflate
every precision figure the radar reports. Alerted tokens and anything that ran
keep full detail, because those are the rows a post-mortem needs.

It runs automatically every 6 hours inside `run.py`, or by hand:

```bash
PYTHONPATH=. uv run python -m memecoin_radar.retention --dry-run
```

## The dataset is the actual asset

Every launch is recorded, not just the alerted ones. Without the rejects there is no base rate,
and without a base rate a threshold can only be asserted, never validated. This is PRD section 8
and it is the part that turns a notifier into a research system.

```bash
PYTHONPATH=. uv run python -m memecoin_radar.backtest refresh    # re-poll for 6h/24h/7d windows
PYTHONPATH=. uv run python -m memecoin_radar.backtest label      # label outcomes
PYTHONPATH=. uv run python -m memecoin_radar.backtest evaluate   # precision vs base rate
```

`evaluate` reports every precision figure next to the base rate it has to beat, and refuses to
draw a conclusion from fewer than 30 alerts in a tier. A tier that alerts on 40% of launches and
catches 40% of winners has found nothing.

## Deliberate deviations from the PRD

| PRD says | This does | Why |
|---|---|---|
| Postgres / TimescaleDB | SQLite (WAL) | Single-writer, append-mostly. Postgres adds a service and no capability. The schema ports with a dump. |
| Telegram first, Discord later | Discord only | That is what was asked for. |
| Trend set from trending feeds | Trend set from our own stream | DexScreener boosts are **paid promotion**, and PRD section 10 requires paid placement to be shown as paid, not treated as organic traction. Recording every launch means the movers are already known locally. |
| Fixed scoring weights | Weights renormalized over available components | Otherwise Phase 1 caps Moon at 60 and the PRD's own ULTRA gate is unreachable. |
| `subscribeTokenTrade` for flow | DexScreener `txns.m5` | The trade stream is metered and needs a funded wallet. |
| Section 5 absolute thresholds | Rate-targeted thresholds | Measured above: the stated gates cost ~218 alerts/hour. |

## Not built yet (PRD phases 2 to 4)

- **Smart-wallet leaderboard** (Phase 2). The `wallets` table and the scoring hook exist, the
  table is empty, and smart money reports as unmeasured. Populating it raises Moon coverage
  from 0.50 to 0.70.
- **Social ingestion** (Phase 3). No X, Telegram, or Reddit. A social handle in token metadata
  proves a creator typed a URL, not that anyone is discussing the contract, and treating it as
  traction is exactly the bot-inflated signal PRD 3.2 warns about.
- **Image/logo similarity** (Phase 4). Needs a CLIP-style embedding model.
- **Funding-cluster wallet graph**. Same-deployer is provable today; "related via a funding
  cluster" is not, so a different deployer scores as unknown rather than unrelated.

## Honest caveat

This hunts sub-minute microcaps in an adversarial market against professional bots, and the
base rate for a random launch is dismal. The value of this build is the recorded dataset and
the separation of danger from upside, not a claim that the alerts are profitable. Nothing here
is validated until `backtest evaluate` says so on a real sample.
