# fomo_radar

Harvests fomo.family's social layer and turns it into one signal: **who wrote a
money-backed thesis on a token, and how early.**

Notifier only. No execution path, no signing, no keys beyond a read-only session.

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
| `wallets` | shared with the radar — the smart-money address set |

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

- **Nothing is validated yet.** There are no labelled outcomes, so no tier has
  been shown to beat the base rate. The harvest is the prerequisite, not the
  proof.
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
