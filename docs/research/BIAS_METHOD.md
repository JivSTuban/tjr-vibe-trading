# TJR Daily-Bias Determination — Method & Codable Encodings

**Status: PROPOSED (nothing here is approved).** Purpose: replace the crude daily-bias proxy in the backtester with a deterministic, OHLC-only rule grounded in the TJR Boot Camp KB.

Sources cited as `L<lesson> [mm:ss]`. Primary lessons: 34 Daily Bias, 35 Daily Bias pt.2, 36 Daily Bias pt.3, 43/51 Weekly Analysis, 50 Daily-Bias Backtest / $9k Loss SPX. Cross-refs: L06 Break of Structure, L26/28 Equilibrium, glossary, `tjr-v0.1-DRAFT.md` Stage (a).

---

## 1. How TJR determines daily bias — faithful summary

### 1.1 Top-down flow (weekly → daily → 4H → LTF)
TJR runs a fixed top-down scan and lets the **higher timeframe dictate direction**:

> "Start on the highest timeframe (weekly) and scale down weekly → daily → 4H → 1H → 15m → 5m to derive bias then find execution." (L34 `[00:45]`)
> "The weekly holds more power than the daily, the monthly more than the weekly." (L06 `[22:41]`)

The **retrace/expansion ladder** (L36 `[07:44–08:01]`) makes each lower TF a retrace of the one above it:
- 15m BOS = 1h retrace · 1h BOS = 4h retrace · **4h BOS = daily retrace** · **daily BOS = weekly retrace**.

Consequence (load-bearing): *a lower-TF BOS opposing the HTF trend is a RETRACEMENT, not a bias flip* (L36 `[07:44]`, L06 `[22:41]`, glossary "Retracement"). "Stop getting trapped into the low timeframe bias" (L36 `[10:18]`).

### 1.2 What specifically sets the *daily* direction
The **daily direction is set by daily market structure — the direction of the last confirmed daily BOS/MSS** (`tjr-v0.1-DRAFT.md` Stage (a); L34):

> "we already broke structure to the upside on the daily, that means even if we [retrace]…" → daily BOS up = **bullish** bias; daily BOS down = **bearish** bias (L34 `[08:42]`, worked bullish flow L34 `[08:42–11:01]`).

Two structural facts about "BOS" in TJR's usage:
- **Body-close confirmation.** A BOS is confirmed only on a candle whose **close** is strictly beyond the target swing; a wick beyond a swing with no close beyond it is a **liquidity sweep / fake-out**, not a BOS (L06 `[07:54]`, `[23:58]`; Stage (d)).
- **BOS ≈ CHoCH.** TJR uses "break of structure = market structure shift = trend shift" as synonyms, always for the *reversal* case (L06 `[01:15]`, `[01:27]`). He does **not** draw the SMC BOS(continuation)-vs-CHoCH(reversal) distinction, so his "BOS-that-flips-bias" maps to SMC **CHoCH**, while continuation breaks map to SMC **BOS**. Either, taken in its own direction, gives the daily direction.

**Daily is authoritative for intraday.** Weekly is *context only* for a day trader:
> "the weekly direction is up however we're not really playing completely off the weekly… I'm just trying to figure out where are we going on the daily." (L34 `[03:31]`, proposed rule r03)

Worked confirmation across lessons: Gold weekly-bearish / **daily-bullish → trade the daily** (L34; L50 `[05:28]`). SPX "overbought, retrace likely, but can we go against daily bias? No." (L50 `[02:52]`).

### 1.3 Draw on liquidity (direction target)
Bias points **toward the next untapped pool of opposing liquidity** (prior prominent highs/lows / all-time highs) when nothing structural sits between price and that pool:
> SPX "broke monthly structure up → next draws on liquidity are the highs above; no building blocks in between, so price should continue up to those highs." (L50 `[04:07]`)
> "Draw on liquidity = prior swing highs/lows (buy-side/sell-side liquidity) price is likely to reach; used both as confirmation of direction and as take-profit targets." (L34 codex). TP for a long = nearest untapped previous high; for a short = nearest untapped previous low (L34 `[07:42]`).

TJR does **not** give a numeric rule to pick among multiple competing draws (L35 codex).

