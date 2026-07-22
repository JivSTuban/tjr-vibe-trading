# Product Requirements Document

## TJR A+ Autonomous Trading System

**Document status:** Draft v0.2
**Product type:** AI-assisted automated trading research, validation, and execution system
**Base repository:** `HKUDS/Vibe-Trading`
**Planned fork:** `JivSTuban/tjr-vibe-trading`
**Primary development environment:** OpenAI Codex
**Initial market:** Cryptocurrency
**Initial exchange target:** Binance
**Initial execution environment:** Binance Testnet or simulated paper trading
**Owner:** Jiv Tuban
**Last updated:** July 23, 2026

---

# 1. Product Summary

The TJR A+ Autonomous Trading System is a fork of Vibe-Trading that studies TJR's publicly available trading course, converts the strategy into explicit machine-readable rules, scans cryptocurrency markets, identifies only approved A+ setups, applies strict risk controls, and executes qualified trades automatically.

Codex will be responsible for:

* Studying and documenting TJR's course.
* Building the strategy knowledge base.
* Developing and maintaining the trading system.
* Running scheduled market-analysis workflows.
* Evaluating setup candidates.
* Producing structured trade proposals.
* Triggering order execution after all deterministic checks pass.
* Monitoring active trades.
* Journaling decisions and outcomes.
* Producing daily and weekly reports.
* Investigating failures and abnormal behavior.

Codex may initiate a trade, but it may not bypass the approved strategy engine, risk engine, exchange restrictions, or execution safeguards.

---

# 2. Product Vision

Create an autonomous trading system that combines:

1. TJR's trading methodology
2. Vibe-Trading's research and agent framework
3. Smart Money Concepts analysis
4. Codex skills and scheduled automations
5. Binance market data and order execution
6. Deterministic risk and eligibility controls
7. Explainable trade decisions
8. Continuous journaling and review

The system should act like a disciplined trading operator rather than a free-form chatbot.

The goal is not to maximize trade frequency. The goal is to identify and execute only highly selective, source-backed, testable A+ setups.

---

# 3. Core Product Principle

Codex is allowed to execute trades, but it must operate inside a constrained execution pipeline.

```text
Codex market analysis
        ↓
Structured setup proposal
        ↓
Deterministic strategy validation
        ↓
A+ setup scoring
        ↓
Risk-engine approval
        ↓
Exchange and account validation
        ↓
Order execution
        ↓
Position monitoring
        ↓
Journal and review
```

Codex must never be able to place a trade through an unrestricted command such as `Buy BTC because this chart looks bullish.` Every order must be backed by a structured and validated trade proposal.

---

# 4. Problem Statement

Trading courses often describe setups using subjective language (clean structure, strong displacement, obvious liquidity, high-probability area, good confirmation, A+ setup). These descriptions are not precise enough for safe automated trading.

The product must solve four problems:

1. Convert TJR's strategy into deterministic rules.
2. Validate whether those rules produce useful signals.
3. Prevent Codex from improvising outside approved rules.
4. Allow automatic execution without removing hard safety boundaries.

The project must also separate: what TJR explicitly teaches; interpretations made by Codex; rules approved by the owner; rules implemented in code; rules validated by backtesting; rules approved for testnet or live execution.

---

# 5. Goals

## 5.1 Primary Goals

1. Fork Vibe-Trading into the owner's GitHub account.
2. Study TJR's public trading course.
3. Build a timestamped strategy knowledge base.
4. Convert TJR concepts into machine-readable rules.
5. Create an objective A+ setup definition.
6. Scan Binance markets for qualifying setups.
7. Allow Codex to generate structured trade proposals.
8. Automatically execute approved setups.
9. Enforce fixed position sizing and loss limits.
10. Backtest all enabled strategy versions.
11. Run in shadow mode before testnet execution.
12. Progress from testnet to live trading only through explicit promotion gates.
13. Journal every candidate, rejection, trade, fill, and outcome.
14. Maintain full explainability for every executed trade.

## 5.2 Secondary Goals

Generate annotated charts; export compatible TradingView Pine Script; compare Python and Pine Script signals; create premarket and post-market reports; detect conflicting strategy definitions; track strategy performance by setup subtype; identify degradation or strategy drift; support more exchanges in later versions; support more instruments after initial validation; package TJR workflows as reusable Codex skills.

---

# 6. Non-Goals

