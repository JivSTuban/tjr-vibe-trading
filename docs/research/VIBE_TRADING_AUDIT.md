# Vibe-Trading Architecture + Safety Audit

**Date:** 2026-07-23
**Repo:** `/Users/jivtuban/Desktop/trader` (fork of HKUDS/Vibe-Trading, Python)
**Task:** TASK-002 — read-only architecture + safety audit for a safety-critical fork (TJR project).
**Scope note:** This audit is READ-ONLY. No source was modified, no credentials were added, and nothing that could place an order or reach a broker was executed. Evidence is cited as `FILE:LINE` throughout.

---

## 1. Repository Architecture

### Layout (from `AGENT_CONTRIBUTOR_GUIDE.md`, README, and tree walk)
- **`agent/`** — backend + Python package (all safety-critical code).
- **`frontend/`** — Vite/React Web UI (`docker-compose.yml` frontend service on `127.0.0.1:5899`).
- **`wiki/`** — public docs, separate CI.
- **`tools/`** — repo tooling incl. the CI env-var gate (`tools/test_ci_env_var_gate.py`).
- **MCP entry point:** `vibe-trading-mcp` / `agent/mcp_server.py` (`AGENT_CONTRIBUTOR_GUIDE.md` "Repository Shape").

### Entry points
- **MCP server:** `agent/mcp_server.py` — builds `mcp = FastMCP("Vibe-Trading", version=APP_VERSION)` (`agent/mcp_server.py:72`) and registers tools with the `@mcp.tool` decorator (`:407`, `:419`, `:442`, `:491`, `:507`, `:602`, `:651`, `:682`, `:717`, …). Network transports are wrapped in DNS-rebinding-hardened ASGI middleware with host allowlisting (`_build_network_app`, `:296`; `_origin_allowed`, `:198`).
- **CLI:** `agent/cli/` package (interactive front door + slash router; refactored out of the old 3216-LOC `agent/cli.py`, README News 2026-05-21). `agent/cli/_legacy.py` shims old subcommands.
- **REST/API + SSE:** FastAPI backend on `127.0.0.1:8899` (`docker-compose.yml`), `agent/src/api/` (e.g. `alpha_routes.py`, `helpers.py`).
- **Docker:** `docker-compose.yml` — read-only rootfs, dropped caps, `no-new-privileges`, `mem_limit 4g`, `pids_limit 512`, named volumes for persistent state under `/home/vibe/.vibe-trading`.

### Agent workflow
- Natural-language prompt → agent loop (`agent/src/core/runner.py`) → tools (48+ registered) → optional multi-agent **swarm** (investment/quant/risk committees). Swarm workers pull market data only through the normalized loader registry (README News 2026-06-11).
- Per-run artifacts written under `agent/runs/` incl. a `TraceWriter` trace (`tool_call`/`tool_result`/`live_action`) and per-run `llm_usage.json`.

### Skill-loading system
- Skills live under `agent/src/skills/<name>/` — each a self-contained directory with a `skill.md` (frontmatter: `name`, `description`, `category`) and an `example_signal_engine.py` exposing a `SignalEngine` class (`agent/src/skills/smc/`, `.../harmonic/`, `.../elliott-wave/`, `.../ichimoku/`, `.../multi-factor/`, 16+ bundled).
- MCP exposes `list_skills()` (`agent/mcp_server.py:408`) and `load_skill(name)` (`:420`). A `_get_skills_loader()` accessor resolves the loader (`:309`).
- The canonical signal contract is `def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]` (validated at `agent/backtest/runner.py:520` error text).

### MCP implementation / exposure
- Built on **FastMCP** (`from fastmcp import Context, FastMCP`, `agent/mcp_server.py:62`).
- Exposed tools are research/read-oriented: `list_skills`, `load_skill`, `start_research_goal`, `get_research_goal`, `add_goal_evidence`, `backtest`, `factor_analysis`, plus trading-connector **reads** and swarm orchestration.
- **Live trading is structurally excluded from the goal layer:** `_risk_tier_from_text` raises `ValueError("live trading or execution goals are not supported")` (`agent/mcp_server.py:398`).

---

## 2. All Order-Execution Entry Points (critical — the fork must be able to disable these)

There are **two** order-execution code paths, plus their user-facing tool wrappers. Both are gated (see Q2/Q9). Enumerated with `FILE:LINE`:

