# Verification Questions — Lesson 07 (owner: Jiv)

1. **Subset validity:** TJR says {liquidity sweep, BOS} alone is tradeable, and {order block, BOS, SMT} is another valid combo [04:33-05:33]. For the auto-system, which component subsets do we authorize as complete setups, and is there a minimum-confluence count? (Downstream liquidity/FVG/OB lessons should constrain this.)
2. **SMT divergence:** TJR explicitly does not trade SMT and disclaims knowing it [05:33-05:43]. Confirm the TJR ruleset should exclude SMT entirely, so no downstream rule assumes it.
3. **"Don't follow every rule" boundary:** Confirm the safety-critical reading of r04 — i.e., the operator may choose WHICH components to enable, but every condition of an ENABLED setup remains mandatory. Is that correct, or does TJR intend looser within-setup discretion?
4. **London session fake-out:** Is the GBPJPY (GJ) London-open fake-out a formal named setup we must implement, and where in the course (08/10/12 liquidity?) is its entry/SL/TP/session-time defined? [06:52-07:27]
5. **Journaling layer:** Should the confidence/emotion log (homework, r05) be wired into the trader dashboard as a per-session prompt, and should low logged confidence ever soft-gate manual execution?
6. **Peer-comparison guardrail (r03):** Do we suppress any peer/leaderboard comparison surfaces to avoid tilt, per [08:57-09:38]?
