# Backtest Interface Spec — adding a deterministic strategy

Implementation-ready contract for authoring a new `SignalEngine` and backtesting it.
All paths are repo-relative to `agent/` unless noted. Read-only survey; nothing here runs trades.

---

## 1. Strategy contract (`SignalEngine`)

There is **no base class and no protocol to subclass**. The runner discovers a strategy by
duck-typing: it imports `code/signal_engine.py` from a *run directory* and looks for a class
literally named `SignalEngine`. Discovery + validation:

- `backtest/runner.py:928` — `engine_cls = getattr(signal_module, "SignalEngine", None)`
- `backtest/runner.py:504-521` — `_validate_signal_engine_class()`: `__init__` must be callable
  with **no required args** (every param needs a default, so the runner can do `SignalEngine()`),
  and `generate` must be callable.
- `backtest/engines/base.py:499` — the engine calls `signal_map = signal_engine.generate(data_map)`.

**Required signatures** (from the shipped example, `src/skills/smc/example_signal_engine.py:56-110`):

```python
class SignalEngine:
    def __init__(self, swing_length: int = 10, close_break: bool = True): ...   # all params defaulted
    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]: ...
```

- **Receives** `data_map`: `{symbol -> OHLCV DataFrame}`. Each frame has columns
  `open/high/low/close/volume` (plus optional `vwap/amount/fund:*/event_score`) and a **DatetimeIndex**.
  It is **single-timeframe** — one frame per symbol at the run's `interval`. There is no built-in
  multi-timeframe argument (see gotcha).
- **Returns** `{symbol -> pd.Series}` of position signals aligned to each frame's index:
  `1 = long, -1 = short, 0 = flat`. `base.py:500-513` hard-rejects any non-`dict` / non-`Series`.
- Values are **clipped to [-1, 1]** then **shifted +1 bar** (next-bar-open execution) and normalized
  so `sum(abs(weights)) <= 1.0` — see `_align()` at `base.py:199-207,226-227`. Emit the signal on the
  bar the setup *confirms*; the engine handles the lag. Do **not** pre-shift yourself.

### AST sandbox (the `base.py:203-206` the audit referenced is the SANDBOX in `runner.py`)
`runner.py:_validate_signal_engine_source` (`:470`) + `_scan_runtime_reachable` (`:431`) parse the file
before import and reject, along the code path reachable from `SignalEngine.generate`: network/subprocess
imports (`requests`, `socket`, `subprocess`, `urllib`, `httpx`…), `os.system`/`getenv`/`environ`/`popen`/
`spawn*`/`exec*`, `eval`/`exec`/`compile`/`__import__`, `getattr(os, …)` indirection, decorators, and
file writes via `open(mode=...w/a/x/+)`. `import requests` is only tolerated inside helpers the engine
never calls (e.g. a `__main__` demo). Keep `generate()` pure: pandas/numpy/`smartmoneyconcepts` only.

---

## 2. Backtester entry point

**Run-directory convention.** A backtest is a directory containing:
- `config.json` — validated by `BacktestConfigSchema` (`runner.py:68-161`).
- `code/signal_engine.py` — your strategy.
Artifacts (`equity.csv`, `trades.csv`, `metrics.csv`, `positions.csv`, `run_card`) are written to `<run_dir>/artifacts/`.

**Entry points:**
- CLI: `python -m backtest.runner <run_dir>` (`runner.py:869 main()`, `:1266`).
- MCP/programmatic: `src/tools/backtest_tool.py:run_backtest(run_dir: str) -> str` (spawns the runner as a subprocess with a 300s timeout).
- Data-only helper: `runner.py:fetch_data_map(config) -> DataFetchResult` (`:1141`).

**Engine call (the real work):** `backtest/engines/base.py:458`
```python
BaseEngine.run_backtest(config, loader, signal_engine, run_dir, bars_per_year=252) -> Dict[str, Any]
```
Routing: `runner._create_market_engine` (`:979`) picks the engine by symbol/source — crypto symbols
(`okx`/`ccxt`/`binance`, or `*-USDT`) → `CryptoEngine`. Cross-market → `CompositeEngine`.