| # | Entry point | File:Line | Path type |
|---|-------------|-----------|-----------|
| 1 | `execute_live_order(...)` — direct-SDK gate (tiger/alpaca/okx/binance/futu) | `agent/src/live/sdk_order_gate.py:98` | Function gate → `connector_module.place_order(config, **place_kwargs)` at `:523` |
| 2 | `_allow(...)` — the only place a direct-SDK order is actually sent | `agent/src/live/sdk_order_gate.py:520-523` | `result = connector_module.place_order(...)` |
| 3 | `LiveOrderGuardTool.execute()` — MCP/Robinhood gate | `agent/src/live/order_guard.py` (class doc `:8`; `halt` check `:157-160`) | Wraps remote MCP `place_order` via `super().execute` |
| 4 | `trading_place_order` tool (`name = "trading_place_order"`) | `agent/src/tools/trading_connector_tool.py:319`, `execute` at `:343` | Agent-facing tool; paper → sandbox, live → gate |
| 5 | `trading_cancel_order` tool | `agent/src/tools/trading_connector_tool.py` (imports `cancel_order` `:20`) | Agent-facing tool |
| 6 | Connector `place_order` / `cancel_order` implementations | `agent/src/trading/` (imported at `trading_connector_tool.py:20,27`) | Per-broker SDK calls |

