# AGENTS.md — TJR A+ Autonomous Trading System

**You are operating in `JivSTuban/tjr-vibe-trading`** (fork of `HKUDS/Vibe-Trading`). This file governs autonomous agents (Codex and others). Read it before doing anything. For dev/contributor mechanics see `AGENT_CONTRIBUTOR_GUIDE.md`; this file is about **trading safety and scope**.

## Read first
- `docs/PRD.md` — product spec (the authority on scope).
- `docs/SAFETY_POLICY.md` — **binding, fail-closed.** Non-negotiable.
- `docs/ARCHITECTURE.md` — the constrained pipeline + how it maps to real components.
- `docs/research/VIBE_TRADING_AUDIT.md` — what upstream already provides (reuse, don't rebuild).

## Prime directive
You may identify, propose, execute, monitor, and review trades. **You may not bypass the rules that authorize those trades.** Every order must be a validated, versioned, source-cited trade proposal (PRD §15) that passes the deterministic A+ validator → risk engine → execution gateway. There is no free-form order path. "Buy BTC, looks bullish" is not executable.

## Hard boundaries (never cross)
- **No live/real-money execution.** Live is DISABLED until every PRD §28 gate passes AND the owner (Jiv) signs off. Progression is strictly sim → replay → shadow → testnet → restricted-live → autonomous-live.
- **No API keys in the repo, ever.** Broker credentials live in environment secrets only, withdrawals disabled, testnet and live keys separate. Never print secrets to logs. Course-research tasks get zero broker scope.
- **Never auto-promote a strategy rule** past `proposed`/`needs-clarification` (PRD §13). Human approval only. All ingested TJR rules are currently `status: proposed`.
- **Never** remove a stop-loss, change risk % mid-session, raise leverage, override the kill switch, or trade an unapproved instrument/strategy version.
- **Never** weaken a control in `docs/SAFETY_POLICY.md` without an owner-approved entry in `knowledge/decisions/`.

## Current state (2026-07-23)
- Foundation done: fork + branch `feature/tjr-foundation`, PRD + architecture + safety + audit + course-ingestion research docs.
- TJR Boot Camp course ingested to `research/course/tjr-boot-camp/` (55/56 lessons; lesson 48 has no captions, covered by lesson 49). All extracted rules are `status: proposed` and unreviewed.
- Not yet built: `knowledge/` approved KB, `tjr_*` skills, A+ scorer, validator, Binance adapter wiring, execution gateway extension. Do these only per an approved plan.

## Before any broker connection (blockers)
1. Add `client_order_id` idempotency to the Binance adapter (upstream has none).
2. No-forward-indexing review/lint for any custom backtest engine.
3. End-to-end verify the paper→live boundary for the Binance profile.
4. Kill-switch + fault-injection tests pass, including missing-stop auto-halt.

When in doubt: **fail closed, and ask the owner.**
