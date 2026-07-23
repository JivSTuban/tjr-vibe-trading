# Lesson 39 — Calculating Lot Size (position sizing math)

## What TJR teaches

Three position-sizing approaches [00:37–01:35]:
1. **Set lot size** (what TJR uses; a range of set sizes tied to conviction).
2. **Calculate lot size every trade** (shown step-by-step).
3. **Full port** — "you will never do... third option is completely out of the picture."

### Method 2 — Calculate per trade

**Inputs for a lot-size calculator** [02:06–03:00]: account balance, risk amount (% ), stop loss in Pips. Tools: the **STINU** app (s-t-i-n-u, ~$14/yr, no S&P), or a website that supports S&P + Forex.

**Forex worked example** [02:14–03:52]:
- Account = **$1,000**, risk = **1%**, stop loss = **30 pips** → calculator returns **0.03 lots** → risking **$10** (=1% of $1,000).
- Can't go beyond **two decimal places** on lot size (so round to 0.01 granularity).
- Another example implied: a smaller allocation → **0.01 lots**.

**Getting SL in pips off the chart** [04:35–05:04]: Use the short-position tool; the tool's number IS your stop-loss in pips (e.g. 11, 47, 16 pips). Plug that into the calculator, get lot size, enter.

**S&P worked example** [05:08–06:43]:
- Account = **$100,000**, stop loss entered → S&P is quoted in **points** (a pip is less than a point). Example SL values: **1807**, and "4700"/"789" appear as intermediate calculator outputs.
- **Contract size / units per lot** matters [05:32, 06:52–07:56]: most offshore brokers = **100 units per lot**. TJR's broker (Hankotrade) = **10 units per lot**. You MUST check "contract size" under the symbol details in MetaTrader (SPX → Details → Contract size). Getting this wrong "could really mess you up."
- This is why his TikTok "100 lots per trade" looks huge but isn't — at 10 units/lot it equals ~10-20 lots on a standard 100-unit-per-lot broker [Lesson 38 preview + 05:41–07:56].

### Method 1 — Set lot size (his actual method) [08:59–15:00]

**S&P set-lot derivation** [09:01–09:51]:
- His S&P SL is usually **400 pips to ~4 points**, up to **7 points**; he uses the **minimum/lowest** expected stop (usually **400 pips**) to size.
- Account $100,000, 1% risk, 400-pip stop → **25 lots**. That 25 lots becomes his fixed "set lot size."

**Why fixed lots + variable risk %** [09:52–11:34]:
- With a fixed 25 lots and a 400-pip stop → **1% risk**.
- If the stop is larger — e.g. **800 pips / 8 points** (2× the base) → he risks **2%**.
- If price stop is **3× the base** → **3%** risk. Most of the time it never reaches 3%.
- He's on a live account and cares less about exact % because the set-lot makes it fast: plug in, enter every time. Knows his average stop, so knows his typical risk.

**Set-lot risk tiers** [12:52–15:00]:
- **Normal risk** = his set lot (25 lots in example) = **1%**. Use on days with no news / news that won't move markets.
- **De-risk** = **50% of normal** (12–13 lots) = ~0.5% base. Use on high-impact-news days, bank holidays, or when something will mess up the market. He used de-risk on the Fourth of July.
- **Confident** = **2× normal** (double) = **2%** base. Use only on no-news days with all biases aligned and a loved setup. **Students should NEVER use confident** — "you guys don't have the confidence built up." Normal or de-risk only for students.

**Per-pair caveat** [11:38–11:57]: The set stop loss is different for every pair (volatility/volume differ), so the set lot must be recomputed per instrument. Beginners should trade only one pair.

**Progression gate** [12:03–12:15]: Beginners should use calculate-lot-size or a **cent lot size**, turn profitable first, then move to set-lot.

## Codex interpretation

- **Base risk = 1% per trade** (his "normal"). De-risk tier = **0.5%** (50% lot). Confident tier = **2%** (2× lot) — the last is disabled for anything but an already-proven track record; the engine should default-cap at 1% and only allow de-risk downward.
- **Lot-size formula (Method 2):** `lot = risk_amount / (SL_pips × pip_value_per_lot)`, where `risk_amount = account × risk_%`, rounded to 2 decimals (0.01 granularity for Forex). `pip_value_per_lot` depends on **contract size (units per lot)** — MUST be read from broker symbol details (100 vs 10). This is the exact math the risk engine needs.
- **Set-lot method:** size the fixed lot from the *minimum expected* SL at target risk %; then actual risk floats UP with wider stops (2% at 2× stop, 3% at 3× stop). Machine implication: with fixed lots, realized risk = `base_risk% × (actual_SL / base_SL)`. The engine should either (a) recompute lots per trade to hold risk constant, or (b) replicate set-lot and CAP realized risk (e.g. reject if actual_SL/base_SL implies >2-3%).
- **Contract size is a mandatory config per broker/instrument** (units per lot); mis-set → order sizing off by 10×.
- **Conviction/news modifiers:** de-risk to 0.5% on high-impact-news/holiday days; never scale up for students. This ties to L38's news/holiday guardrails.
