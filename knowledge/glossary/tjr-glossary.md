# TJR Boot Camp — Canonical Glossary

> STATUS: DRAFT — synthesized from 55 extracted lesson records (folders 01–56; folder 48 empty/skipped).
> Citations use folder index `LNN` (matches `research/course/tjr-boot-camp/NN-<slug>/`). Note: folder `NN` = "Boot Camp Day NN-1" in the manifest title (e.g. L54 = "Day 53").
> Nothing here is approved. All timestamps `[mm:ss]` are ASR-derived and may drift. Every definition is TJR's teaching, not standard SMC unless noted.

---

## 4X strat (TJR 4X strategy / Forex A+ template)
**TJR definition:** His named end-to-end Forex A+ template. On the $19k GBPJPY recap he calls the winning trade "literally copy and paste TJR 4X strat, pinpoint." Structure = daily bias → daily BOS → HTF building block (order block) → session-liquidity sweep → LTF BOS → entry (L54). L55 adds a concrete precondition: **price must sweep a 30-minute high/low** as a required component of the 4X strat.
**Defining lessons:** L54 `[07:42]`, L55.
**Confidence:** medium. **Ambiguity:** The name "4X" is never formally defined (likely "Forex"); no single lesson enumerates all four/N steps — it is reconstructed from the exemplar trades. Whether the 30-min-sweep is mandatory in every 4X trade or specific to L55's context is unconfirmed.

## Break of Structure (BOS)
**TJR definition:** "The simplest way I can describe a break of structure is a shift in the trend." An uptrend of higher-highs/higher-lows that starts making lower-lows/lower-highs has broken structure (L06 `[01:27]`). **The load-bearing rule:** "It is not a break of structure unless the candle *closes* above a high or below a low — write that down. We do not care about wicks." A wick alone is never a BOS (L06 `[07:54]`).
**Defining lessons:** L06 (primary), reinforced L34, L36, L14/L16 (setup chain).
**Confidence:** high.
**Ambiguity/ASR:** TJR uses **BOS = MSS = market structure shift = trend shift** as synonyms, always for the *reversal* case, and does NOT draw the standard SMC BOS(continuation)-vs-CHoCH(reversal) distinction (L06 `[01:15]`, flagged requires_confirmation). ASR corruptions: "breaker structure / break instruction / braking structure / break obstruction" → BOS (L34). Strict-greater vs equal at the exact swing price is unspecified; minimum penetration distance undefined.

## Building blocks
**TJR definition:** His umbrella term for the execution tools: order block, FVG, equilibrium, liquidity, and the BOS event ("price magnets"). Used interchangeably for entry and take-profit anchors (L34 `[17:18]`, `[19:38]`; L37 `[08:09]`).
**Confidence:** high. **ASR:** "billing blocks" → building blocks (L34).

## CHoCH (Change of Character)
**TJR definition:** NOT used as a distinct term by TJR. He collapses reversal-BOS / MSS / trend-shift into one concept. Standard SMC would label an uptrend→downtrend break a CHoCH; TJR just calls it a BOS (L06 `[01:15]`).
**Confidence:** high that he omits it. **Ambiguity:** Whether his "BOS" should map to SMC CHoCH for coding is an open definitional question (see OPEN_QUESTIONS).

## Daily bias
**TJR definition:** "The direction price wants to go for the day." Trade *with* it; trading opposite the daily bias makes a trade "short-lived or a loss." Set by current **daily market-structure/trend**: uptrend or daily BOS-up → bullish; downtrend or daily BOS-down → bearish. This is the authoritative bias for intraday because "we're doing intraday trades, not swing trading" (L34 `[00:20]`, `[17:17]`; daily-vs-weekly at L34/L36).
**Defining lessons:** L34–L36 (concept), applied L47–L55.
**Confidence:** high.

## Displacement
**TJR definition:** Not given a standalone verbal definition in the extracted concepts; appears implicitly as the strong/impulsive move that creates an FVG ("a big move up because there are no sell orders through that range"; "typically manifests as a large candle") (L14 `[02:00]`). It is a PRD §14 scorer component (10 pts) but TJR does not quantify it.
**Confidence:** low (inferred). **Ambiguity:** No numeric displacement threshold (candle size / ATR / body ratio) is taught — a key automation gap.

## Draw on liquidity
**TJR definition:** The nearest opposite-side prominent liquidity level that price is magnetically drawn toward; used to set both bias and targets. "A touch is NOT an entry" (L12).
**Confidence:** high. **ASR:** "Jaws on liquidity / draws on liquidity" → draw on liquidity (L34 `[02:50]`, `[14:44]`).

## Equilibrium / Premium / Discount
**TJR definition:** Equilibrium = the **50% mark of a swing range** — "measuring literally the high from the low and finding the 50 mark"; also called the range "break-even price" (L26 `[05:38]`). **Discount** = below 50% = cheap = where banks BUY = long zone ("it's on sale"; Doritos analogy) (L26 `[08:13]`). **Premium** = above 50% = expensive = short zone (L26).
**Defining lessons:** L26 (verbal), L28 (chart application).
**Confidence:** high on the 50% concept.
**KNOWN ASR/MISSPEAK:** L26 `[07:00]–[07:23]` TJR says above-50% "is considered a discount to go short" — this is a **misspeak**; canonical = above 50 = premium = sell, below 50 = discount = buy. L28 `[02:54]–[03:07]` "they always buy and [short] in a discount" is likewise muddled; canonical resolution: **longs entered FROM discount, shorts entered FROM premium**. See OPEN_QUESTIONS (Day26→Day28 correction).
**Ambiguity:** The **reference swing is undefined** (which timeframe / which leg) — flagged as "the #1 gap." No sub-levels (0.62/0.705/0.79 OTE) taught.

