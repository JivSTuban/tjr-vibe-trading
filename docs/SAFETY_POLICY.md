# Safety Policy — TJR A+ Autonomous Trading System

**Status:** Draft v0.1 · **Date:** 2026-07-23 · Binding on all code, agents, and automations in this fork.

This policy is **non-negotiable and fail-closed**. Where it references existing enforcement, see `docs/research/VIBE_TRADING_AUDIT.md` for file evidence. Nothing in this fork may weaken a control below without owner (Jiv) sign-off recorded in `knowledge/decisions/`.

---

## 0. Prime directive

> Codex may identify, propose, execute, monitor, and review trades. **Codex may not bypass the rules that authorize those trades.** Every order must be backed by a validated, versioned, source-cited trade proposal that passes an independent, deterministic gate. (PRD §33)

## 1. Current posture (this fork, today)

- **Live execution: DISABLED.** Real-money trading remains off until every promotion gate in PRD §28 is met and the owner signs off.
- **Environment: shadow / testnet-disabled.** Progression is strictly `local sim → replay → shadow → Binance Testnet → restricted live → autonomous live` (PRD §19.2). No skipping stages.
- **No credentials in-repo.** No API keys have been added. None may be committed, ever.

## 2. Fail-closed execution (PRD §16)

Execution authorization evaluates a full conjunction of conditions (strategy version, environment, setup score ≥ threshold, all mandatory conditions, R:R, fresh+complete data, account health, all risk limits, no duplicate, kill switch off, no news window). **Any missing or unknown condition rejects the trade.** Unknown ≠ permissive. Every rejection emits a code (PRD §21) to the audit log.

Enforced upstream by the fail-closed mandate gate (`check_mandate`) and the filesystem kill switch (`live/HALT`) checked before every broker call. The TJR A+ validator sits in front of these, never around them.

## 3. Codex permission boundaries (PRD §17)

**Codex MAY:** scan approved instruments; analyze approved timeframes; generate proposals; request validation; trigger *validated* testnet orders (and live only after live-approval); cancel stale unfilled orders; move stops only under approved management rules; close on approved exit rules; record outcomes; disable trading on abnormal behavior.

**Codex MAY NOT:** change risk % mid-session; remove a stop-loss; increase max leverage; override the kill switch; trade an unapproved instrument or strategy version; create a market order without a validated proposal; average into a loser unless the approved strategy explicitly allows; retry a failed order indefinitely; transfer or withdraw funds; reveal API secrets; **promote the system from testnet to live.**

Structural backing: Codex never holds raw broker credentials (gateway boundary, audit Q9); it cannot edit the mandate or re-scope keys.

## 4. Risk engine independence (PRD §18)

The risk engine runs **outside** LLM reasoning. It owns: max risk/trade, max exposure, max leverage, max daily/weekly loss, max trades/session, max consecutive losses, max simultaneous positions, concentration + correlation limits, stale-data/duplicate-signal/price-deviation/spread/slippage protection, minimum R:R, mandatory stop-loss, and the kill switch. Initial limits (PRD §18.2) are **placeholders requiring owner approval** before any testnet run. Position sizing is deterministic (engine clip/normalize/round + mandate caps, audit Q8) — never LLM-chosen.

## 5. Credential rules (PRD §19.3)

Execution credentials must: disable withdrawals; use minimum permissions; use IP restrictions where supported; live **outside** the repo (environment secrets only); use separate testnet vs live keys; never be exposed to course-research tasks; never be printed in logs. The audit log is append-only and **redacted** (audit Q10). Course-research agents (e.g. `tjr_course_research`) run with zero broker scope.

## 6. Kill switch (PRD FR-010)

Global shutdown must trigger: manually; automatically after loss limits, repeated API errors, state mismatch, a **missing stop-loss**, or **unexpected live-environment activation**. Reuses the upstream `live/HALT` filesystem switch. A halted system rejects all new orders and requires human clearance to resume.

## 7. Strategy governance (PRD §13)

Rules move through `observed → proposed → … → live-approved → retired`. **Codex may propose but may never auto-promote a rule to `live-approved`.** All ingested TJR rules currently sit at `status: proposed` (this session's course ingestion) and require human review before any coding/backtest. Direct teaching is kept separate from Codex interpretation in every lesson record.

## 8. Mandatory safeguards to CLOSE before any broker connection

From the audit's top gaps — these are blockers for the Testnet gate:
1. **Broker idempotency key.** Add `client_order_id` + dedup on the Binance adapter (upstream has `repeatable=False` + a daily lock but **no client-order-id**). No order may be sendable twice on a retry.
2. **Custom-strategy look-ahead review.** Built-in backtester is look-ahead SAFE (signal lagged 1 bar), but author-written engines/optimizers can reintroduce bias via full-history frames. Require mandate review + a no-forward-indexing lint before any custom engine backtests.
3. **Paper→live boundary verification.** End-to-end prove the structural testnet/live isolation for the chosen Binance broker profile before enabling testnet, and again before restricted-live.
4. **Fault-injection + kill-switch tests** must pass (PRD §28 Testnet→Live) — including a missing-stop auto-halt test, which upstream currently lacks.

## 9. Copyright & data ethics

TJR course content is public but copyrighted. This project extracts **timestamped rules and notes for an internal strategy KB only** — it does not redistribute full transcripts and does not train on paid/private content without authorization (PRD §6). Raw transcripts under `research/course/**/_transcripts/` are working artifacts, not for republication.

---

**Change control:** any deviation from this policy requires an entry in `knowledge/decisions/` with owner approval and a dated rationale. Silence is not approval; when in doubt, fail closed.