**Both real send-sites (#2 MCP `super().execute`, and the direct-SDK `connector_module.place_order` at `sdk_order_gate.py:523`) are reached only after the fail-closed gate.** For a broker with no structural paper/live discriminator (Longbridge, Trading 212, Dhan, Shoonya), `place_order`/`cancel_order` hard-refuse any non-paper config at the first line (README News 2026-06-29, 2026-06-05).

---

## 3. The 10 Audit Questions

### Q1 — Can agent-generated strategy logic be replaced with approved deterministic rules?
**VERDICT: YES — the strategy layer is fully pluggable, not LLM-freeform at execution time.**
Strategies are `SignalEngine` classes implementing `generate(data_map) -> {code: signal Series}` (`agent/src/skills/smc/example_signal_engine.py:678`; contract validated at `agent/backtest/runner.py:520`). The LLM *drafts* engine source, but every engine passes an **AST sandbox + interface validation** before it can run: `_validate_signal_engine_source` (`runner.py:470`), `_validate_signal_engine_class` (`:504`), forbidden-import/os/open/getattr rejectors (`:335`, `:348`, `:379`, `:403`), and runtime-reachable scanning (`:431`). A fork can simply ship its own approved `SignalEngine` (deterministic TJR rules) and disable LLM-authored engines. **REUSE the interface; the LLM authorship step is optional and replaceable.**

### Q2 — Can broker execution be disabled globally?
**VERDICT: YES — single filesystem kill switch + selectable profiles.**
`agent/src/live/halt.py` implements an out-of-band sentinel `<runtime_root>/live/HALT`. `halt_flag_set()` is checked at the top of **every** order path before any broker call (`order_guard.py:157-160`; the direct-SDK gate imports `halt_flag_set` at `sdk_order_gate.py:85` and checks it in step 3). It is enforced "**independent of the LLM cooperating**" and even if the agent loop is wedged (`halt.py` module docstring). Global sentinel overrides per-broker sentinels. `touch`-ing the file trips it; malformed contents still count as tripped (fail-closed). Additionally, only *live* profiles route to a broker at all — selecting a paper profile (`trading_select_profile`, `trading_connector_tool.py:114`) keeps all writes in sandbox.

### Q3 — Can testnet and live environments be isolated?
**VERDICT: YES — structural per-broker paper/live guard + separate profiles + separate secrets.**
Every paper/live distinction is a **structural** per-broker guard: account-id format, host separation, demo flag, or trade environment (README News 2026-06-02). Profiles are stored in `~/.vibe-trading/trading-connections.json` and selected by id (e.g. `ibkr-paper-local` vs `robinhood-live-mcp`) via `trading_connector_tool.py:3-4,57,114-136`. Live tests (`test_sdk_order_gate.py:204` "paper_is_direct", `:217` "live_routes_through_gate") prove paper bypasses the mandate gate while live is forced through it. Secrets are per-broker env fields (see Q Secret Handling). No shared testnet/live toggle to fat-finger.

### Q4 — Does the backtester introduce look-ahead bias? (highest-stakes)
**VERDICT: SAFE.**
The position matrix is built by lagging each symbol's signal by one bar on its **own** calendar, then applying next-bar returns:
- `agent/backtest/engines/base.py:191` — `# Build position matrix: shift on each symbol's OWN calendar, then fill`
- `:199` — signal reindexed to own index
- `:203-206` — `# shift(1) + fillna(0): prepend 0, drop last` → `shifted_vals[0] = 0.0; shifted_vals[1:] = sig_vals[:-1]`. **Signal computed at bar `t` becomes the position held at bar `t+1`.**
- `:221` — `ret = close.pct_change().fillna(0.0)` (return from `t-1→t`).
Because position at `t` derives from the signal at `t-1` and is multiplied against the `t-1→t` return, no future information reaches a trade. The intraday execution loop is separately proven causal: `agent/tests/test_execution_causality.py::test_decision_bar_close_cannot_change_open_position_size` asserts that shocking a symbol's decision-bar close (100→200) does **not** change the size opened for a rotated-in symbol (`assert shocked_b.size == baseline_b.size`). Portfolio-optimizer look-ahead was also fixed across all 5 optimizers (README News 2026-07-13) and there is `test_optimizer_causality.py`. Residual caution: the `optimizer` hook (`base.py:223-224,246`) receives full `ret`/`pos`/`dates` and a malicious/naive optimizer *could* peek; verify any custom optimizer. Overall: **SAFE** for the built-in engines.

### Q5 — Are SMC calculations configurable?
**VERDICT: YES — parameterized, not hardcoded (built on the `smartmoneyconcepts` library).**
`SignalEngine.__init__(self, swing_length: int = 10, close_break: bool = True)` (`agent/src/skills/smc/example_signal_engine.py:918`). Params flow into `smc.swing_highs_lows(ohlc, swing_length=self.swing_length)` (`:975`) and `smc.bos_choch(ohlc, swing_highs_lows=swing_hl, close_break=self.close_break)` (`:978`). FVG via `smc.fvg(ohlc)` (`:135`), combined into buy/sell (`:146-147`). Documented params in `agent/src/skills/smc/skill.md` (Parameters section). A fork can subclass and expose additional knobs (e.g. FVG mitigation, OB lookback) — the library call sites are the extension points.

### Q6 — Can market data be sourced directly from Binance?
**VERDICT: YES — a dedicated Binance loader already exists.**
`agent/backtest/loaders/binance_loader.py` — `@register class DataLoader(CcxtDataLoader)` with `name = "binance"`, `markets = {"crypto"}`, `requires_auth = False`; `_get_exchange` uses `ccxt.binance` (spot) / `ccxt.binanceusdm` (USD-M perps) and ignores `CCXT_EXCHANGE` (`binance_loader.py:724-745`). It sits **alongside** OKX in the crypto fallback chain (`source="binance"` explicit, or `source="auto"` fallthrough). The generic `ccxt_loader.py` also defaults to Binance (`ccxt_loader.py` docstring `:578-582`), public data, no API key. Path to add more: register another `@register` subclass — no new plumbing needed.

### Q7 — Are order requests idempotent?
**VERDICT: PARTIAL — strong no-double-issue guarantees, but no explicit client order ID / dedup key.**
Live orders are explicitly **non-repeatable**: `repeatable = False` mirrors the no-retry stance in `MCPServerAdapter._call_tool` — "a live order must never be silently re-issued" (`order_guard.py` docstring `:379`). A daily count is consumed only on a confirmed non-error ALLOW (`sdk_order_gate.py:_allow` `:528-547`; `increment_daily_count` at `:542`), under a `daily_order_lock` (`:71`). However, evidence shows **no client-generated `client_order_id`/dedup token** passed to brokers; dedup is behavioral (no auto-retry) rather than a broker-side idempotency key. **Close this before live** (see gaps).

### Q8 — Can position sizing be controlled outside the LLM?
**VERDICT: YES — sizing is deterministic and bounded outside the model.**
In backtest, sizing is engine-side: signals are clipped to `[-1, 1]` (`base.py:202`), normalized so gross exposure ≤ 1 (`base.py:226-227` `scale = pos.abs().sum(...).clip(lower=1.0); pos = pos.div(scale)`), and rounded via `round_size` (engine method, `test_execution_causality.py:_FrictionlessEngine.round_size`). In live, the mandate caps single-order notional, total exposure, leverage, and daily count — enforced by `check_mandate` (`enforcement.py:455`) with normalization on the **larger** of explicit notional and `quantity × price` (`order_guard.py:376`). A fork can inject its own deterministic sizing in the engine and/or tighten the mandate; neither depends on the LLM.

### Q9 — Can an agent trigger execution WITHOUT unrestricted broker access?
**VERDICT: YES — there is a hard gateway boundary; the agent never holds a blank check.**
Live orders pass through a single fail-closed enforcement gate before any broker call, in fixed order: `load_mandate` → expiry → `halt_flag_set` → notional normalization → read positions/balance via the broker's own READ funcs → `check_mandate` (`sdk_order_gate.py:41-62` docstring; `order_guard.py:8-16`). `check_mandate` (`enforcement.py:455-464`) returns a `BreachEvent` (`:138`) or `None`(ALLOW); structural breaches (`universe`/`instrument`, `:78-79`) DENY outright, and the **agent may never edit the mandate** (`enforcement.py:143-145`; there is a `test_no_set_mandate_tool.py`). The mandate itself is committed only by an explicit user click (`mandate/commit.py`), and there is a broker-side funding ceiling the agent "physically cannot breach" (`enforcement.py:135-137`). So the agent holds credentials only via connector profiles it cannot re-scope, and every write is bounded + audited.

### Q10 — Can the system create a full audit trail?
**VERDICT: YES — a dedicated, append-only, compliance-grade ledger with 3 sinks and redaction.**
`agent/src/live/audit.py` writes every live action (`order_placed`, `order_cancelled`, `order_rejected`, `mandate_committed`, `breach`, `halt_tripped`, `halt_cleared`) as one immutable JSONL record to `<runtime_root>/live/audit.jsonl` (`audit.py:430-434,493-501`). It fans out to 3 append-only sinks: the compliance ledger (always), the per-run `TraceWriter` (`type="live_action"`), and the SSE `event_callback` (`"live.action"`) (`audit.py:440-446`). Every record is scrubbed by `redact_payload` **before** any sink so OAuth tokens/account numbers/PII become `[redacted]` (`audit.py:448-454`). `mandate_snapshot_ref` + `consent_record_ref` chain each order back to the exact authorizing user click (`:436-438`). Redaction has its own test (`test_audit_redact.py`).

---

## 4. Backtester Look-Ahead Safety Assessment

**VERDICT: SAFE** (built-in engines).
- Positions are the signal lagged one bar per-symbol-calendar (`base.py:203-206`), applied to next-bar `pct_change` returns (`base.py:221`) — causally correct.
- Cross-symbol rotation and decision-bar/execution ordering are regression-tested to be free of look-ahead (`test_execution_causality.py`).
- Portfolio optimizers had a look-ahead fix across all 5 (README News 2026-07-13) with `test_optimizer_causality.py`.
- Event feeds have a look-ahead guard (`test_rsshub_events_lookahead.py`); fundamental factors are PIT-safe (filed-date anchoring, README News 2026-07-08).
- **Residual risk:** a *custom* optimizer plugged into the `optimizer` hook (`base.py:223,246`) or a *custom* `SignalEngine` receives full-history frames and could self-introduce look-ahead. The framework prevents leakage in its own iteration; it cannot prevent a strategy author from indexing the future. TJR strategies must be reviewed for `iloc[i+1:]`/full-series peeking.

---

## 5. Secret Handling

- **Centralized Pydantic schema.** All env vars flow through a single `EnvConfig` schema (`agent/src/config/env_schema.py`) with typed `Field(alias="...")` entries: broker/data keys (`FINNHUB_API_KEY`, `ALPHAVANTAGE_API_KEY`, `TIINGO_API_KEY`, `FMP_API_KEY`, `FRED_API_KEY`, `LONGBRIDGE_APP_KEY/APP_SECRET/ACCESS_TOKEN`, `QVERIS_API_KEY`, `FUTU_TRADE_PWD_MD5`), and API auth (`API_AUTH_KEY`, `VIBE_TRADING_API_KEY`) — `env_schema.py:161-181,232-261`.
- **CI gate against sprawl.** An AST-based CI gate forbids raw `os.getenv` / `os.environ[...]` reads **outside `config/`** (`tools/test_ci_env_var_gate.py:62-137`), so no module can quietly read a secret off the environment (README News 2026-07-10, #440).
- **Storage.** Real credentials live in `agent/.env` (Docker `env_file`) and `~/.vibe-trading/` (named volume `vibe-home`), never the repo. Docker rootfs is read-only; `.env` edits are persisted via a dedicated volume (`docker-compose.yml`, `src/api/helpers.py:_write_env_values`).
- **No leaks in logs.** Audit records are redacted before write (`audit.py:448-454`). The provider doctor prints a **redacted** provider/model/proxy snapshot (README News 2026-06-12). Security Rules (README) forbid committing keys and mandate rotation on exposure.
- **Web/API auth.** Remote (non-loopback) API/MCP access requires `API_AUTH_KEY`; SSE uses short-lived single-use tickets (README News 2026-07-13).

---

## 6. Test Coverage Snapshot

- **Location:** `agent/tests/` — **302 files**. Plus `tools/test_ci_env_var_gate.py` and frontend vitest (197 tests, README News 2026-06-05).
- **Safety-critical coverage present:** `test_sdk_order_gate.py`, `test_mandate_enforcement.py`, `test_mandate_model.py`, `test_mandate_commit_security.py`, `test_mandate_forex.py`, `test_india_mandate.py`, `test_no_set_mandate_tool.py`, `test_halt.py`, `test_killswitch_blocks_orders.py`, `test_audit_redact.py`, `test_execution_causality.py`, `test_optimizer_causality.py`, `test_rsshub_events_lookahead.py`, `test_backtest_runner_security.py`, `test_trading_connections.py`, `test_trading212_connector.py`, `test_sdk_connectors.py`, `test_binance_fallback.py`, `test_ccxt_perpetual_loader.py`, `test_ccxt_loader_bounded.py`, `test_api_live_runtime.py`, `test_cli_live.py`.
- **Assessment:** the mandate/kill-switch/audit/causality surfaces are well covered. No evidence of an idempotency/client-order-id test (consistent with Q7).

---

## 7. Reusable vs Replaceable (for the TJR project)

| Subsystem | Verdict | Reason |
|-----------|---------|--------|
| Agent framework (loop, swarm, MCP tools) | **ADAPT** | Solid, but TJR wants deterministic flow — keep the loop, restrict the toolset (drop LLM strategy authorship). |
| Skill loader | **REUSE** | Clean `SignalEngine` contract + AST sandbox; drop in approved TJR engines. |
| MCP (FastMCP + host allowlisting) | **REUSE** | Hardened, live-goal-excluded (`mcp_server.py:398`); good gateway surface. |
| Market data | **REUSE** | Binance loader already exists (`binance_loader.py`), registry-based fallback, no keys for public data. |
| Backtester | **REUSE (with custom-optimizer/engine review)** | Causally correct lag + causality tests; only risk is author-introduced look-ahead in custom code. |
| SMC | **ADAPT** | Parameterized wrapper over `smartmoneyconcepts`; extend params for TJR concepts (OB/FVG mitigation, sessions). |
| Broker / execution | **REUSE the gate, REPLACE the strategy trigger** | Mandate + kill switch + audit are best-in-class; wire TJR sizing/entry into the same fail-closed gate. |
| Logging / audit | **REUSE** | Append-only redacted 3-sink ledger with consent chain — directly usable for compliance. |

---

## 8. Safety Gaps to Close Before Any Broker Connection

1. **No broker-side idempotency key.** Add a client-generated `client_order_id` / dedup token threaded through `place_order` (both `sdk_order_gate.py:523` and the MCP path) so a network retry or crash-replay cannot double-submit. Current protection is behavioral (`repeatable=False`) only — insufficient under partial failure.
2. **Custom-strategy / custom-optimizer look-ahead.** The framework is causal, but a TJR `SignalEngine` or an `optimizer` hook (`base.py:223,246`) receives full-history frames and can peek the future. Mandate a review + a "no forward indexing" lint/test for every strategy before it runs live.
3. **Verify the paper→live profile boundary end-to-end for the target broker.** For any broker without a structural paper/live discriminator (Longbridge/Trading 212/Dhan/Shoonya) writes hard-refuse; confirm the chosen live broker (e.g. Binance/Alpaca) has a *real* structural guard (`test_sdk_order_gate.py:204/217`) and that no code path can reach `connector_module.place_order` with a live config unless the mandate + non-tripped HALT + expiry all pass.
4. **Kill switch depends on `<runtime_root>/live/HALT` filesystem availability.** In Docker the runtime root lives on a named volume; confirm the HALT path is writable/readable by an external watchdog and is NOT on the read-only rootfs, so an operator (or watchdog) can trip it even if the app is wedged.
5. **Mandate immutability + secret scope.** Confirm no fork-added tool can commit/edit a mandate (guard `test_no_set_mandate_tool.py` still passes) and that connector profiles grant least-privilege API scopes (trade-only where possible, withdrawals disabled) so an escaped agent still cannot move funds.