The initial product will not: guarantee profitability; trade unrestricted capital; permit withdrawals through exchange credentials; allow Codex to select arbitrary position sizes; allow Codex to override daily loss limits; allow Codex to modify the active strategy while trading; automatically deploy unreviewed strategy changes; use martingale or uncontrolled averaging down; trade without a valid stop-loss; trade without a defined invalidation point; trade stale or incomplete market data; redistribute full copyrighted course materials; train on private or paid content without authorization; support high-frequency or sub-second trading.

---

# 7. Base Repository Strategy

## 7.1 Fork

Built as a fork of `HKUDS/Vibe-Trading` → `JivSTuban/tjr-vibe-trading`.

## 7.2 Why Vibe-Trading

Candidate foundation because it provides or may provide: agent-based financial research; strategy generation; backtesting workflows; skill-based analysis; Smart Money Concepts support; market-data integrations; MCP support; TradingView and Pine Script workflows; persistent research outputs; CLI and service interfaces. The fork must be audited before any broker connection is enabled.

## 7.3 Required Changes to the Fork

TJR course-research skill; TJR strategy knowledge base; TJR-specific market structure definitions; A+ setup scorer; deterministic execution validator; hard risk-management engine; Binance market-data adapter; Binance Testnet execution adapter; idempotent order handling; position-monitoring service; kill switch; audit log; strategy-version locking; Codex execution permissions; testnet/live environment separation.

---

# 8. TASK-001: Evaluate Course-Study Skills and Plugins

**Objective:** Find and test the best Codex-compatible workflow for studying TJR's public YouTube course and converting it into timestamped structured notes.

**Research areas:** YouTube playlist discovery; video metadata extraction; public caption retrieval; transcript processing; browser automation; chapter extraction; structured note generation; citation and timestamp preservation; course-progress tracking; duplicate-content detection; resume support; knowledge-base generation.

**Candidate approaches:** (A) existing Codex plugin; (B) browser automation; (C) local transcript pipeline; (D) custom Codex skill.

**Deliverable:** `docs/research/COURSE_INGESTION_OPTIONS.md` — tools investigated, installation, authentication, supported capabilities, known limitations, automation compatibility, copyright considerations, test results using one TJR lesson, recommended approach, fallback approach, go/no-go decision.

**Acceptance:** ≥3 approaches evaluated; one official TJR lesson processed; important claims retain video timestamps; direct teaching separated from interpretation; proposed algorithmic rules clearly labeled; process can resume without repeating completed work; final architecture recommendation documented.

---

# 9. TASK-002: Fork and Audit Vibe-Trading

**Objective:** Create the project fork and determine which existing Vibe-Trading components can be safely reused.

**Audit areas:** repository architecture; agent workflow; skill-loading system; MCP implementation; market-data providers; backtesting engine; SMC implementation; broker integrations; order-execution paths; secret handling; logging; state persistence; error handling; test coverage.

**Deliverable:** `docs/research/VIBE_TRADING_AUDIT.md`.

**Audit questions:**
1. Can agent-generated strategy logic be replaced with approved deterministic rules?
2. Can broker execution be disabled globally?
3. Can testnet and live environments be isolated?
4. Does the backtester introduce look-ahead bias?
5. Are SMC calculations configurable?
6. Can market data be sourced directly from Binance?
7. Are order requests idempotent?
8. Can position sizing be controlled outside the LLM?
9. Can Codex trigger execution without receiving unrestricted broker access?
10. Can the system create a full audit trail?

**Acceptance:** fork exists; upstream remote preserved; broker execution disabled by default; all existing execution entry points identified; backtesting engine has an initial safety assessment; reusable and replaceable components documented; no real API credentials added.

---

# 10. TASK-003: Create the TJR Course Researcher Skill

Proposed location `agent/src/skills/tjr_course_research/` with `SKILL.md`, `references/` (extraction-schema, terminology-policy, source-ranking), `scripts/` (discover_playlist, extract_metadata, normalize_transcript, validate_timestamps, generate_lesson_record), `templates/` (lesson-record.yaml, unresolved-question.yaml).

**Responsibilities:** accept a video/playlist reference; verify it belongs to the approved corpus; retrieve public metadata; retrieve/produce a timestamped transcript; divide the lesson into logical sections; extract definitions, rules, examples, warnings, exceptions; preserve timestamps; identify ambiguous concepts; propose machine-readable rules; mark all proposed rules unapproved; update course progress; avoid reprocessing completed lessons.

---

# 11. Course Research Outputs

Each lesson produces `research/course/<course-name>/<lesson-number>-<slug>/` containing: `metadata.yaml`, `lesson-summary.md`, `concepts.yaml`, `examples.yaml`, `proposed-rules.yaml`, `ambiguities.md`, `verification-questions.md`, `completion.json`.

