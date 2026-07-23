# Verification Questions — Lesson 29: Trading Plan
owner: Jiv

1. **Daily risk budget** — What monetary value or account % should the automated system use as the daily pre-designated risk? ($100 was only TJR's example.) [r01]

2. **Trades/day cap** — Lock the default at 1/day? Allow a 2/day mode with automatic risk-halving (r03)? [r02, r03]

3. **Position sizing** — Confirm calculated sizing as default (balance × risk% ÷ stop-pips). What risk % should be used? Is fixed-lot tiering ever needed? [r04]

4. **Session window** — Confirm the trading window in explicit clock time + timezone. Is TJR's "first 90 min of NYSE open" = 09:30–11:00 ET the intended default? [r05]

5. **High-impact news blackout** — What pre/post-event blackout window (minutes) should surround CPI/NFP/FOMC/PPI? TJR only names the events, not the window. [r06]

6. **News volatility filter** — Do we implement the "points-in-a-candle" opt-out, and with what threshold per instrument? (TJR's 5pt/5min is admittedly arbitrary.) [r07]

7. **Instrument universe** — Which single instrument does the system trade first? What quantitative "profitable" gate unlocks adding a second? [r08]

8. **Daily bias derivation** — How is daily bias computed (deferred to next lesson)? Confirm before enabling the bias-alignment gate. [r09]

9. **Confluence definitions** — Liquidity sweep, BOS, FVG, OB: exact machine definitions and timeframes are deferred to Lesson 30 ("putting it all together"). Do NOT implement r09/r10(g) until that lesson is ingested. [r09, r10]

10. **Bank-holiday gate** — Which holiday calendar/source feeds the US bank-holiday check, per instrument? [r10]

11. **"Leave" filter ordering** — Confirm the AND-chain in r10 is complete and correctly ordered as hard pre-trade gates for the executor.

12. **Validation loop** — Should the ~2-week backtest + journaling requirement be enforced programmatically before a new confluence goes live, or is it advisory? [r11]
