# Lesson 47 — Verification Questions (owner: Jiv)

1. **News-move exhaustion metric:** Should the "most of the move is in the release candle" heuristic be coded as `release_candle_range / residual_session_range > X`? What X, and does it apply to both CPI and PPI (and NFP)? [ref 03:04]
2. **Authoritative timeframe for intraday bias:** For conflicting-bias rejection, is the *daily* the primary bias (with weekly only for retrace context, per lesson 49), or must all of W/D/4H/1H align? [ref 11:28 vs. lesson 49 09:56]
3. **Sweep validity threshold:** TJR says whether a "barely hits it" London-high sweep is valid is up to the trader. What pip/tick/percentage penetration should the machine require to count a liquidity sweep as valid? [ref 08:19]
4. **Building-block proximity tolerance:** How close must price be to an OB/FVG/equilibrium for the reaction to count (exact touch, within the zone, within N ticks)? [ref 14:44]
5. **Retrace-override conditions:** The retrace rule is overridden by "liquidity sweeps and change of market structure." Provide machine-checkable definitions of both so the override can be automated. [ref 04:52]
6. **GJ short template levels:** Confirm the concrete stop placement (above OB vs. above sweep high) and target-selection priority (unhit OB / resting liquidity / new-FVG start) for coding the template. [ref 08:35]
