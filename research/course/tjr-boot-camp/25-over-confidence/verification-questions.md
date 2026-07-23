# Verification Questions — Day 25 (Over Confidence) — owner: Jiv

1. **Trade cap scope:** Is the "1-2 trades a day" cap `[04:40]` per calendar day or per session (London/NY)? Confirm before wiring the risk engine.
2. **Session-open window:** What exact time/timezone defines the "market open" high-probability window `[04:16]`? Cross-reference the session/kill-zone lesson — do not use a number invented here.
3. **News blackout:** Which events trigger a no-trade window (FOMC, Fed-chair speeches, CPI, PPI, NFP?) and what is the window (minutes before/after, timezone)? `[16:13]` only gives Powell as an example. Needs a dedicated news lesson.
4. **Per-trade risk %:** This lesson gives NO risk % `[10:00]`. Which lesson defines the actual fixed risk % / max drawdown? Confirm so R:R and sizing rules are grounded.
5. **Demo/scale gate:** What sample size or win-rate qualifies as "proven profitable" before scaling size or going live `[11:54]`? Not quantified here.
6. **Win-streak rule:** Confirm the intended behavior is "never scale up on wins" (no counted trigger) vs a specific streak length.
