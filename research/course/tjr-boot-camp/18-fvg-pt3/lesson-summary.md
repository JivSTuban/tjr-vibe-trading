# Lesson 18 — Fair Value Gap (Part 3): Putting It All Together

**Video:** https://youtu.be/qecF411R83s · **Duration:** 17:47 (1067s) · **Primary topic:** concept (entry model / strategy integration)

This is the third and final lesson of the FVG series. TJR states the goal explicitly: this video is a **recap** of the first two FVG episodes plus a demonstration of **how to combine FVG with the other building blocks (liquidity sweep + break of structure + HTF bias) to actually take trades** [0:22–0:31]. He moves forward assuming full understanding of liquidity sweep, trend, break of structure (BOS), and fair value gap [1:19–1:29]. He notes the full strategy and executions have NOT been formally taught yet — this is showing how the pieces already combine [8:01–8:17].

---

## What TJR teaches

### The core entry model (the "building blocks")
TJR repeatedly names the same sequence of pieces that form a trade:
**liquidity sweep → break of structure → imbalance (FVG) fill → break of structure** [7:49–7:54, 5:26–5:47].

The full multi-timeframe workflow he demonstrates:
1. **HTF bias / structure first.** Establish direction from the higher timeframe. In the recap example he cites HTF break of structure + "trend shift" as the first confirmation before doing anything [3:56–4:04]. In the gold/GBPUSD example he checks the daily: "we're bullish because we got that daily break of structure to the upside" [11:28–11:32].
2. **Liquidity sweep / grab** aligned with that bias (e.g. HTF highs swept before a short) [6:00–6:13, 10:03–10:12 "spike up into that liquidity area"].
3. **Break of structure on a mid timeframe (15m / 1h / 4h)** — confirms the move / trend shift [2:04–2:07, 6:11–6:15].
4. **Imbalance (FVG) marked off; wait for price to RETRACE and FILL the FVG** [3:22–3:44, 4:06–4:08]. TJR: mark out ALL fair value gaps in the leg and look for a reaction [3:25–3:31, 6:27–6:33]. Any FVG price pushes fully past is discarded — "the second we push past this, no longer considering it" [9:45–9:53].
5. **Scale DOWN to a lower timeframe** once the HTF imbalance is being filled [4:06–4:15]. His demonstrated chain: 15m HTF context → 5m break of structure → 1m for the "prime time entry" [4:04–4:18, 3:48–3:52].
6. **Confirmation = a lower-timeframe break of structure** off the FVG fill. This is the actual entry trigger — "we get a break of structure right here off of this candle close, boom you can enter into short position off of that" [4:27–4:33].

### FVG as a RETRACEMENT tool, not the entry itself (key distinction)
This is the central rule of the lesson. TJR: "with imbalances, all I like to do... I use them for retracements" [5:23–5:25]. **He does NOT enter the moment price taps/hits the FVG** [4:52–5:07] — entering directly on the FVG tap would have gotten him stopped out [5:05–5:11]. Instead the FVG tells him *where* price will retrace to; he then waits for an LTF break of structure as the trigger [5:36–5:47]. Explicit summary: "to me imbalances are mainly used for **retracement tools** to figure out where market wants to retrace to, and then from there I find other reasoning on why I want to get in — whether it's an order block, break of structure, or a liquidity sweep within an imbalance then a break of structure. **I use it as more of a confirmation rather than an entry**" [5:56–6:13 / 15:56–16:13].

### Stop loss
Placed **beyond the swept highs/lows** that preceded the entry. Short example: "stop above these highs" [7:14–7:18].

### Take profit / targets
Target **previous areas of liquidity** in the direction of the trade — previous highs/lows, accumulation zones, and opposing imbalances [7:18–7:31, 10:26–10:41]. He targets multiple liquidity pools scaling out; in the SP500 example both TPs (liquidity + a small order block) were hit before the remaining position stopped out at break-even [4:36–4:48]. TP can also be set at the **start / 50% (equilibrium) / end of an opposing imbalance** — "the start of the imbalance, the 50 of the imbalance, the end of the imbalance, whatever you want to do" [10:32–10:41].

### Timeframe combinations demonstrated
- SP500 recap: 15m (HTF context/imbalance) → 5m imbalance → 1m entry [2:04, 4:04–4:18].
- GJ (GBPJPY): 15m BOS + sweep → 5m BOS to enter [6:11–6:15, 6:36–6:38, 7:09–7:14]; also references 1h broke structure [6:50–6:52].
- Gold/GBPUSD: 4h BOS + imbalance → 15m BOS to enter [9:09–10:20]; also daily bias, 1h imbalance prioritized [11:28, 12:03–12:20].

### FVG "fully filled" nuance
He notes an FVG can already be filled by a later wick — if a wick reaches across the gap, "this isn't even an imbalance we're waiting for" [12:12–12:20]. He re-locates the true unfilled imbalance for the entry.

### Psychology / process notes
- **Only trade off market open** (or after market open) — no pre-market trades [3:08–3:20].
- Encourages re-watching prior videos; "nothing bad about putting in extra work" [1:33–1:47].
- Warns against getting scared out on small retraces before TP hits [14:22–14:37].
- Reminds this is easier in hindsight; practice + live watching required [15:18–15:28].

### Series roadmap (cross-lesson)
Next concept: **order blocks** (same 3-part format: explain / spot / put together), then **equilibrium**, then **strategy** [16:23–16:53].

---

## Codex interpretation (inference toward machine rules — NOT TJR's words)

- The entry model can be encoded as a **state machine** requiring, in order: (a) HTF bias direction set, (b) liquidity sweep aligned with bias, (c) mid-TF BOS in bias direction leaving an FVG, (d) retrace that fills (or partially enters) that FVG, (e) LTF (5m/1m) BOS in bias direction = ENTRY TRIGGER. Missing any step = no trade.
- TJR never gives a numeric fill threshold (edge vs 50% vs full). The trigger is the LTF BOS, not a fixed price inside the FVG — so entry price = fill/close of the LTF BOS candle, NOT a fixed FVG level. This must be confirmed (ambiguity).
- SL = beyond the sweep wick / swept high-low that created the setup. TP = nearest opposing liquidity, scaling out at multiple pools, move remainder to break-even. No numeric R:R given — he only says a raw FVG-tap entry gives "not a good risk reward," implying the retrace-then-BOS waits for a better R:R (ambiguity: threshold undefined).
- FVG has TWO roles that must be distinguished in code: **(1) draw-on-liquidity / retracement magnet** (where price returns to) and **(2) confirmation zone** (entry only after LTF BOS inside/after it). It is NOT a standalone entry signal.