## 11.1 Lesson Schema

```yaml
lesson:
  course: ""
  lesson_number: 0
  title: ""
  source_reference: ""
  publication_date: ""
  processed_at: ""
  strategy_version_context: ""

concepts:
  - name: ""
    teacher_definition: ""
    source_timestamp: ""
    codex_interpretation: ""
    confidence: low
    requires_confirmation: true

rules:
  - id: ""
    teacher_statement: ""
    source_timestamp: ""
    proposed_machine_rule: ""
    status: proposed
    ambiguity: ""
    counterexamples: []

examples:
  - timestamp: ""
    instrument: ""
    timeframe: ""
    direction: ""
    setup_components: []
    stated_outcome: ""
    suitable_for_dataset: false
```

---

# 12. Strategy Knowledge Base

`knowledge/` with `glossary/`, `rules/` (bias, setup, entry, stop, target, management, risk), `examples/` (positive, negative, ambiguous), `conflicts/`, `decisions/`, `strategy-versions/`.

Each strategy rule must contain: human-readable definition; source reference; source timestamp; Codex interpretation; approved machine rule; positive examples; negative examples; edge cases; unit-test requirements; approval status; strategy version.

---

# 13. Strategy Rule Lifecycle

`observed → proposed → needs-clarification → conflicting → approved-for-coding → implemented → unit-tested → backtested → shadow-approved → testnet-approved → live-approved → retired`.

Codex may propose rules but may not promote a rule to `live-approved` automatically.

---

# 14. A+ Setup Definition

An A+ setup must: match the active strategy version; pass every mandatory condition; meet the minimum setup score; occur during an approved session; use fresh and complete market data; have a defined entry, stop-loss, and target; meet minimum reward-to-risk; pass all account and risk restrictions; have no duplicate active signal; use an approved execution environment; be recorded before its outcome is known.

## 14.1 Initial Setup Score

| Component | Max Points |
| --- | ---: |
| Higher-timeframe bias | 15 |
| Approved market session | 10 |
| Valid area of interest | 10 |
| Liquidity sweep or event | 15 |
| Market-structure shift | 15 |
| Displacement | 10 |
| Fair-value gap or entry model | 10 |
| Clear invalidation | 5 |
| Reward-to-risk quality | 5 |
| No conflicting condition | 5 |
| **Total** | **100** |

Initial threshold: `A+ score >= 90`. A mandatory requirement cannot be replaced by a higher score elsewhere.

---

# 15. Codex Trade Proposal

```json
{
  "proposal_id": "uuid",
  "strategy_version": "tjr-v0.1",
  "environment": "binance_testnet",
  "instrument": "BTCUSDT",
  "market_type": "futures",
  "direction": "long",
  "timeframe": "5m",
  "setup_type": "liquidity_sweep_mss_fvg",
  "setup_score": 94,
  "mandatory_conditions": {
    "higher_timeframe_bias": true,
    "liquidity_sweep": true,
    "market_structure_shift": true,
    "displacement": true,
    "entry_model": true
  },
  "entry": 65000,
  "stop_loss": 64750,
  "take_profit": 65625,
  "reward_risk": 2.5,
  "risk_percent": 0.25,
  "expires_at": "ISO-8601 timestamp",
  "evidence": [],
  "rejection_conditions": []
}
```

Codex cannot submit free-form orders. Only validated proposals may reach the execution service.

---

# 16. Execution Authorization

```python
eligible = (
    proposal.strategy_version == active_strategy_version
    and proposal.environment == approved_environment
    and proposal.setup_score >= minimum_setup_score
    and proposal.all_mandatory_conditions_passed
    and proposal.reward_risk >= minimum_reward_risk
    and market_data.is_fresh
    and market_data.is_complete
    and account.is_healthy
    and not risk.daily_loss_limit_hit
    and not risk.weekly_loss_limit_hit
    and not risk.max_trade_count_hit
    and not risk.position_already_open
    and not risk.duplicate_signal
    and not execution.kill_switch_active
    and not execution.news_restriction_active
)
```

Execution must fail closed. Any missing or unknown condition must reject the trade.

---

# 17. Codex Execution Permissions

**May:** scan approved instruments; analyze approved timeframes; generate trade proposals; request validation; trigger validated testnet orders; trigger validated live orders after live approval; cancel stale unfilled orders; move stops only under approved management rules; close trades when an approved exit rule triggers; record execution outcomes; disable trading when abnormal behavior is detected.

