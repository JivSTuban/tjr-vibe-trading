# Verification Questions — Day 27 (Fear) — owner: Jiv

1. **Trade cap:** Reconcile "one trade a day" (Day 27, `[06:57]`) vs "one to two trades a day, one best" (Day 25). Is the engine cap 1 (hard) or 2 (hard, 1 preferred)?
2. **Risk %:** Confirm 1% is per-trade AND effectively the daily cap given 1 trade/day `[06:57]`. If 2 trades are ever allowed, is risk 1% per trade or 1% total/day?
3. **Profitability window (critical):** Is the go-live proof "**10% total over 3 months**" `[03:36]` or "**10% per month**" `[13:19]`? These imply very different sizing/expectations. Which governs the account-state gate?
4. **Personal-vs-canonical:** These numbers are framed as TJR-personal defaults. Which later lesson (risk-management / stop-loss / take-profit / trading-plan — all teased here) fixes the CANONICAL engine constants? Do not hard-code from Day 27 alone.
5. **Funded thresholds:** The $10k capital threshold and 10%/month funded-pass target `[12:43]` are prop-firm-specific. Which prop firm's rules apply, if any, for the automated account?
6. **Fear-side guardrail:** Confirm the intended behavior is "take EVERY valid, plan-conformant setup within the risk envelope" (no skipping) — i.e. automation IS the fix for fear. `[15:39]`, `[18:12]`
