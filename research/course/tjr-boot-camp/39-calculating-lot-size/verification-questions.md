# Lesson 39 — Verification Questions (owner: Jiv)

1. **Sizing philosophy:** Should the risk engine (a) replicate TJR's set-lot (fixed lots, realized risk floats 1%→3% with stop width), or (b) recompute lots per trade to hold risk constant at 1%? These diverge materially for wide stops.
2. **pip/point value:** Source pip_value_per_lot per instrument+quote-currency+contract-size. Confirm the S&P pip-to-point ratio (he mixes "400 pips" and "4 points").
3. **Contract size config:** Confirm per-broker units-per-lot (Hankotrade=10, generic offshore=100, prop firms often 10). Make this a required, validated config field.
4. **Confident tier:** Keep disabled by default? Define the numeric "proven track record" gate before ever allowing 2% risk.
5. **De-risk triggers:** Enumerate the high-impact-news events (CPI/PPI/NFP + others?) and holiday calendar that auto-select the 0.5% tier.
6. **Risk cap:** If using set-lot, confirm the hard cap on realized risk (TJR tolerates ~3%; is that acceptable, or cap at 2%?).
7. **Cent lot / beginner mode:** Should the engine expose a cent-lot / demo mode as the default until a profitability threshold is met?
