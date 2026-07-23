# Lesson 38 — Verification Questions (owner: Jiv)

1. **Spread buffer formula:** Is the SL buffer a flat 0.5-point floor, the broker spread for the pair, or volatility-scaled? Reconcile the 0.5-pt rule with the 4-pt live S&P example. Should it be per-instrument config?
2. **Sweep selection for SL anchor:** When bias is on a high timeframe but entry is on a low timeframe (e.g. daily-bullish, 5m execution), does SL anchor to the execution-TF sweep or a higher-TF sweep? The recap trade got stopped anchoring to the LTF sweep.
3. **R:R trigger for the elongated-stop / inner-OB exception:** confirm it uses L37's 1:1 minimum as the substitution threshold.
4. **HTF scale-down anchor:** formalize "a low one scale lower under the liquidity sweep" — which structural feature exactly?
5. **Units:** confirm point vs pip conversion for S&P (and other instruments) so the buffer and R:R are computed consistently.
6. **Holiday calendar:** which holiday/half-day set gates the no-trade rule (U.S. only, or all relevant exchanges)?