**May not:** change active risk percentage during a session; remove a stop-loss; increase maximum leverage; override a kill switch; trade an unapproved instrument; trade an unapproved strategy version; create a market order without a validated proposal; average into a losing trade unless explicitly allowed; retry a failed order indefinitely; transfer or withdraw funds; reveal API secrets; promote the system from testnet to live.

---

# 18. Risk Engine

Operates independently of Codex reasoning.

**Controls:** max risk per trade; max account exposure; max leverage; max daily loss; max weekly loss; max trades per session; max consecutive losses; max simultaneous positions; instrument concentration limit; correlated-position limit; stale-data protection; duplicate-signal protection; price-deviation protection; spread protection; slippage protection; minimum reward-to-risk; mandatory stop-loss; kill switch.

**Initial default limits (placeholders — require owner approval):**

```yaml
risk:
  risk_per_trade_percent: 0.25
  maximum_daily_loss_percent: 0.75
  maximum_weekly_loss_percent: 2.0
  maximum_trades_per_day: 2
  maximum_open_positions: 1
  maximum_consecutive_losses: 3
  minimum_reward_risk: 2.0
  maximum_leverage: 2
```

---

# 19. Binance Integration

**Scope:** exchange info; instrument filters; OHLCV candles; mark price; order book; account balance; open positions; open orders; order creation; order cancellation; fill retrieval; position closure.

**Environment order:** local simulation → historical replay → live shadow mode → Binance Testnet → human-approved live trading → limited autonomous live execution.

**Credential requirements:** disable withdrawals; minimum permissions; IP restrictions where supported; remain outside the repo; stored through environment secrets; separate testnet and live credentials; never exposed to course-research tasks; never printed in logs.

---

# 20. Functional Requirements

- **FR-001 Course Progress** — track lessons discovered/completed/awaiting review; rules extracted/approved; open ambiguities; conflicting definitions.
- **FR-002 Source Traceability** — every enabled rule includes course, lesson, video reference, timestamp, extraction date, approval state, strategy version.
- **FR-003 Market Data** — multiple timeframes; UTC normalization; session boundaries; missing-data detection; freshness checks; historical replay; Binance instrument rules.
- **FR-004 Setup Detection** — swing highs/lows; market structure; liquidity levels; liquidity sweeps; BOS; MSS; CHoCH; displacement; FVGs; premium/discount; entry zones; invalidation levels; target liquidity. Only course-approved definitions active.
- **FR-005 Setup Scoring** — total score; component scores; mandatory-condition results; evidence; rejection codes; strategy version; expiration; execution eligibility.
- **FR-006 Explainability** — every executed trade explains instrument, HTF bias, liquidity level, confirmation, entry, stop, target, rules passed, risks checked, authorization.
- **FR-007 Order Execution** — market/limit/stop/take-profit/reduce-only orders; cancellation; idempotency keys; retry limits; partial fills; exchange filter validation; position reconciliation.
- **FR-008 Position Monitoring** — entry fills; remaining quantity; stop/target placement; unrealized PnL; disconnections; rejection; unexpected position changes; exit conditions.
- **FR-009 Journaling** — all candidates; rejected/approved setups; proposals; risk-engine results; orders; fills; slippage; stops/targets; position changes; outcome; explanation; strategy version; market snapshot.
- **FR-010 Kill Switch** — manual global shutdown; auto after loss limits, repeated API errors, state mismatch, missing stop-loss, unexpected live-environment activation.

---

# 21. Rejection Codes

```text
REJECT_UNAPPROVED_STRATEGY, REJECT_WRONG_ENVIRONMENT, REJECT_NO_HTF_ALIGNMENT,
REJECT_NO_LIQUIDITY_EVENT, REJECT_NO_STRUCTURE_SHIFT, REJECT_WEAK_DISPLACEMENT,
REJECT_INVALID_ENTRY_MODEL, REJECT_LOW_SETUP_SCORE, REJECT_LOW_REWARD_RISK,
REJECT_INVALID_STOP, REJECT_INVALID_TARGET, REJECT_STALE_DATA, REJECT_MISSING_DATA,
REJECT_DUPLICATE_SIGNAL, REJECT_POSITION_ALREADY_OPEN, REJECT_MAX_TRADES,
REJECT_DAILY_LOSS_LIMIT, REJECT_WEEKLY_LOSS_LIMIT, REJECT_MAX_CONSECUTIVE_LOSSES,
REJECT_EXCESSIVE_LEVERAGE, REJECT_EXCHANGE_FILTER, REJECT_PRICE_DEVIATION,
REJECT_SPREAD_TOO_WIDE, REJECT_KILL_SWITCH, REJECT_NEWS_WINDOW, REJECT_PROPOSAL_EXPIRED
```

