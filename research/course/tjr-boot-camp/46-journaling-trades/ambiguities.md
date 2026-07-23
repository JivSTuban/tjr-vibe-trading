# Lesson 46 — Ambiguities

- **Risk %** [04:36]: "1 to 3%, ideally 1%." Unclear whether measured on equity vs. balance, and whether 3% is a hard ceiling or soft warning. Also "a set calculated lot size" implies a fixed pre-computed size for the instrument — value not given.
- **Session windows** [03:12]: NY / London allowed, Asian excluded, but no clock times or timezone specified in this lesson. Must confirm exact session boundaries.
- **OB vs. FVG as confirmation** [09:34]: he lists "order block entry / fair value gap entry" as interchangeable added confirmations after sweep+BOS. Whether they are truly interchangeable and what constitutes a valid "reaction/entry" needs the precise definition (lesson 49 adds nuance: a single bullish candle at equilibrium is NOT enough unless it's at an OB or FVG).
- **Live S&P trade mentioned in-video** [00:07, 10:11]: TJR is in a live long S&P position "about to hit take profit three" during filming. This is an aside, not a walked-through setup — no entry/stop/confluence detail given here, so it is NOT logged in examples.yaml. (The same PPI-day context is worked in lessons 47/49.)
- **Column layout** is a human-notebook convention; the machine schema should capture the same fields regardless of layout.
