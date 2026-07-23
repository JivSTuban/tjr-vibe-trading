# TJR Boot Camp — OPEN QUESTIONS (Human-Review Worklist)

> Every unresolved ambiguity, definitional conflict, and automation blocker aggregated from all lessons' `ambiguities.md` + `verification-questions.md`, deduped and grouped.
> Citations use folder index `LNN` = `research/course/tjr-boot-camp/NN-<slug>/`.
> **None of these may be silently resolved.** Each blocks safe automation of the corresponding strategy stage. Nothing downstream is approved until a human answers these.

---

## A. Structure & Entry

1. **"Prominent" high/low is undefined.** TJR: "most importantly PROMINENT highs and lows… what is prominent varies from timeframe to timeframe — just look at the chart" (L12). No numeric prominence/pivot-strength formula. **Blocks:** liquidity detection, target selection, sweep identification — the whole entry chain keys off which levels count.

2. **Sweep penetration / overshoot threshold undefined.** Sweep = stops taken "by a couple of pips" then reverse (L08 `[04:14]`); "exact overshoot threshold undefined." How far may a wick exceed a swing and still be "just a sweep" vs a real close-through? (L06). **Blocks:** distinguishing sweep from BOS deterministically.

3. **BOS body-close: strict-greater vs equal, and minimum penetration.** Is `close > swing` strict, or `>=` at the exact price? Any minimum distance beyond the swing? (L06 `[07:54]`). **Blocks:** the load-bearing confirmation gate.

4. **Swing definition: literal 2-candle vs structural.** TJR's verbatim rule is a 2-candle high/low (L06 `[02:15]`), but his drawn examples appear to use larger structural swings. 2-candle over-generates. Doji/equal-open-close direction undefined. **Blocks:** every swing-dependent step.

5. **BOS vs MSS vs CHoCH labeling.** TJR treats BOS = MSS = market-structure-shift = trend-shift as synonyms, always reversal, and never uses CHoCH (L06 `[01:15]`). Standard SMC splits BOS(continuation) from CHoCH/MSS(reversal). PRD §14 scores "market-structure shift" as its own 15-pt component. **Blocks:** mapping his term onto the scorer; must confirm whether his BOS = SMC CHoCH.

6. **FVG-fill definition & 3-candle boundaries.** The 3-candle detection rule / gap edges are deferred, not stated verbatim (L14). Is "filled" = touch near edge, reach 50%, or full fill? Must the FVG sit fully inside the discount or is partial overlap enough? (L26 `[10:03]`). **Blocks:** FVG detector and the secondary-entry trigger.

7. **Order block: "leg/move" vs single candle; which edge to use.** TJR frames OB as "the move prior to the sweep," NOT the SMC last-opposing-candle; that single-candle reading is codex inference (L20 `[03:10]`, requires_confirmation). Enter/target near edge, far edge, or midpoint? — used inconsistently. **Blocks:** OB detection and OB-based entries/targets.

8. **Displacement is never quantified.** It is a 10-pt PRD scorer component but TJR gives no candle-size / body-ratio / ATR threshold; only "a large candle" (L14). **Blocks:** the displacement score.

## B. Risk & Sizing

9. **⚠ Per-trade risk %: extracts say 1–3%, task brief says 1%/0.5%/2%-forbidden.** L13 teaches "1–3% per trade, preferred 1–3% per DAY" (L13 `[03:42]`, `[10:56]`); L39 grounds a **0.5% de-risk** tier (L39 `[13:02]`). The brief's "1% normal / 2% forbidden-for-students" caps are **NOT found verbatim** in the extracts. **Conflict — do not code either version.** Human must set the canonical risk ladder.

10. **Set-lot vs constant-risk design choice.** L39 gives a constant-risk lot-size formula `lot = round(balance×risk% / (SL_pips × pip_value_per_lot), 2)` (L39 `[02:14]`), but `pip_value_per_lot` per instrument/quote currency is delegated to an external calculator, not taught. Whether the system sizes by constant-% risk or fixed lots is a design decision. **Blocks:** the sizing engine.

