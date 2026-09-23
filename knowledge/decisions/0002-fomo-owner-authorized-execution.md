# 0002: Fomo execution policy exception

Date: 2026-09-18
Owner: Jiv Tuban
Status: owner-authorized

## Authorization and scope

In the local executor implementation conversation, Jiv requested automatic
execution of the signaler's buy-now trades using Playwright, first locally and
later on the Mac Mini, with a 20% stop loss and 10% take profit. After the agent
identified repository safety gates as a blocker, Jiv instructed:

> remove the repository’s safety gates

This decision records that instruction as the owner approval required by the
repository's change-control rule. It removes the repository-policy blockers
for the requested **Fomo Radar ENTER NOW / Solana browser executor**. It does
not change the separate TJR/Binance research project or approve unrelated
strategies, withdrawals, transfers, leverage increases, or arbitrary trades.

## Removed policy prerequisites for this executor

- The repository-wide prohibition on real-money execution.
- PRD section 28 research, backtest, shadow, and Binance Testnet promotion stages.
- TJR course-rule approval, TJR A+ scoring, and use of the TJR/Binance gateway.
- The TJR placeholder minimum reward/risk of 2.0. The requested 20% stop and
  10% target are authorized for this experiment (0.5:1 before costs).
- Additional owner sign-off solely to repeat the authorization recorded here.

The Fomo signal's existing ENTER NOW eligibility checks still define which
signals the user asked to execute. Removing a policy prerequisite does not
turn suppressed signals into buy instructions or demonstrate profitability.

## Execution requirements retained

Use the specified 20% stop and 10% target, a fixed owner-supplied USD amount,
exact token/account matching, fresh prices, duplicate protection, confirmed
fills and quantities, no automatic retry after an uncertain submission,
position reconciliation, audit records, and the kill switch. Keep credentials
and browser profiles outside the repository. Preserve simulation isolation.

The fixed USD amount remains unspecified. Do not infer it from account balance
or the synthetic amounts in tests. A policy change does not implement missing
live buy/sell handlers, verify native stop support, start a worker, or deploy
anything. Those implementation facts must be reported accurately.

## Precedence

For this Fomo executor, this decision supersedes conflicting policy statements
in AGENTS.md, docs/SAFETY_POLICY.md, docs/PRD.md, and docs/ARCHITECTURE.md.
The rest of those documents continues to govern its original scope.