### config.json keys (`runner.py:68-84`)
`codes: [str]` (required, non-empty), `start_date`, `end_date` (YYYY-MM-DD), `source` (default `tushare`;
must be in `VALID_SOURCES` — includes `binance`, `okx`, `ccxt`, `auto`), `interval` ∈
`{1m,5m,15m,30m,1H,4H,1D}` (default `1D`), `engine` ∈ `{daily,options}`, `initial_cash` (>0, default 1e6),
`leverage`, `benchmark`, `optimizer`. Optional `fundamental_fields`, `event_feeds`, `validation`.

### Fees / slippage / spread — where configured
Per-engine, read from `config`. For crypto (`backtest/engines/crypto.py:36-39`):
`maker_rate=0.0002`, `taker_rate=0.0005`, `slippage=0.0005`, `funding_rate=0.0001`.
Model: opens pay taker, closes pay maker (`crypto.py:51-58`); slippage is
`price * (1 + direction * slippage_rate)` (`:60-62`). There is **no explicit bid/ask spread** knob —
model spread by widening `slippage`. Override hooks live on `BaseEngine`: `calc_commission`,
`apply_slippage`, `round_size`, `can_execute`, `on_bar` (`base.py:372-427`).

### Metrics you get for free (`backtest/metrics.py:344-362`, via `calc_metrics`)
`total_return, annual_return, max_drawdown, sharpe, calmar, sortino, win_rate, profit_loss_ratio`
(payoff = avg_win/avg_loss), `profit_factor` (gross_profit/gross_loss), `max_consecutive_loss`,
`avg_holding_days, trade_count, benchmark_return, excess_return, information_ratio, avg_turnover,
total_turnover`. Plus `by_symbol` and `by_exit_reason` breakdowns (`base.py:578-579`).
**Not computed:** expectancy and R-multiples — derive from `trades.csv` (`pnl`, `return_pct`) if needed.

---

## 3. Market data loader (`binance_loader.py`)

`backtest/loaders/binance_loader.py:24` — `class DataLoader(CcxtDataLoader)`, `name = "binance"`,
`markets = {"crypto"}`, `requires_auth = False`. It only overrides exchange selection
(`_get_exchange`, `:31`): `spot` → `ccxt.binance`, `swap` → `ccxt.binanceusdm`. The **fetch signature is
inherited** from `backtest/loaders/ccxt_loader.py:223`:

```python
DataLoader.fetch(codes: List[str], start_date: str, end_date: str, *,
                 interval: str = "1D", fields=None,
                 bracket_artifacts=None, require_brackets=False) -> Dict[str, pd.DataFrame]
```

- **Symbols / spot vs futures:** `BTC-USDT` → spot; `BTC-USDT-PERP` → USD-M perpetual (routed to
  `binanceusdm`). Parsing: `_parse_ccxt_symbol` (`ccxt_loader.py:57-66`). PERP stays zero-credential.
- **Bar count:** you don't pass a count — you pass `start_date`/`end_date`; the loader paginates
  (`_INTERVAL_MAP`, `ccxt_loader.py:31`). Public data, no API key.
- **Returned schema:** `{symbol -> DataFrame[open,high,low,close,volume]}` with DatetimeIndex.
- **Multiple aligned timeframes (HTF bias + LTF entry):** there is **no multi-TF loader**. Call
  `fetch(...)` twice with different `interval` (e.g. `"4H"` and `"15m"`), then align yourself — e.g.
  `htf.reindex(ltf.index, method="ffill")`. The backtest engine only runs on ONE `interval`, so a
  multi-TF strategy must fetch the HTF frame *inside* `generate()` — but the sandbox blocks network
  calls there. Practical path: request both intervals as separate symbols is not supported; instead
  compute HTF features by resampling the single provided frame inside `generate()`
  (`df.resample("4H").agg(...)`) — pure-pandas, sandbox-safe.

