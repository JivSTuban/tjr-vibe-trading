# Lesson 38 — Ambiguities

- **Spread buffer: 0.5 pt vs 4 pt.** He states a 0.5-point minimum buffer as the rule, but his live S&P trade used a **4-point** buffer. These are not reconciled — is 0.5 pt the universal floor and 4 pt just that instrument's need, or is buffer always instrument/volatility-scaled? Needs a single formula.
- **Which sweep anchors the SL when several exist.** In the recap he had a bullish DAILY bias but anchored the SL to a 5m/1m sweep, and got stopped even though daily bias played out. It's unclear whether the SL should anchor to the execution-TF sweep (tighter, more stop-outs) or a higher-TF sweep (wider, fewer stop-outs). He even says "maybe we should have covered ourselves by putting price lower."
- **R:R threshold for the elongated-stop exception.** L38 says "terrible risk reward" triggers substituting an inner OB, but gives no number. The 1:1 floor is only stated in L37.
- **"Extra safe" scale-down.** The HTF exception ("one scale lower under the sweep") is described qualitatively; the exact lower-structure feature to anchor to is not formalized.
- **Points vs pips for S&P.** He uses "points" and "Pips" loosely for S&P; L39 clarifies S&P is usually in points and a pip < a point. Reconcile units before coding the buffer.
- **ASR notes:** "liquidity Suite/Sweet" = liquidity sweep; "breaker structure" = break of structure; "de-risk" spelled "d-risk"/"dearest"; "hanko/hanco trade" = Hankotrade broker. Set-lot-size details ("100 lots", "10 units per lot") are previewed here but fully covered in L39.
