# Local execution staging

Status: implementation foundation, **live submission unavailable**. This does
not yet automate real Fomo trades. It stages signals and tests order lifecycle
behavior in an isolated Playwright browser. No strategy was promoted, no real
order placed, and nothing deployed to the Mac Mini.

Update, 2026-09-18: the owner removed repository-policy blockers for Fomo in
[decision 0002](../knowledge/decisions/0002-fomo-owner-authorized-execution.md).
The remaining live-submission limitation is missing implementation, not a
pending policy approval. Simulation isolation and operational checks remain.

## Implemented

- Optional staging directly from `FomoRadar._consider`, before Discord delivery.
  Suppressed signals and radar `--dry-run` runs never enter the queue.
- A fresh market observation, strict source timestamp validation, and a second
  eligibility/cost check using the configured USD amount. Cached quote times
  are preserved rather than relabeled as fresh.
- Immutable proposal snapshots with source item ID, evidence, proposed strategy
  version, token identity, fixed size, 60-second maximum expiry, and exits.
- SQLite uniqueness by strategy, network, and token: repeated theses, delivery
  failures, and restarts do not create multiple entries. There is deliberately
  no automatic reentry for the same token/version.
- Simulated confirmed fills set stop price to **fill × 0.80** and take profit to
  **fill × 1.10**. Percentages refer to token price, not account equity or net
  return after fees. A gap through the stop exits at the observed price, not an
  invented guaranteed stop price.
- Persistent submitting/open/closing/closed/uncertain states, a journal, one
  position at a time, one worker per journal, no uncertain-order retries, and
  halt on missing/changed protection or unavailable position quotes.
- Restart with any unresolved or open position requires reconciliation. The
  current harness halts; it does not pretend a fresh browser owns that position.

## Running locally

Tests use synthetic signals and a fresh Chromium context. Every network request
is blocked, service workers are disabled, and no persistent login is loaded.

```sh
.venv/bin/python -m pytest fomo_radar/tests/test_execution.py -q
```

To stage future real signals only, choose a fixed amount first and set `SIZE`
in your shell. There is no default allocation. This command starts the normal
radar, including its existing Discord behavior, and an opt-in proposal journal;
it does **not** start an execution worker:

```sh
.venv/bin/python -m fomo_radar.run \
  --stage-execution-db "$HOME/memecoin-radar-data/execution.sqlite3" \
  --execution-size-usd "$SIZE"
```

Use separate journals for real signal staging and test fixtures. Removing these
flags disables staging without changing the existing radar. The simulation
worker's caller supplies a HALT file; touching it blocks further simulation
orders. No code clears it. Do not delete uncertain state to retry an order.

The simulated fills are deterministic UI fixtures, not economic backtests. The
existing `fill.py` remains the cost model for proposal gating and `paper.py`
remains the historical simulation. The browser fixture makes no profitability
claim and does not implement native stop orders.

## Verified browser connection

On 2026-09-18, the global Claude configuration at `~/.claude.json` contained:

```text
MCP server: onlinejobs-browser
command: npx -y @playwright/mcp@latest
arguments: --user-data-dir ~/.claude/browser-profiles/onlinejobs-apply --browser chromium
```

Connected through that MCP server and verified a logged-in Fomo session.
No order was submitted. On a Solana token page:

- URL: `https://fomo.family/tokens/solana/<mint>`
- Buy/Sell tabs: exact button names `Buy` and `Sell`
- Amount field: exact placeholder `0` (Buy is USD)
- Submit buttons: exact names `Buy <ticker>` / `Sell <ticker>`
- Sell presets: `10%`, `25%`, `50%`, `100%`

`execution_browser.FomoUI.inspect` checks the exact origin/token page and reads
these controls. Its buy/sell methods always refuse. The fixture's fill receipt
schema is synthetic; it has **not** been verified against real Fomo receipts.
Account sessions and secrets are never copied into this repository. The global
MCP registration was not changed.

The implementation uses role/placeholder locators from
[Playwright's locator guidance](https://playwright.dev/python/docs/locators)
and isolates network traffic with
[context routing and blocked service workers](https://playwright.dev/python/docs/network).

## Remaining work before real execution or transfer

Decision 0002 removes the blanket live prohibition, TJR A+ approval requirements,
PRD promotion stages, Binance prerequisites, and TJR minimum reward/risk for this
Fomo executor. The owner-specified stop/target is 0.5:1 gross reward/risk.

Real execution still needs implemented browser handlers, configured sizing,
exact fill/position
reconciliation, prevention of duplicate submissions across browser failures,
and a working exit monitor. A browser price poll is not a broker-held stop;
native protection was not established during this inspection. The Fomo executor
must retain its kill switch. It is not required to use the Binance gateway.

Fixed USD size is awaiting the owner's answer. No background worker or launchd
job is installed. Transfer to the Mini has not been attempted.