### 1.4 Premium / discount (a *quality/entry* filter, not the direction itself)
Equilibrium = **50% of a swing range**: `eq = (swing_high + swing_low)/2` (L26 `[05:38]`). **Below 50% = discount = buy zone; above 50% = premium = sell zone** (L26 `[08:13]`; longs FROM discount, shorts FROM premium — glossary corrects an L26/28 misspeak). TJR treats this as *where in the range to look for the entry*, not as what sets direction. Ideally a retrace reaches "**at least equilibrium (50%) or fills the FVG** before continuation" (L36 `[01:17–01:25]`).

### 1.5 Unmitigated HTF PD arrays
Order blocks / FVGs are **retracement targets and secondary entries**, not bias setters: "Fair value gaps are used for retracements. I don't use FVGs for entries necessarily… I use liquidity sweeps to understand where the market's going, and then FVGs to figure out where price wants to draw to." (L14 `[03:58]`). High-confluence retrace zone = **FVG + equilibrium + 4H order block lined up** (L50 `[05:13]`).

### 1.6 How 4H is used (confluence, not the setter)
4H is a **confluence / confidence gate on the daily bias**, plus a take-profit governor — it does not override the daily direction:
- "we are bullish on the 4H… until we turn bearish on the 4H we can't target these absurd long-timeframe take-profits because we haven't been proved to the downside on the 4H." (L34 `[04:46]`, r04) → if 4H conflicts with daily, you may still trade *in the daily direction* but must **restrict take-profits** until 4H breaks in the daily direction.
- "Need **at least the daily AND the 4H in confluence** before trading; a 4H BOS requires a 1H BOS first." (L50 `[04:03]`).
- Even a 4H BOS *against* the daily is read as "daily retrace" = still fine for the daily bias (L34 `[08:42–09:17]`).

### 1.7 The $9k-loss lesson (bias-right, execution-wrong)
SPX fully bullish daily/weekly/4H/1H (L50 `[01:07]`). TJR went long, was stopped out for ~$9.5k, yet "**bias was ultimately correct**… labels it an EXECUTION error, not a bias error" — his mistake was entering off a *lower-timeframe* liquidity sweep instead of his marked *higher-timeframe* liquidity (`l50_loss [19:00]`, ambiguities L50 `[21:50]`). Governing principle: "**Your goal should be to lose trades based on high-timeframe reversals, not off execution errors.**" (L50 `[03:11]`). **Implication for the backtester:** the bias module's job is only to output {+1,−1,0}; entry/SL/TP quality is a *separate* module and must not be conflated with bias correctness.

---

## 2. Deterministic ENCODINGS (OHLC only; daily + 4H + weekly resampled from 5m)

All use `smartmoneyconcepts` (`smc.swing_highs_lows`, `smc.bos_choch`, `smc.previous_high_low`) + pandas. `bos_choch(..., close_break=True)` enforces the **body-close** rule from L06. Convention: bias ∈ {+1 long, −1 short, 0 flat}. "Most recent confirmed" = last non-NaN structure event at or before the evaluation timestamp (no look-ahead — evaluate on **closed** daily/4H bars only).

### Encoding A — Structure-only (most faithful to §1.2, simplest)
**Input:** daily OHLC (resampled from 5m).
**Logic:**
```
sh = smc.swing_highs_lows(daily, swing_length=SL)          # SL≈5–10 daily bars, human-set
bc = smc.bos_choch(daily, sh, close_break=True)            # body-close confirmed
struct = bc["CHOCH"].fillna(bc["BOS"]).replace(0, np.nan)  # CHoCH first (reversal), else BOS
last = struct.ffill()                                       # carry last confirmed break
bias = last  # +1 if last confirmed daily break was up, -1 if down, 0/NaN before first break
```
- **Grounded in:** L34 (daily BOS sets bias), L06 body-close, Stage (a)/(d).
- **Tradeoff:** Highest faithfulness to "daily structure = bias," lowest input burden. But it ignores premium/discount and draw-on-liquidity, so it will hold a stale direction through deep retraces (the exact thing §1.6 warns is fine for *bias* but bad for *entry*). Good clean baseline.