## Fair Value Gap (FVG) / Imbalance / Liquidity Void
**TJR definition:** "A fair value gap, imbalance, and liquidity void are all pretty much the same thing (I prefer 'liquidity void')." It's the opposite of liquidity: a price range with no contradicting orders, left by a fast move (L14 `[02:00]`). **Usage:** a **retracement/continuation tool, NOT a reversal tool and NOT a primary entry** — "I use liquidity sweeps to understand where the market's going, and fair value gaps to figure out where price wants to draw, or for a *secondary* entry" (L14 `[03:58]`).
**Defining lessons:** L14, L16, L18.
**Confidence:** high on definition/role.
**Ambiguity:** The **3-candle detection rule and gap boundaries are deferred/not stated verbatim** (codex infers the standard candle1–candle3 non-overlap). "FVG filled" precise definition (touch edge vs 50% vs full fill) is undefined. ASR: "for Valley Gap / fair value Gap" → FVG (L34).

## HTF (Higher Timeframe) & top-down analysis
**TJR definition:** Start on the highest timeframe (weekly) and scale down weekly → daily → 4H → 1H → 15m → 5m to derive bias then find execution (L34 top-down `[00:45]`). **Power hierarchy:** "The weekly holds more power than the daily, the monthly more than the weekly" (L06 `[22:41]`). A lower-TF BOS opposing the HTF trend is a **retracement, not a bias flip**.
**Confidence:** high. **Ambiguity:** Whether HTF alignment is a hard gate or a confidence weight is not specified.

## Kill zones / Sessions (Asian, London, New York)
**TJR definition:** Named trading sessions — Asian, London, New York — used to source intraday liquidity (session highs/lows) and to time entries ("once New York session kicks in we'll understand where price wants to go") (L34, L54 example uses London-session-highs then Asian-session-highs as the swept liquidity). "kill zone" appears in canonical jargon (L33).
**Confidence:** medium.
**Ambiguity:** **No explicit clock times or timezone are ever given** for any session (L34 `[05:39]`, `[08:33]`). This is a major automation blocker.

## Liquidity / BSL (buy-side) / SSL (sell-side)
**TJR definition:** "Liquidity is resting orders" — stop orders + limit orders clustered at a price; "a pool of money" (L08 `[02:30]`). Below lows = **sell-side liquidity (SSL)**: sell stops + longs' stop-losses; above highs = buy-side liquidity (BSL): breakout buyers' stops. Banks seek liquidity to fill size, then reverse (L08 `[05:38]`, `[05:52]`).
**Confidence:** high.
**Ambiguity:** TJR says "PROMINENT highs and lows" matter most but "what is prominent varies from timeframe to timeframe — just look at the chart" — **no numeric prominence formula** (L12). Key automation gap.

## Liquidity sweep (raid / inducement)
**TJR definition:** Price pushes beyond a high/low, triggers breakout entrants and their stops "by a couple of pips," then reverses — "they literally liquidated all of those people" (L08 `[04:14]`). It's the fake-out that separates from a real BOS: "a wick below a previous low that doesn't close below looks like a liquidity sweep… market does this to fake people out" (L06 `[23:58]`). Fractal — occurs on all timeframes (L08 `[07:19]`).
**Confidence:** high.
**Ambiguity:** **The overshoot/penetration threshold is undefined** ("a couple of pips" is qualitative; "exact overshoot threshold undefined"). This is the sweep-penetration-threshold open question.

## Market Structure Shift (MSS)
**TJR definition:** Synonym for BOS (see BOS). Used interchangeably with "trend shift" (L06 `[01:15]`). PRD §14 lists "market-structure shift" (15 pts) as its own scorer component.
**Confidence:** high (as synonym). **Ambiguity:** BOS-vs-MSS-vs-CHoCH labeling for the machine is unresolved.

## Order Block (OB) / Accumulation area
**TJR definition:** "All an order block is is that move up that causes the liquidity sweep" — "the move/leg prior to the liquidity sweep." Bullish OB = the up-leg that sweeps a prior low and breaks structure up; bearish OB = the down-leg that sweeps a prior high. Called an "order block" because "when liquidity gets swept orders get filled" in "this whole price range"; also "accumulation area" (L20 `[03:10]`, `[03:17]`).
**Defining lessons:** L20, L22, L24.
**Confidence:** high on TJR's framing.
**Ambiguity:** TJR frames the OB as a **"move/leg," NOT the standard SMC "last opposing candle before displacement"** — the single-candle definition is codex inference, flagged requires_confirmation. Whether to target the OB near edge, far edge, or midpoint is inconsistent.

## Retracement
**TJR definition:** A move against the prevailing HTF trend that does NOT flip bias. "If we see a BOS to the downside on the daily but the weekly is still bullish, it's just a retracement" (L06 `[22:41]`). FVG and equilibrium are "retracement tools."
**Confidence:** high. **Ambiguity:** L36↔L41 tension on when an opposing BOS is a retracement vs a real bias flip (see OPEN_QUESTIONS).

## Swing high / Swing low (2-candle definition)
**TJR definition:** "A high is a move up then a move down — it only takes two candles: one green candle up then a red candle down. A low is a move down then a move up." Take the highest/lowest wick of whichever of the two candles it is (L06 `[02:15]`, `[04:40]`).
**Confidence:** high (verbatim) but flagged requires_confirmation.
**Ambiguity:** This 2-candle rule is looser than a standard 3-bar fractal and may over-generate swings; TJR's drawn examples may use larger structural swings. Doji / equal-open-close direction undefined.
