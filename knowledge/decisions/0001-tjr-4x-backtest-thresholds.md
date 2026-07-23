# Decision 0001 — TJR 4X backtest thresholds (approved-for-coding)

**Date:** 2026-07-23 · **Approved by:** Jiv (owner) · **Scope:** backtest research only — NOT live/testnet approval.

This promotes a **single** setup (the "4X strat", derived from lesson 54) from `proposed` to **`approved-for-coding`** (PRD §13 lifecycle) for the purpose of measuring its historical edge. It does **not** approve the rule for shadow/testnet/live. Values chosen resolve some `knowledge/conflicts/OPEN_QUESTIONS.md` items **for this backtest only**; the underlying course rules remain `proposed`.

## Approved parameters
| Parameter | Value | Source / rationale |
|---|---|---|
| Instrument | `BTCUSDT` USDⓈ-M **perpetual futures** | PRD §15 example; allows shorts + leverage TJR's model uses |
| HTF bias timeframe | `1D` | L34–36 daily bias is authoritative for intraday |
| Setup + sweep timeframe | `15m` | crypto-adapted (TJR taught 5m on FX); fewer false sweeps |
| Entry timeframe | `5m` | scale-down execution (L35) |
| Swing point | pivot high/low, **3 bars each side** | resolves OPEN_QUESTIONS #1 ("prominent" undefined) for backtest |
| Liquidity sweep | wick pierces the swing level **and** a body closes back beyond it **within 1 bar** | body-close confirmation (L06); resolves sweep-threshold gap |
| Confirmation | body-close **BOS/MSS** after the sweep (wick alone ≠ BOS, L06) | core primitive |
| Entry trigger | price returns into an **OB or FVG** left by the displacement leg | bare sweep+BOS insufficient (L41/L46) |
| Stop loss | just beyond the sweep extreme **+ 0.1% buffer** | L38 (SL = invalidation beyond the sweep, not the entry candle) |
| Take profit | **fixed 2R** (single TP) | L37 min 1:1; 2R chosen for a clean first-pass win-rate/expectancy |
| Risk per trade | **1%** (sizing only; not compounded assumptions) | L13/L39 normal risk |
| Direction | bias-aligned only (long in bullish daily bias, short in bearish) | L50 lesson: don't fight HTF |

## Defaults I set (adjust anytime — documented, not silently assumed)
- **History:** all available BTCUSDT perp OHLCV; **last 20% held out** as out-of-sample.
- **Costs:** taker fee `0.04%`/side + `0.02%` slippage assumption (tunable).
- **Session/news gating:** **DISABLED for v0** — TJR's London/NY + CPI/PPI model doesn't map to 24/7 crypto. This is itself an open question; a session-gated variant comes later.

## Explicitly still UNRESOLVED (do not read this backtest as validating the strategy)
Equilibrium reference-swing, multi-TP/scale-out (L54 real exit), the 30-min-high sweep precondition (L55), news correlation, and the 1–3% vs 1% risk question all remain `proposed` in OPEN_QUESTIONS. A profitable v0 backtest is a **signal to invest in resolving those**, not a green light.
