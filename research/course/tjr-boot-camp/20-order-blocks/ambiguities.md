# Ambiguities — Lesson 20 (Order Blocks, Day 1 concept)

This is the "why" day; TJR explicitly defers "how to spot / draw" to Day 2 and
"putting it together" to Day 3. Many mechanics are therefore undefined here.

## 1. OB candle vs leg — which structure IS the order block? (confidence: low/medium)
TJR describes the OB as "that move up that causes the liquidity sweep" and "the
leg down prior to the liquidity sweep" [03:10, 08:55] — i.e. a **leg/move**. He
never states the standard SMC single-candle rule ("last opposing candle before
displacement / the last down candle before an up move"). Unresolved: is the OB
one candle or the whole initiating leg? This changes the entire detection
algorithm. → confirm in Day 2 (video ~lesson 21/22) before coding.

## 2. OB zone boundaries — body vs wick, high/low (confidence: low)
He calls it "this whole price range… where orders were filled" [03:24] but never
specifies: body (open→close) vs full candle (incl. wick), nor which high/low
anchors the zone. No measurement method given at all.

## 3. Mitigation / valid vs invalid OB — NOT DEFINED (confidence: low)
TJR never says "mitigated," "used up," "valid," or "invalid." He implies price
retraces into the OB once for a retracement entry, but gives no rule for when an
OB is consumed, how many touches invalidate it, or whether an unmitigated OB
persists. Any one-touch / mitigation logic would be pure inference.

## 4. Entry confirmation — NOT SPECIFIED (confidence: low)
No LTF confirmation, candle-close requirement, CHoCH, or trigger is stated for
entering off the OB retrace. He only says OB is his #1 POI. Do not assume a
confirmation model from this lesson.

## 5. Stop loss & take profit — ABSENT (confidence: low)
No SL placement (beyond OB high/low or wick) and no TP/RR target are given.
Standard SMC (SL beyond OB extreme) is inference only, NOT from this transcript.

## 6. "Trend" / "trend shift" definition (confidence: medium)
The "one OB per trend" rule [07:53] depends on a precise machine definition of
"trend" and "trend shift" (MSS/BOS), which is set in prior lessons, not here.

## 7. Timeframe selection for the tradeable OB (confidence: medium)
OBs are stated to exist on "every single time frame" incl. 1m [09:23], but which
timeframe the actual entry OB should come from (HTF bias vs LTF entry) is
deferred to Day 3.

## 8. News-window numbers (confidence: medium)
"34 pips," "PPI," "FOMC," "about two hours" are illustrative [11:58–12:33]; no
coded no-trade buffer (minutes before/after news) is defined.

## ASR corrections applied (jargon normalization)
- "order Cox" / "Order Box" → **order block** (OB).
- "fair value Yap" / "fair value gaps" → **fair value gap** (FVG).
- "liquidity Suite" / "Suite" → **liquidity sweep**.
- "break of structure" preserved as-is (BOS).
- "fomc" → **FOMC**; "PPI PPI" → **PPI** (ASR duplicate).
None of these are non-obvious; context makes each unambiguous.
