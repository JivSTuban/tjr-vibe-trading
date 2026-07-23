# Lesson 43 — Ambiguities

- **News timing / timezone** [01:49]: "these news events happen an hour before market opens." Which market open (NYSE 9:30 ET? futures?) and which timezone for CPI/PPI (typically 8:30 AM ET) needs confirmation before coding a news blocker.
- **GBP 11 AM caution** [00:39]: "around 11 AM US time" — US timezone unspecified (ET/CT/PT). The specific GBP release is not named. Cannot yet code an exact window.
- **"Break of structure" definition**: used across monthly/weekly/daily/4H/1H but not formally defined in this lesson (body-close vs. wick, swing-point selection). Needed for rules r03/r04.
- **"Following that sentiment"** [03:59]: for buy entries the 1H/4H must be "following" the weekly bias — unclear if this means same trend direction, most-recent structure event, or price above equilibrium.
- **Instrument prices not stated**: this is a visual chart walkthrough; specific levels/prices for the order blocks, imbalances, and liquidity pools were pointed at on-screen and not verbalized, so exact target values are unavailable from the transcript.
- **Divergence (gold)** [07:24]: "this looks a bit like a little divergence to me" — divergence type/indicator not specified.