### Encoding B — Structure + premium/discount gate (adds §1.4)
**Input:** daily OHLC.
**Logic:** compute Encoding A's `bias`. Define the current daily dealing range from the swing pair bounding the last confirmed break (`swing_low`, `swing_high` from `sh`); `eq = (swing_high+swing_low)/2`. Then:
```
in_discount = close < eq
in_premium  = close > eq
bias = +1 if (A_bias==+1 and in_discount)
       -1 if (A_bias==-1 and in_premium)
        0 otherwise      # right direction but wrong half → stand down
```
- **Grounded in:** A + L26 `[05:38/08:13]`, L36 `[01:17]` ("at least equilibrium before continuation").
- **Tradeoff:** More faithful to "buy discount / sell premium," and it self-flattens when price is extended (fewer chase entries). Cost: it emits `0` more often, and it inherits **the #1 ambiguity — which swing defines the range** (see §3). Medium faithfulness, medium complexity.

### Encoding C — Draw-on-liquidity, structure-gated (adds §1.3)
**Input:** daily OHLC.
**Logic:** compute Encoding A's `bias`. Get the nearest **unswept** opposing daily pool with `smc.previous_high_low(daily, time_frame="1D")` (or prior swing highs/lows from `sh`). A pool counts as *swept* once a later high/low exceeds it.
```
nearest_high = closest untapped prev/swing HIGH above close
nearest_low  = closest untapped prev/swing LOW  below close
dir_to_draw = +1 if (dist to nearest_high < dist to nearest_low) else -1
bias = dir_to_draw  ONLY IF dir_to_draw == A_bias   else 0   # structure gate
```
- **Grounded in:** A + L50 `[04:07]` (draw = next liquidity when nothing sits between), L34 `[07:42]`.
- **Tradeoff:** Closest to TJR's *narrative* ("where does price want to go"), and it agrees with structure by construction. Cost: "nearest untapped pool" needs a pool-definition and a sweep-detection rule TJR never numerically specifies (L35 codex: no rule to choose among multiple draws). Highest faithfulness-of-intent, highest fragility.

---

## 3. The single biggest ambiguity a human must resolve

**Which reference swing / dealing range defines equilibrium and "the structure" — which timeframe, which leg.** The glossary flags this verbatim as **"the #1 gap"**: TJR says "a swing high to a swing low" but never fixes the timeframe or the leg (the impulse leg that broke structure? the full HTF range? the most recent swing?) (L26 `[07:53]`, glossary Equilibrium, Day-26 ambiguities). Equilibrium and the "current daily dealing range" are meaningless until pinned. A close second: **bias-flip vs retracement threshold** (L36↔L41) — how deep/confirmed must an opposing move be before it flips daily bias rather than counting as a retrace.

How each candidate handles it:
- **A:** Largely **immune** — never computes a range; only uses `swing_length` (one human parameter) and the ladder implicitly resolves flip-vs-retrace by requiring a *confirmed body-close daily break* to change `bias`.
- **B:** **Most exposed** — the discount/premium gate is only as good as the chosen range. Requires the human to fix the reference swing (recommend: the swing pair bounding the last confirmed daily break, as coded above).
- **C:** Exposed via **pool definition + sweep rule** rather than the range; needs the human to enumerate the liquidity set (prev-day H/L? swing H/L? equal highs/lows?) and a "swept" test.

---

## 4. Recommended default for the first backtest

**Encoding A (structure-only).** Reasons:
1. It is the most faithful literal encoding of TJR's own statement that *daily market structure = the bias* (L34, Stage (a)), and the $9k-loss lesson (§1.6) explicitly separates **bias** from **execution** — so the bias module should stay minimal and let a separate entry module own premium/discount and liquidity quality.
2. It sidesteps the #1 ambiguity (§3) entirely — no reference-swing choice, one tunable (`swing_length`), fully deterministic and testable.
3. B and C both bake in unresolved human judgment (range choice, pool set), which contaminates a clean bias-vs-execution attribution in the first backtest.

Sequence: ship **A** as the baseline, then A/B and A/C ablations to measure the marginal effect of the premium/discount gate and the draw-on-liquidity gate. Add the 4H confluence gate (§1.6) as a *separate* filter on top of A, not inside it.

---

*All encodings are `proposed`. `swing_length`, the reference-swing definition (B), and the liquidity pool set + sweep test (C) are human-set knobs the backtest must expose.*
