# Architecture — TJR A+ Autonomous Trading System

**Status:** Draft v0.1 · **Date:** 2026-07-23 · **Fork:** `JivSTuban/tjr-vibe-trading` (upstream `HKUDS/Vibe-Trading`)

This document maps the PRD's constrained execution pipeline (PRD §3, §24, §25) onto the **actual Vibe-Trading components** identified in `docs/research/VIBE_TRADING_AUDIT.md`. Where a component already exists upstream it is marked **REUSE**; where TJR-specific logic must be added it is marked **ADD**.

---

## 1. Design invariant

Codex may identify, propose, execute, monitor, and review trades — but **every order must pass a deterministic, LLM-independent gate**. No free-form order path exists. This is enforced structurally, not by prompt discipline.

```text
TJR Course (research/course/)                         [ADD — ingested this session]
      ↓  tjr_course_research skill
Strategy Knowledge Base (knowledge/)                  [ADD]
      ↓  human rule approval (status lifecycle, PRD §13)
Versioned TJR Strategy Engine  ── implements ──▶ SignalEngine.generate()   [REUSE: pluggable engine + AST sandbox]
      ↓
Binance Market Data ──────────── binance_loader.py (ccxt.binance / binanceusdm)   [REUSE]
      ↓
Candidate Scanner (tjr_a_plus_scorer)                 [ADD]
      ↓
Codex Trade Proposal (structured JSON, PRD §15)       [ADD]
      ↓
A+ Setup Validator (deterministic, PRD §16)           [ADD]
      ↓
Risk Engine (independent, PRD §18)  ── enforced by ──▶ mandate gate `check_mandate` (fail-closed)   [REUSE + EXTEND]
      ↓
Execution Gateway (PRD §25)  ── the ONLY broker caller ──▶ sdk_order_gate.py / order_guard.py   [REUSE]
      ↓            ▲ kill switch: filesystem `live/HALT` checked before every broker call   [REUSE]
Binance Testnet / Live API
      ↓
Position Monitor (tjr_execution_monitor)              [ADD — reconciliation exists, wire TJR rules]
      ↓
Journal & Review ──────────────── append-only redacted `audit.jsonl` (3 sinks, consent chain)   [REUSE]
```

---

## 2. Component map (PRD → upstream reality)

| Pipeline stage | PRD ref | Upstream component (audit) | Action |
|---|---|---|---|
| Deterministic strategy logic | §4, §13 | `SignalEngine.generate()` + AST sandbox; LLM authorship optional | REUSE — implement TJR rules as an engine, do **not** let the LLM author signals |
| Global execution disable | §6, FR-010 | filesystem kill switch `live/HALT`, checked before every broker call | REUSE — default-on for this fork until testnet gate |
| Testnet/live isolation | §19 | per-broker paper/live guard + separate profiles + per-broker secrets | REUSE — configure Binance testnet profile only |
| Backtester | §27 | built-in engines, signal lagged 1 bar (`base.py:203-206`), causality tests pass — **look-ahead SAFE** | REUSE — forbid custom full-history optimizers without review |
| SMC calculations | FR-004 | `smartmoneyconcepts` lib, params `swing_length`, `close_break` | ADAPT — override with TJR-approved definitions only |
| Market data | FR-003 | `binance_loader.py` (ccxt, no key needed for market data) | REUSE |
| Order idempotency | FR-007 | `repeatable=False` + daily lock; **no client_order_id** | **ADD** — inject `client_order_id` dedup key (top gap) |
| Position sizing | §6, FR-007 | engine clip/normalize/round + mandate caps | REUSE — deterministic, outside the LLM |
| Gateway boundary | §25 | fail-closed `check_mandate`; agent can't edit mandate or re-scope keys | REUSE — Codex never holds raw broker keys |
| Audit trail | FR-009 | append-only redacted `audit.jsonl`, 3 sinks, consent chain | REUSE — extend schema with TJR proposal + rejection codes |

**Order-execution send-sites (must stay behind the gate — 2 real):**
- Direct SDK: `agent/src/live/sdk_order_gate.py:523`
- MCP path: `agent/src/live/order_guard.py`
- Tool entry points: `trading_connector_tool.py:319` (`trading_place_order`, `trading_cancel_order`)

---

## 3. What this fork ADDS (TJR layer)

1. `research/course/` — ingested TJR Boot Camp KB (55/56 lessons, this session).
2. `knowledge/` — approved glossary, rules (bias/setup/entry/stop/target/management/risk), strategy-versions (PRD §12).
3. `agent/src/skills/tjr_*` — course research, rule extractor, market bias, liquidity, market structure, entry model, A+ scorer, trade proposer, risk review, execution monitor, trade reviewer (PRD §22).
4. A+ setup scorer + deterministic validator (PRD §14, §16) with the 100-point rubric and `>=90` threshold.
5. Trade-proposal schema + validation service (PRD §15) — the only input the execution gateway accepts.
6. `client_order_id` idempotency on the Binance adapter (closes audit gap Q7).

## 4. Environment progression (PRD §19.2)

`local simulation → historical replay → live shadow mode → Binance Testnet → human-approved live → limited autonomous live`. The fork ships pinned at **shadow mode / testnet-disabled**; promotion requires the gates in PRD §28 and owner sign-off. See `SAFETY_POLICY.md`.

## 5. Open architectural decisions (for STRATEGY_GOVERNANCE.md)

- Crypto market has 24/7 sessions — TJR's session/kill-zone concepts (London/NY) need re-mapping for crypto (decide in the strategy-version spec once ingestion rules are reviewed).
- Spot vs USDⓈ-M futures for the first instrument (BTCUSDT). PRD example uses futures; testnet choice affects the adapter.
- Whether to reuse `smartmoneyconcepts` detections or reimplement per TJR's exact definitions (ambiguities surfaced during ingestion will decide this per-concept).
