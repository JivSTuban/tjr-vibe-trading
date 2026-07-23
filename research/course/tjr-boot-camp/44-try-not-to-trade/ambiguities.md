# Lesson 44 — Ambiguities

- **Chop / "directionless" is undefined numerically** [04:56, 07:26]. TJR shows it visually ("a whole bunch of nothing," repeated fake BOS + liquidity sweeps). A machine chop-detector needs a concrete metric (e.g., count of failed BOS in lookback, range compression, net displacement) and a threshold. Human must set this.
- **No explicit max-trades-per-day number.** "Take the most days off" and "don't trade that day" are directional. The Paladin "~8 trades in a month" [10:52] is an anecdote about another trader, NOT a stated rule for the student. Do not hardcode a numeric cap from this lesson.
- **"Building block"** is used (hourly building block, etc.) as a catch-all for order block / FVG / liquidity level. Confirm the canonical enumeration from earlier lessons.
- **"Confirmation on the five minute"** [03:14] — the confirmation is a 5m break of structure in the examples, but whether other confirmations (FVG fill, OB reaction) also qualify as "confirmation" on the execution TF is not enumerated here (lesson 49 adds OB/EQ/FVG reaction as confirmation types).
- Examples are all **hypothetical** ("this is all hypothetical," "let's say") — no real dated trade with outcome is walked through, so no examples.yaml.