---

# 22. Codex Skills

`agent/src/skills/`: smc, tjr_course_research, tjr_rule_extractor, tjr_market_bias, tjr_liquidity, tjr_market_structure, tjr_entry_model, tjr_a_plus_scorer, tjr_trade_proposer, tjr_risk_review, tjr_execution_monitor, tjr_trade_reviewer.

**Trade Proposer:** uses only active strategy version; approved market data; structured output; includes evidence + expiration; never calls the exchange directly; submits to the validation service.

**Execution Monitor:** checks order status; checks stop/target status; detects missing protection; reconciles local vs exchange state; cancels stale orders; triggers the kill switch when required.

---

# 23. Codex Automations

Course study; market scan; execution monitoring; post-trade review; weekly audit. Weekly audit never alters the live strategy automatically.

---

# 24. System Architecture

```text
TJR Course → Course Research Skill → Strategy KB → Human Rule Approval →
Versioned TJR Strategy Engine → Binance Market Data → Candidate Scanner →
Codex Trade Proposal → A+ Setup Validator → Risk Engine → Execution Gateway →
Binance Testnet/Live API → Position Monitor → Journal & Performance Review
```

---

# 25. Execution Gateway

The only component allowed to communicate with the Binance order API. It must: accept only signed internal trade proposals; validate proposal schemas; check expiration; check strategy version; check environment; re-run all risk checks; validate exchange filters; add an idempotency key; submit the order; confirm stop/target placement; store the exchange response; reject any incomplete request. Codex must not hold direct unrestricted exchange credentials.

---

# 26. Proposed Repository Structure

See PRD source; top-level: `agent/`, `docs/`, `research/`, `knowledge/`, `strategy/`, `market_data/`, `proposals/`, `validation/`, `risk/`, `execution/` (gateway, binance_testnet, binance_live, reconciliation), `monitoring/`, `journaling/`, `backtesting/`, `reporting/`, `tests/` (unit, integration, execution, safety, regression, fixtures), `data/` (raw, normalized, labeled).

---

# 27. Validation Stages

1. Course Extraction 2. Rule Implementation 3. Backtesting 4. Shadow Mode 5. Binance Testnet 6. Restricted Live Mode 7. Autonomous Live Mode. Each stage has explicit required gates (no look-ahead bias, fees/spread/slippage, kill-switch verification, owner promotion, etc.).

---

# 28. Promotion Gates

Research→Development; Development→Backtesting; Backtesting→Shadow; Shadow→Testnet; Testnet→Live. Each gate lists explicit criteria; Testnet→Live requires owner approval.

---

# 29. Success Metrics

Research (completion %, rules extracted/approved, ambiguities, conflicts); Setup Detection (precision, recall, FP rate, A+/week); Strategy (expectancy, profit factor, win rate, avg RR, max drawdown); Execution (fill rate, slippage, missing-stop events, reconciliation failures, kill-switch activations); Operations (data freshness, proposal/execution latency, uptime, recovery time).

---

# 30. Initial Backlog (Epics)

1. Repository Foundation 2. Research 3. Strategy Knowledge Base 4. TJR Strategy 5. Vibe-Trading Adaptation 6. Binance 7. Codex Execution 8. Validation.

---

# 31. MVP Definition

Forked; one TJR course processed; core rules have source timestamps; an approved strategy version exists; one Binance instrument; one setup type; one market session; Codex can generate structured proposals; deterministic validation operational; risk engine operational; Binance Testnet execution operational; every trade has a stop and target; every action journaled; kill switch tested; real-money execution remains disabled.

---

# 32. Recommended First Codex Task

Fork `HKUDS/Vibe-Trading` → `JivSTuban/tjr-vibe-trading`; no broker/live integration; preserve upstream remote; branch `feature/tjr-foundation`. Execute TASK-001 + TASK-002; create `docs/research/COURSE_INGESTION_OPTIONS.md`, `docs/research/VIBE_TRADING_AUDIT.md`, `docs/ARCHITECTURE.md`, `docs/SAFETY_POLICY.md`. Do not add API keys; do not enable live execution; do not process the complete course prematurely; do not approve any strategy rule automatically.

---

# 33. Final Product Rule

Every execution must satisfy: approved course-backed strategy + versioned deterministic rules + A+ setup qualification + structured trade proposal + independent risk approval + fresh market data + authorized environment + exchange validation + complete audit trail. Codex may identify, propose, execute, monitor, and review trades. Codex may not bypass the rules that authorize those trades.
