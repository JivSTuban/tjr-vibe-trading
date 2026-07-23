# Lesson 15 — Identifying Problems

**Course:** TJR Boot Camp · **Video:** https://youtu.be/T4xVS7iV5d8 · **Duration:** 18:14 (1094s)
**Primary topic:** psychology (discipline / self-diagnosis / root-cause problem solving)

---

## What TJR teaches

This is a discipline / psychology "homework-inside-a-video" lesson [18:00]. There is **no chart walk-through and no strategy content**. The entire lesson is a self-diagnostic framework for finding and killing your own trading problems.

### The core exercise
- Pull out a notebook (or notes app; homework: buy a physical notebook — a callback to day one/two homework) [0:50–1:21].
- Write down **the three biggest issues you have with trading** [1:52].
- TJR insists these must have **nothing to do with strategy** [2:01]. If you were going to write "I can't find order blocks," that is disallowed — "finding order blocks is the easiest thing ever" and he'll teach it [2:02–2:07]. The three problems must relate to **risk management, emotions, or psychology** — not strategy [2:29–2:36].
- Example problem categories he names: trouble knowing when to stop trading [2:15]; over-leveraging (risking ~10% per trade instead of 1% and calling it risk management) [2:19–2:26]; not being able to walk away / put the phone down after a loss [2:51–2:59]; getting out of trades before SL or TP because you get "two in my head" [confusion] [3:52–3:57].

### The "pyramid" root-cause method
The teaching method (which his football coach taught him) [15:25–15:33]: for each problem, keep asking **WHY** until you reach the **root emotion**, then solve the root — not the surface symptom [2:39–2:45, 4:31].
1. Identify the problem [2:59].
2. Ask "why am I doing it? what is my reasoning?" [4:34].
3. Identify the **emotion** driving it — greed, revenge, fear/FOMO, overconfidence, confusion, lack of bias, lack of knowledge [3:31, 5:04–5:07, 8:13–8:22].
4. Trace further down the pyramid to the base cause [4:29 "go down that pyramid", 3:14 "find the base of the problem"].
5. Solve the **root** ("this stuff down here"), which eliminates the symptom leaves up top and prevents it spreading to other trades / life areas [9:51–10:05].

He frames it with two metaphors: **snipping leaves vs. pulling the base** of a plant/tree [13:05–13:12], and a **fungus network** under a lawn — cut the underground connections (bad habits) and "your shit's gonna be glowing" [13:20–13:37].

### Worked pyramid #1 — over-trading
- Problem: "I take 5 trades a day and I say **I should only take one**." [6:04–6:09] → surface problem is over-trading.
- Why? "Because I want to make more money" [6:10] → emotion: **greed** [7:31–7:36].
- Why greedy / why need more money? "I have no money / I'm broke" [6:18, 7:01].
- Solution: **get a job** (nine-to-five), sell things, make money outside trading [6:22–6:25, 7:03–7:07]. Rationale: relying on inconsistent trading income while unprofitable makes you trade in fear; having outside money removes the greed driver [6:29–6:44]. Trading is **not the avenue** to fix "no money" right now — focus on learning to trade [7:11–7:22].

### Worked pyramid #2 — exiting trades too early
- Problem: "I get out of trades before SL or before TP because I get two in my head" [confusion] [3:52–3:57].
- Emotions: **fear / under-confidence** (under-confidence is essentially fear), plus confusion, lack of bias, lack of knowledge [4:00–4:22].
- Why fear? You're dealing with **real / live money you can't handle** — you can't handle that **lot size** [4:29–4:36]. If you actually knew your risk you wouldn't cut early [4:44–4:48].
- Solutions offered: (1) **Understand your risk** [4:51]. (2) **Reduce risk / lower lot size** [5:01, 9:05]. (3) **Go to demo** — "you shouldn't even be putting any money at risk … maybe you should go to demo" [4:54–5:02, 9:07]. The deeper why loops back to greed ("you need the money for that trade to hit → you're broke → get a job") [9:14–9:22].

### Accountability
Every loss is **your fault and your fault only** — not the market's, not anyone else's; the market doesn't care about you [5:15–5:34]. The sooner you own that, the better off you'll be [5:34].

### "Million-dollar job" mindset
Alex Hormozi-style quote (attribution uncertain) [5:35]: if you had the best job of your life, made a big mistake, and your boss said "I won't fire you but you must never make that mistake again," you'd guarantee you never repeat it [10:35–11:20]. Treat trading like a million-dollar job you're not at yet but must respect [11:21–11:28]. If he had $10M and lost one trade with a known cause, he'd fix it because that's real money left on the table [11:32–11:49].

### On greed being unavoidable, not un-actable
TJR admits he gets greedy **every single time he trades** [21:03–21:06] — sitting in $20k profit he thinks "I could close and buy my dad a Rolex" [16:19–16:26]. The difference is he **doesn't act** on the emotion; he identifies it in the moment and says "nope, not today" [16:34, 16:46]. He can resist because he has money and knows his skill — if this trade loses he'll make it back tomorrow [16:36, 21:20–21:26]. Bad people and good people feel the same emotions; the difference is **self-control** [15:43–15:56].

Closing: apply this pyramid to life problems and New Year's resolutions too, not just trading [16:32–18:03]. Next lesson: "fair value gaps part two" [18:10].

---

## Codex interpretation (inferred machine rules — NOT TJR's literal words)

This lesson is behavioral, so it yields **guardrail rules** the risk engine / trade-journal layer can enforce, all `status: proposed`:

- **Max trades/day = 1 (aspirational).** TJR's own example is "I take 5 trades a day and I should only take one" [6:04–6:09]. Codex reads this as a *personal* target he uses to illustrate over-trading, **not a universal system rule** — the "one" is his self-diagnosis example, so the enforced cap needs Jiv to set the number. See ambiguities.
- **Stop trading after a loss / no revenge trading.** He repeatedly ties the second trade of the day after a first loss to revenge/FOMO and predicts it will lose [3:54–3:59]. Codex: enforce a "no new trade after realized loss" cooldown, and/or a daily-loss stop.
- **Fear-driven behavior → reduce size or drop to demo.** Explicit: reduce lot size, or go to demo if you can't handle the money [4:54–5:07, 9:05]. Codex: a fear/early-exit flag should trigger a size-reduction or demo recommendation.
- **Own every loss (accountability logging).** [5:24–5:34] Codex: journal must attribute each loss to a trader-side cause, never "the market."
- **Root-cause tagging.** Each logged mistake should carry a root-emotion tag (greed / fear / revenge / FOMO / overconfidence / confusion) so recurring roots can be detected — the "pyramid" [4:31].

None of these are approved; all thresholds (trades/day, loss count, cooldown length, size reduction %) are undefined by TJR here and must be confirmed by Jiv.
