# Lesson 39 — Ambiguities

- **pip_value_per_lot is delegated to a calculator app** (STINU / website), never stated as a formula. The risk engine must source pip/point value per instrument and quote currency from broker specs — TJR does not give it.
- **Set-lot vs constant-risk conflict.** TJR's set-lot method deliberately lets realized risk float from 1% up to ~3% as the stop widens. A safety-critical engine more likely wants CONSTANT 1% risk (recompute lots each trade). This is a design decision a human must make; the two methods diverge.
- **"Confident" tier (2%) is explicitly forbidden for students** but he uses it himself. The engine should not enable it without a proven-track-record gate — and no numeric definition of "proven" is given.
- **Base SL is instrument-specific and volatility-driven.** S&P example: usually 400 pips to 4 points, up to 7 points; he sizes off the 400-pip minimum. "400 pips" vs "4 points" for the same stop reflects the pip<point relationship on S&P — confirm the conversion.
- **Points vs pips on S&P.** He says S&P is "usually in points" and "a pip is less than a point," and mixes "400 pips" with "4 points." The exact pip/point ratio for S&P must be pinned down before coding.
- **High-impact news list not enumerated here.** De-risk triggers on "high impact news" but the events (CPI/PPI/NFP per spec jargon) are not listed in L39.
- **ASR notes:** "law size"/"loss size"/"lot size" all = lot size; "stenu" = STINU app; "hanco/hanko trade" = Hankotrade; "d-risk"/"dearest"/"D risk" = de-risk; "25 watts"/"25 blocks" = 25 lots; "GBP USC" = GBP/USD. Some intermediate calculator numbers (4700, 789, 1807) are read off-screen and their instrument context is fuzzy.
