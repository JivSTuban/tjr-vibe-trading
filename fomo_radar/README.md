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

Measured over 20,337 theses on 2026-09-17:

- **Earliness is the edge.** Median unrealized PnL decays monotonically across
  all ten deciles of thesis order on a token: **+192% for the earliest 10%, +21%
  for the latest 10%.** The literal first thesis medians **+716%**.
- **Size, not the X link.** X-linked theses look far better raw (57.1% win vs
  46.0%) but are **7.8× larger**; gate both at ≥$5k and it inverts. `has_x_link`
  is stored and displayed as context and contributes **zero** to the score.
- **Distinct authors, not post count.** One handle posting three times in four
  minutes was common and is not confirmation.
- **The leaderboard lags.** Its top-consensus holdings are already-won positions
  ($56M aggregate PnL on the most-held name) and only 19 of 153 were trending.
  It raises a candidate's tier; it can never create one.

> ⚠️ The research sample is 50 **trending** tokens, so those PnL *levels* are
> survivorship-biased and meaningless in absolute terms. What survives is the
> *ordering*, because both sides of every comparison share the bias. That is why
> this harvester records every candidate including the ones that die — the
> rejects are the base rate.

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

Very quiet. Replaying 2,374 real harvested theses, **3 cleared the hard gates**
(~0.1%). Most tokens never qualify and a silent channel is the designed steady
state. `fomo_alerts` plus the `delivered` flag is how you tell "nothing
qualified" from "delivery broke".

## Known gaps

- **Nothing is validated yet.** There are no labelled outcomes, so no tier has
  been shown to beat the base rate. The harvest is the prerequisite, not the
  proof.
- The `CONVICTION` tier has never fired on real data — it is reachable by
  construction (`test_all_tiers_reachable`) but unobserved. Treat its rate as
  unknown until it fires.
- Solana is the only chain the radar cares about, but the feed is multi-chain and
  everything is recorded. Filter downstream.
