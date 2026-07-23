# Lesson 42 — Verification Questions (owner: Jiv)

1. **Point-in-time reconstruction:** Confirm the backtest harness reconstructs partial (as-of) candles on every timeframe used for bias, with zero look-ahead of completed HTF candles. (TJR's #1 bar-replay objection = look-ahead.)
2. **Validation gate:** Define the forward/demo-test threshold (# trades, min win rate, min R:R, sample across regimes) that promotes a strategy from backtest to live. TJR gives none.
3. **Sampling:** For an unbiased engine backtest, deliberately sample across regimes/sessions/news conditions rather than "a random day." Confirm the harness does this.
4. **Detector validation:** Set target precision/recall thresholds for OB/FVG/sweep/BOS detectors before trusting the execution layer.
5. **Emotion factor:** Confirm that the human "psychology" caveat is out-of-scope for the automated engine (no emotion), so backtest validity for the engine hinges on look-ahead elimination, not emotional realism.
