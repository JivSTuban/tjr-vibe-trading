# Verification Questions — Lesson 15 (Identifying Problems)

Owner: Jiv. Resolve before promoting any rule out of `proposed`.

1. **Daily trade cap:** TJR says "I should only take one" [06:04]. Do we enforce a
   hard max-trades-per-day = 1, a different number, or make it per-setup /
   per-session configurable? Is "one" his personal example or a system default?

2. **Post-loss behavior:** Should the engine implement a *hard stop* after the first
   realized loss (no revenge trade [03:54]), or a *cooldown* period? If cooldown,
   how long? Is there a daily-loss-count or daily-loss-% stop?

3. **Fear-driven de-risk trigger:** What measurable signal marks a trade/session as
   "fear-driven" (e.g., N early exits before SL/TP within M trades)? And what is the
   concrete response — reduce risk % (to what?), reduce lot size (by how much?), or
   force demo?

4. **Canonical risk %:** Is 1% per trade the authoritative rule (referenced only
   illustratively here at [02:19])? Confirm from the risk-management lesson so r05
   can be given a number.

5. **Loss attribution enforcement:** Do we build a journal field that *requires* a
   trader-side root-cause tag on every loss and disallows "market" [05:24]? Is this
   manual entry, or model-assisted tagging?

6. **Emotion taxonomy:** Adopt the closed set {greed, fear, revenge, fomo,
   overconfidence, confusion, lack_of_bias, lack_of_knowledge} for the root-cause
   tag, or keep it open-ended? Treat under-confidence as fear [04:13]?

7. **Never-repeat registry:** Do we implement a persistent per-trader "resolved
   mistakes" list that flags recurring root causes [10:32]? Where does it live
   (journal DB, risk config)?

8. **Cross-lesson dependency:** This lesson defers all strategy ("finding order
   blocks is easy, I'll teach it" [02:05]) and points to "fair value gaps part two"
   next [18:10]. Confirm the strategy numbers (RR targets, risk %) are captured in
   those lessons, not invented here.
