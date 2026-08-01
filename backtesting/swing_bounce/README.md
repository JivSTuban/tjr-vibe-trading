# swing_bounce — beaten-down bounce backtest

Event-driven backtest measuring the base rate (hit rate + expectancy in R, after costs) of buying a
**beaten-down + "financially alive"** US stock with a stop/target over a swing horizon — and whether
the "alive" quality gate improves expectancy vs ungated. Reuses `value_quality` for EDGAR PIT
fundamentals + the ticker↔CIK map; adds an OHLC price loader (the trade sim needs high/low).

**Result:** see `FINDINGS.md` — **edge not proven; do not automate.** The intuitive +20%/−10%/20d
setup loses, the quality gate doesn't help, and positives are survivor-biased + concentration-driven.

## Run
```bash
uv run python -m backtesting.swing_bounce.run     # fetches ~30 names 2015-2023, runs the sweep, writes runs/<ts>/{results.json,dashboard.html}
uv run pytest backtesting/swing_bounce/tests -q   # pure-logic tests (network-free)
```

## Pieces
- `gate.py` — `financially_alive(FinYear)`: profit + positive CFO + solvent (the anti-knife filter).
- `events.py` — drop-event detection: ≤ threshold×trailing-63d-high AND oversold (RSI<35 / lower Bollinger).
- `trade_sim.py` — stop/target/time simulator over OHLC (gap-through at open; same-bar → stop first; 15bps/side).
- `metrics.py` — event-level expectancy (hit/stop/time rates, expectancy_R).
- `prices_ohlc.py` — Yahoo OHLC loader + cache.
- `run.py` — driver: event stream → gated/ungated sweep grid → SPY benchmark → survivorship stress → concentration.
- `viz.py` — offline HTML dashboard.

## Disclosed biases
- **Survivorship (severe):** Yahoo drops delisted names → the worst knives are absent → optimistic.
  The bounded run had 0 truncated events (all survivors). A survivorship-free source (Polygon $29) is
  the biggest missing piece.
- **Entry-at-close** is optimistic vs a real limit fill on a falling name.
- **Intrabar** stop/target uses a conservative "stop first" rule (coarse).
- Point-in-time fundamentals via EDGAR `filed` dates; prices ≤ t for decisions.