11. **Points vs pips on the S&P / instrument unit handling.** SL/TP taught in "pips" for FX but the S&P moves in points; conversion and per-instrument tick/pip value are never reconciled in-course. **Blocks:** lot sizing and SL/TP math for SPX/gold.

12. **Spread-buffer size for the stop.** SL = "beyond the sweep" + buffer, but the buffer magnitude is never quantified (L38, L16). **Blocks:** exact SL placement.

13. **TP 1:1 — hard reject or soft flag; measured to TP1 or blended.** L37 `[06:39]` "minimum one to one… kind of the goal." **Blocks:** the reward-to-risk gate (PRD 5 pts, mandatory).

## C. Sessions & News Timing

14. **Session open + news clock times & timezones never stated.** Asian / London / New York and "NYSE open" are named but with **no start/end times and no timezone** (L34 `[05:39]`, `[08:33]`). L55 adds a "30-minute high/low" sweep with no anchor time. **Blocks:** the approved-session gate (PRD 10 pts) and 30-min-sweep detection.

15. **News-avoidance strength & event list.** Not-trading a Powell/high-impact day is framed as preference ("probably wouldn't want to"), not an absolute rule (L34 `[04:15]`). "High impact" enumerated only loosely (red/orange folders; CPI/PPI/NFP per spec); exact blackout window (minutes before/after) not given (L19, L39). **Blocks:** the news blackout automation.

16. **Instrument scope of session logic.** Session-timing claims are stated specifically for the S&P; whether NY-session logic transfers to gold/FX is not addressed (L34). **Blocks:** multi-instrument generalization.

## D. Psychology → operational rules

17. **"~1 trade/day", post-loss stop, patience** are taught as discipline, not hard numeric rules (L11, L17, L44, L53/L55). Must a human convert these to enforced limits (max trades/day, stop-after-loss), or keep them advisory? **Blocks:** the operational risk guardrails.

18. **Zero-minimum activity vs A+ selectivity.** "Some days you risk zero" (L13) and no-trade days (L55) are endorsed — confirm the system is allowed to emit zero signals for extended periods without being treated as broken.

## E. Definitional Conflicts (must present BOTH, not pick)

19. **Bias-flip vs retracement tension (L36 ↔ L41).** L36: a LTF BOS opposing HTF bias is just a *retrace* — don't flip. L41: an HTF BOS against your bias means "adapt and switch." The rule hinges on WHICH timeframe the opposing BOS is on, and "high time frame" is not pinned to a specific TF. **Both statements are in-corpus; reconcile before coding any bias-flip rule.**

20. **Premium/discount misspeaks (Day 26 → Day 28 correction).** L26 `[07:00]` says above-50% "is a discount to go short" (misspeak); L28 `[02:54]` says smart money "buys and shorts in a discount" (muddled). **Canonical resolution stated in the extracts:** above 50 = premium = sell/short entry; below 50 = discount = buy/long entry; longs entered FROM discount, shorts FROM premium. Confirm this canonical mapping and ensure the ASR words don't corrupt the zone gate.

21. **Equilibrium reference swing undefined ("the #1 gap").** L26 `[07:53]`: "swing high to swing low or low to high" but never WHICH swing (timeframe, leg = structure-break impulse vs full HTF range vs most-recent pivot). L28 clarifies "current-trend impulse leg re-drawn on each new high/low" but still needs an explicit fractal size / leg-boundary rule (L28 `[18:23]`; echoed L41). **Blocks:** every equilibrium/premium/discount computation. Do NOT finalize equilibrium from L26 alone.

22. **HTF alignment: hard gate or confidence weight?** L06 `[22:41]` gives the hierarchy but "no concrete 'only trade if daily BOS agrees with weekly' rule." **Blocks:** whether HTF-bias is a mandatory filter or a score contributor (PRD 15 pts).

23. **Retracement-ladder depth (how far up to confirm a real reversal).** L36 `[07:44]`: "N BOS = N+1 retrace," but "a 1m BOS could just be a 5m retrace" — unclear how many TF levels up you must confirm. **Blocks:** LTF-entry vs HTF-reversal disambiguation.
