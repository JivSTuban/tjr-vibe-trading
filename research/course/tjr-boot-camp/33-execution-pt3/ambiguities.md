# Ambiguities — Lesson 33 (Execution pt.3)

All items below are low-confidence and `requires_confirmation: true`. Nothing was invented;
these are gaps or vague statements in the transcript.

## 1. FVG fill depth [07:04], [10:46]
TJR shows price "filling the imbalance completely" [10:46] in one case but enters on partial
returns elsewhere. No numeric rule (full fill vs 50% vs first touch) is given.
- confidence: low | requires_confirmation: true

## 2. "Equilibrium matching up perfectly with the FVG" [15:00]
No tolerance defined for "perfectly." Machine rule needs a price-band overlap threshold that
TJR never states.
- confidence: low | requires_confirmation: true

## 3. Leg measurement direction [19:54] -> [20:13]
TJR says "measure it from swing low to the swing high" then immediately self-corrects "swing
High to the swing low." Ambiguous which he means; likely just verbal correction (draw the
Fib/equilibrium across the impulse leg), but direction convention should be confirmed.
- confidence: low | requires_confirmation: true

## 4. Whether lower-TF confirmation is mandatory [07:26], [09:44]
Sometimes framed as required ("you scale down to find confirmation"), sometimes optional ("I
guess you could scale down for this"). Unclear if BOS confirmation is a hard gate.
- confidence: low | requires_confirmation: true

## 5. Which timeframe is "the setup" vs "the confirmation"
Examples span 15m, hourly, daily, 5m. The relationship between the HTF setup TF and the
lower confirmation TF (fixed ratio? trader's choice?) is not specified.
- confidence: low | requires_confirmation: true

## 6. Confluence threshold to trade [22:56]
"Seven confluences" is illustrative hype. No stated minimum number of confluences required to
justify an entry.
- confidence: low | requires_confirmation: true

## 7. Stop loss placement [07:35]
Only a throwaway "put your stop loss like I don't know under this low or under these lows, we
haven't covered that yet." SL rules are explicitly deferred; do NOT machine-encode from this
lesson.
- confidence: low | requires_confirmation: true

## 8. Take-profit selection [10:02], [18:02]
"Target previous draws on liquidity" — but with multiple pools present, which to choose, and
first-TP vs runner logic, is deferred to a later lesson.
- confidence: low | requires_confirmation: true

## 9. Short-side rules
Almost all examples are long. The bearish inversion (e.g. down-move example [09:13]) is
implied, never spelled out.
- confidence: low | requires_confirmation: true

## 10. News-avoidance window [06:48]
"Didn't trade because Powell was speaking" — no time buffer (minutes before/after) or list of
which events qualify.
- confidence: low | requires_confirmation: true

## ASR / jargon normalizations applied
- "liquidity Suite" / "Suite breaking" -> liquidity sweep (BOS) [06:38]
- "rank of structure" / "brake structure" / "breakup structure" -> break of structure [08:18], [22:16]
- "for Value Gap" / "favorite value Gap" / "value Gap" -> fair value gap [14:52], [19:45]
- "Balance" / "in Balance" -> imbalance [10:48]
- "Wicks into equilibrium" -> wicks into equilibrium (kept) [22:34]
- "S P" -> S&P (SP/ES) [06:48]
- "draws on liquidity" kept canonical [10:02]
