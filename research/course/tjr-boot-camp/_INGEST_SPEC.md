# TJR Boot Camp — Lesson Ingestion Spec (shared by all ingestion subagents)

You convert TJR Boot Camp lesson transcripts into a structured, source-cited strategy knowledge base. **Goal: miss NO concept.** Every definition, rule, condition, number, session time, and trade example the teacher states must be captured with a timestamp. This feeds a safety-critical automated-trading system, so accuracy and honest labeling matter more than speed.

## Inputs
- Transcript dir: `research/course/tjr-boot-camp/_transcripts/`
- For lesson NN, read `NN-<videoid>.en-orig.srt` (preferred). If absent, use `NN-<videoid>.en.srt`.
- Manifest: `research/course/tjr-boot-camp/_manifest.tsv` (idx, video_id, duration_s, slug, title, primary_topic).
- Source is **YouTube auto-generated captions (ASR)** — see Jargon Normalization below.

## Output — write to `research/course/tjr-boot-camp/NN-<slug>/`
Always write these four:
1. `metadata.yaml` — course, lesson_number, title, video_id, source_reference (https://youtu.be/<id>), duration_s, processed_at ("2026-07-23"), primary_topic, transcript_source (en-orig-asr | en-asr).
2. `lesson-summary.md` — structured prose summary. Use `[mm:ss]` timestamps inline on key claims. Two clearly separated layers:
   - **What TJR teaches** (direct, faithful to the transcript).
   - **Codex interpretation** (your inference toward machine rules — explicitly labeled, never blended with the teaching).
3. `concepts.yaml` — list, each: `name`, `teacher_definition`, `source_timestamp` (mm:ss), `codex_interpretation`, `confidence` (low|medium|high), `requires_confirmation` (true unless trivially unambiguous).
4. `completion.json` — `{lesson_number, video_id, slug, status:"processed", transcript_source, transcript_chars, concepts_count, rules_count, examples_count, notes}`.

Write these **only when the lesson contains them** (skip empty files, note the skip in completion.json.notes):
5. `proposed-rules.yaml` — list, each: `id` (`tjr-<slug>-rNN`), `teacher_statement`, `source_timestamp`, `proposed_machine_rule` (concrete, testable — e.g. "enter on 5m FVG fill after MSS confirming HTF bias"), `status: proposed` (ALWAYS proposed — never approve), `ambiguity`, `counterexamples: []`.
6. `examples.yaml` — trade examples TJR walks through: `timestamp`, `instrument`, `timeframe`, `direction`, `setup_components: []`, `stated_outcome`, `suitable_for_dataset` (bool).
7. `ambiguities.md` — vague points, undefined thresholds, or jargon the ASR likely corrupted; anything a human must resolve before coding a rule.
8. `verification-questions.md` — specific questions for human review (owner: Jiv).

## Extraction rules
- **Capture concrete numbers verbatim**: risk %, R:R targets, session/kill-zone times & timezone, max trades/day, lot-size math, timeframe combos. These become risk-engine + scorer inputs.
- **Psychology/process lessons still yield rules** — convert discipline lessons into behavioral guardrails (e.g. "stop trading after N losses", "one setup per session", "no trading during high-impact news"). Label primary_topic accordingly.
- **Never invent.** If TJR is vague, record it in `ambiguities.md`, set `confidence: low`, `requires_confirmation: true`. Do NOT fill gaps with generic SMC knowledge — only capture generic SMC context as clearly-labeled `codex_interpretation`.
- **Every rule stays `status: proposed`.** Nothing is approved here.
- Preserve timestamps: SRT cues carry `HH:MM:SS,mmm`. Cite as `[mm:ss]` (or `[h:mm:ss]` if >1h).

## Jargon normalization (ASR corrupts these — map to canonical when clearly intended)
order block (OB) · break of structure (BOS) · market structure shift (MSS) · change of character (CHoCH) · fair value gap (FVG) / imbalance · liquidity · liquidity sweep / grab / raid · buy-side / sell-side liquidity (BSL/SSL) · displacement · equilibrium (50%) · premium / discount · daily bias · higher timeframe (HTF) · stop loss (SL) · take profit (TP) · risk-to-reward (RR) · lot size · kill zone / session (London, New York) · CPI / PPI / NFP (news). If an ASR word is garbled but context makes the intended term obvious, use the canonical term and note the correction in `ambiguities.md` if non-obvious.

## Return to orchestrator (compact — do NOT paste file contents)
Per lesson, one line: `NN <slug>: C concepts, R rules, E examples — <one-phrase topic>`. Then: any cross-lesson conflicts or notable multi-part concept threads you saw, and total files written. Keep under 250 words.