---

## 4. SMC primitives already available (`smartmoneyconcepts`)

`from smartmoneyconcepts import smc`. Live call examples in
`src/skills/smc/example_signal_engine.py:127-135`:

```python
swing_hl  = smc.swing_highs_lows(ohlc, swing_length=self.swing_length)   # :127
bos_choch = smc.bos_choch(ohlc, swing_highs_lows=swing_hl, close_break=self.close_break)  # :130
fvg       = smc.fvg(ohlc)                                                # :135
# columns used: bos_choch["BOS"], bos_choch["CHOCH"], fvg["FVG"]  (:138-140)
```
Also available in the library: `smc.ob(...)` (order blocks), `smc.liquidity(...)`, `smc.previous_high_low(...)`.
`ohlc` must be exactly the `open/high/low/close/volume` columns (`example:95-96`).
Params: `swing_length` (int, larger → fewer/stronger swings; example default 10, `min_bars = swing_length*2`),
`close_break` (bool, require a *close* through the level to confirm BOS/ChoCH).

---

## 5. Test layout

Tests live in `agent/tests/` (`pytest`, flat `test_*.py`). Closest patterns to copy:
- `agent/tests/test_crypto_engine.py` — engine-rule unit tests; `_make_engine(**overrides)` builds a
  `CryptoEngine` from a config dict, `_make_bar()` builds a `pd.Series` bar; classes group by method
  (`TestCanExecute`, fees, slippage, liquidation). **Follow this for testing your signal math.**
- `agent/tests/test_metrics.py` — asserts on `calc_metrics` output keys.
- `agent/tests/test_run_card.py:282` and `test_realized_turnover.py:76` — define an inline stub
  `class SignalEngine: def generate(self, data_map): ...` and drive `run_backtest` end-to-end with a
  fake loader. **Follow this for an end-to-end backtest test.**
- `agent/tests/test_backtest_runner_security.py` — how the AST sandbox is exercised (what `generate()`
  bodies get rejected); read before writing anything network-touching.

Run: `cd agent && pytest tests/test_crypto_engine.py`.

---

## 6. Minimal worked example (exists in-repo)

`src/skills/smc/example_signal_engine.py` is a complete, sandbox-passing strategy: `__init__` with
defaulted params, `generate(data_map) -> {code: Series}` returning `1/-1/0` from SMC ChoCH→BOS→FVG,
and a `__main__` demo. Skill doc: `src/skills/smc/SKILL.md`.

### Smallest correct path for a NEW deterministic strategy
1. `mkdir -p <run_dir>/code`.
2. Write `<run_dir>/code/signal_engine.py` — copy the SMC example's class shape; put all logic in
   `generate()` and helpers it calls; **no network / file writes / os.system inside that call graph**.
3. Write `<run_dir>/config.json`, e.g.
   `{"codes":["BTC-USDT"],"start_date":"2023-01-01","end_date":"2024-01-01","source":"binance","interval":"4H","engine":"daily","initial_cash":100000,"slippage":0.0005}`.
4. `python -m backtest.runner <run_dir>` (or `BacktestTool`).
5. Read metrics from stdout JSON and `<run_dir>/artifacts/metrics.csv` / `trades.csv`.

---

## Biggest integration gotcha

**The engine runs on exactly ONE timeframe and pre-lags/normalizes your signal — and the sandbox
forbids fetching a second timeframe inside `generate()`.** For an HTF-bias + LTF-entry strategy you
cannot load a 4H frame from inside the strategy (no network allowed there). Do HTF via
`df.resample()` on the single provided LTF frame *inside* `generate()`, and emit the confirmation-bar
signal WITHOUT shifting it yourself — `_align()` (`base.py:199-207`) already applies the +1-bar lag,
clips to [-1,1], and rescales weights. Double-shifting or returning raw prices/booleans instead of a
{-1,0,1} `pd.Series` are the common breakages (`base.py:500-513` rejects wrong return types).
