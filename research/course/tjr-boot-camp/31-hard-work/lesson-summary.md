# Boot Camp Day 31: Hard Work — Lesson Summary

**Video:** https://youtu.be/isetVuqlSLo · **Duration:** ~19:30 · **Primary topic:** psychology (work ethic / discipline)

This is a pure motivation/discipline lesson filmed at the gym. No trading strategy, chart mechanics, or numeric trade parameters are taught. TJR reframes an Alex Hormozi video and delivers a "wake-up call" that trading results are a function of hours of work and discipline, not talent, motivation, or manifestation. It is a mid-boot-camp morale/accountability check (~1 month in).

---

## What TJR teaches

- **Minimum effort → minimum results.** "If you put in minimum effort and minimum work you are going to get minimum results" [00:52]. Conversely, put in so much work that the desired result becomes *undeniable*.
- **The 4× rule (attributed to Alex Hormozi).** To reach where the top person in an industry is, you must do "four times the work that the top person in that industry is doing" [01:17]. You cannot just copy what they do *now* — when they were in your position they did far more.
- **His own past work volume (as proof of the standard).** He watched "eight hours of YouTube videos a day," read "10 plus day trading books" and "10 plus books on psychology" [01:49–01:57], constantly learning until he mastered the skill — and did not let up after mastering it.
- **Minimum daily study target: 4 hours/day** (again attributed to Hormozi): "do four hours a day, four hours is not a lot of time" [00:24:19 → cue at ~04:24; spoken as] "he says do four hours a day" [04:24]. Reclaim it from TikTok/YouTube screen time. *(ASR note: the "four hours a day" quote is stated around [04:24].)*
- **He personally did 2× that (8 hours/day)** in high school, e.g. watching 2 hours of day-trading videos while doing cardio on the bike [04:40–04:53].
- **"Undeniable results" build self-belief.** Paraphrasing Hormozi: you need undeniable results to prove to yourself you're confident enough to offer something to someone; you get undeniable results through work [02:43–02:59].
- **Practice/work so hard they "have no choice."** Story from "Mo Trades" (ASR: "more trades") whose dad told him: practice and work so hard "so they have no other choice but to play you" [03:52–03:58]. Applies to any skill.
- **Kobe example.** Kobe practiced ~3× a day while teammates practiced 1–2× [05:39–05:43]; greatness = genetics + work ethic, and work ethic is what *sustains* it [05:47–06:11].
- **Self-audit rule:** if you don't see yourself getting better *every single day*, change something and do more [06:32–06:35]. Concrete example: if you back-test 1 hour/day, do 1.5 hours; add 30 min of trading study + 30 min of psychology study [06:41–06:52].
- **Discipline > motivation.** "Motivation won't get you everywhere, it's the discipline that will" [10:40]. You won't *want* to wake up early, trade, study, and journal daily — do it anyway. Don't let today be your only motivated day; let discipline drive you [19:07].
- **Embrace failure.** Paraphrasing Hormozi: fail a thousand times — if you succeed even 1–10 of those, you're on a better/great track [04:35–04:53 region, cues ~797–815]. Fear of trying is the real blocker.
- **Progress compounds like the gym.** Newbies who stick ~1–1.5 weeks see results and get "addicted"; put in enough work to get addicted to seeing results (subscribers, win rate, etc.) [12:17–12:38].
- **His own goal check-in.** His boot-camp short-term goals were social-media based; he says he's "killing it" [11:50–11:56]. Subscriber ladder: aims for 100k → proud-not-satisfied → 200k → 300k → 500k, never settling [17:04–17:14].
- **Improvement metrics for a trader** (stated as the things that should be improving if you're working): win rate, risk-to-reward, entry precision ("entries get more exact"), profitability, and learning from mistakes [14:15–14:27].
- **Homework:** re-watch Day 1 of the boot camp; reconsider your goals and the short-term goals set earlier; assess progress on them [11:12–11:16, 03:03 region].
- **Gatekeeping tone:** if a competitor is out-working you and that isn't a wake-up call, "I don't think trading's for you" [13:53–14:00]. Framed as a deliberate "slap in the face."

---

## Codex interpretation (inference toward machine rules — NOT taught verbatim)

This lesson contributes **behavioral guardrails and effort telemetry**, not entry logic. For an automated-trading + operator-discipline system, the machine-relevant translations are:

- **Study/effort quota tracker (soft, operator-facing).** TJR's stated minimum is 4 h/day of trading study/back-test/psychology; his personal max was 8 h/day. *Codex:* could log daily study/back-test minutes and flag when below a configured threshold. This is an operator-productivity metric, not a trade filter. Confidence low — the 4 h figure is quoted from Hormozi, not a TJR-mandated system parameter.
- **Continuous-improvement KPIs.** The metrics TJR names — win rate, R:R, entry precision, profitability, "learning from mistakes" — map cleanly to a **journal/scorer dashboard** that trends these per week. *Codex:* these become monitoring outputs, not gates.
- **Discipline over discretionary motivation.** *Codex:* argues for *fully rule-based* execution (remove "do I feel like it") — supports automating the process rather than leaving it to daily willpower.
- **Failure tolerance / expectancy framing.** "Fail 1000× and succeed a few" = a positive-expectancy, high-sample mindset. *Codex:* consistent with requiring a large back-test sample before trusting a setup, and not abandoning a rule on a small losing streak. No numeric sample size is given here — do NOT invent one.

**No entry rules, session times, risk %, R:R targets, or timeframe combos are stated in this lesson.** Nothing here should be coded as a trade trigger.
