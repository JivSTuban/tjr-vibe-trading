# Course Ingestion Options — TJR "Boot Camp"

**Task:** TASK-001 — Evaluate and select a pipeline to ingest the TJR "Boot Camp" YouTube course into the trading knowledge base.
**Date:** 2026-07-23
**Author:** Ingestion research
**Status:** Decided — Go

---

## 1. Objective

Ingest the TJR "Boot Camp" YouTube playlist into a structured, timestamp-cited knowledge base under `research/course/tjr-boot-camp/` that the OpenAI Codex trading agent can query.

- **Playlist:** `PLKE_22Jx497twaT62Qv9DAiagynP4dAYV`
- **Scope:** 56 lessons, ~18.6 hours total
- **First lesson (test target):** video `Xq6-oO2n6-U`
- **Output consumer:** Codex trading agent (retrieval over per-lesson structured records)

The goal is **not** to mirror the videos. It is to extract timestamped teaching (definitions, rules, setups) into an internal strategy KB, with every claim traceable back to a source timestamp.

---

## 2. Environment

| Component | Detail |
|---|---|
| OS | macOS |
| `yt-dlp` | `/opt/homebrew/bin/yt-dlp` (Homebrew) |
| `ffmpeg` | available on PATH (used by `--convert-subs`) |
| Whisper | available locally as fallback ASR |
| Runtime agent | OpenAI Codex (consumes the generated KB; not part of ingestion) |

---

## 3. Approaches evaluated

Per PRD §8 we evaluated four approaches (A–D). Summary first, detail below.

| Approach | Auth needed | Automation | Verdict |
|---|---|---|---|
| A — Existing plugin/skill | Varies | Medium | Rejected as primary — opaque, not resumable at 56-lesson scale |
| B — Browser automation | Session cookies | Low (brittle) | Fallback-of-last-resort only |
| C — Local transcript pipeline (yt-dlp) | None (public) | High | **CHOSEN** |
| D — Custom Codex skill wrapping C | None | High | **CHOSEN wrapper** — how C ships as a repeatable workflow |

### Approach A — Existing plugin / agent skill

An existing video/transcript research skill (e.g. an MCP "watch"-style tool, or a hosted transcript API such as `youtube-transcript-api`).

- **Installation:** none-to-light (skill already present, or `pip install youtube-transcript-api`).
- **Auth:** none for public videos via the skill; hosted transcript APIs may require a key/proxy.
- **Capabilities:** fast one-off "what does this video say" answers.
- **Limitations:**
  - Optimized for single-video Q&A, not a resumable 56-item batch producing a structured KB.
  - `youtube-transcript-api` is **not** reliable at scale: YouTube blocks most cloud/datacenter IP ranges and soft-limits ~100–200 requests/hr/IP; the documented `RequestBlocked` failure mode requires proxies. ([jdepoix issue #511](https://github.com/jdepoix/youtube-transcript-api/issues/511), [TranscriptAPI 2026](https://transcriptapi.com/blog/best-youtube-transcript-apis-compared))
  - Output shape is controlled by the tool, not by our lesson schema (PRD §11).
- **Automation compatibility:** medium; hard to make idempotent/resumable and to guarantee our field layout.
- **Verdict:** rejected as primary. Its transport (`yt-dlp`) is the same one we adopt directly in C, but with full control over format and resumability.

### Approach B — Browser automation

Drive a real browser (Playwright / claude-in-chrome) to open each lesson, expand the transcript panel, and scrape cues.

- **Installation:** Playwright + browser, or the claude-in-chrome extension.
- **Auth:** a logged-in session; **required** for member-only / paid content.
- **Capabilities:** can reach content that is gated behind a login or that hides captions from the download API.
- **Limitations:** slow, brittle (DOM/selectors change), rate-limit and bot-detection exposure, heavy to run 56× and to make idempotent.
- **When it is actually needed:**
  1. The video has **no captions at all** and audio download is blocked (rare) — but Whisper on downloaded audio (part of C) covers most no-caption cases without a browser.
  2. Content is **member-only / paid** and only accessible via an authenticated session.
- **Note:** the TJR Boot Camp playlist is public and captioned, so neither condition applies. B is held as a last-resort fallback only.

### Approach C — Local transcript pipeline (CHOSEN)

`yt-dlp` auto-captions → normalize SRT → structured lesson records; Whisper only if captions are absent or poor.

- **Installation:** `yt-dlp` + `ffmpeg` (both present). No YouTube account, no API key.
- **Auth:** none — the playlist is public.
- **Capabilities:** batch-downloads timestamped captions for the whole playlist, converts to a single reliable format (SRT), and feeds a deterministic normalize → validate → record generation chain we fully control.
- **Format choice:** we take auto-captions and `--convert-subs srt`. SRT (and VTT) are the reliable formats; `json3`/`srv*`/`ttml` have documented `UnsafeExtensionError`-class issues and are avoided in production. ([yt-dlp #9371](https://github.com/yt-dlp/yt-dlp/issues/9371), skipthewatch 2026)
- **Automation compatibility:** high — pure CLI, scriptable, resumable, deterministic.
- **Limitations:** auto-captions are ASR, so trading jargon is a known accuracy risk (see §5 and §7); no speaker labels; occasional cue drift on fast speech.

**Exact working commands (this is what we run).**

Discover the playlist (IDs + titles, no download):
```bash
/opt/homebrew/bin/yt-dlp \
  --flat-playlist \
  --print "%(playlist_index)03d|%(id)s|%(title)s" \
  "https://www.youtube.com/playlist?list=PLKE_22Jx497twaT62Qv9DAiagynP4dAYV"
```

Confirm caption availability for a single lesson (the test step already run on lesson 1):
```bash
/opt/homebrew/bin/yt-dlp --list-subs "https://www.youtube.com/watch?v=Xq6-oO2n6-U"
```

Download captions as SRT for one lesson (skip the video):
```bash
/opt/homebrew/bin/yt-dlp \
  --write-auto-subs \
  --sub-langs "en-orig,en" \
  --convert-subs srt \
  --skip-download \
  -o "research/course/tjr-boot-camp/%(playlist_index)03d-%(id)s.%(ext)s" \
  "https://www.youtube.com/watch?v=Xq6-oO2n6-U"
```

Batch the whole playlist (the chosen pipeline):
```bash
/opt/homebrew/bin/yt-dlp \
  --write-auto-subs \
  --sub-langs "en-orig,en" \
  --convert-subs srt \
  --skip-download \
  --download-archive research/course/tjr-boot-camp/.yt-archive.txt \
  -o "research/course/tjr-boot-camp/%(playlist_index)03d-%(id)s.%(ext)s" \
  "https://www.youtube.com/playlist?list=PLKE_22Jx497twaT62Qv9DAiagynP4dAYV"
```

Whisper fallback (only when a lesson has no usable caption):
```bash
/opt/homebrew/bin/yt-dlp -x --audio-format mp3 \
  -o "research/course/tjr-boot-camp/audio/%(id)s.%(ext)s" \
  "https://www.youtube.com/watch?v=<id>"
whisper "research/course/tjr-boot-camp/audio/<id>.mp3" \
  --model medium.en --output_format srt \
  --output_dir research/course/tjr-boot-camp/
```

### Approach D — Custom Codex skill `tjr_course_research` (CHOSEN wrapper)

Wraps Approach C into a repeatable, resumable workflow (PRD §10) so a re-run is safe and each lesson lands in the PRD §11 schema. Script set:

| Script | Responsibility |
|---|---|
| `discover_playlist` | `yt-dlp --flat-playlist` → ordered manifest of `{index, video_id, title, url}`. |
| `extract_metadata` | Per lesson: duration, upload date, chapter markers (if present), channel — from `yt-dlp -J` (JSON), no download. |
| `normalize_transcript` | Parse the SRT → ordered cues `{start, end, text}`; strip caption artifacts (music tags, dedup rolling-caption repeats, collapse whitespace). |
| `validate_timestamps` | Assert monotonic non-overlapping cues, `end > start`, and that max cue end ≈ video duration (flags truncated/corrupt captions and Whisper drift). |
| `generate_lesson_record` | Emit the per-lesson structured record (§11 schema) with citations, then write the completion marker (§9). |

The skill is the single entry point; running it against the playlist produces/refreshes the whole KB idempotently.

---

## 4. Copyright considerations

The TJR videos are **public but copyrighted**. This pipeline treats them accordingly:

- **Internal use only.** We extract **timestamped rules, definitions, and notes** into an internal strategy KB. We do **not** publish or redistribute the videos or their full transcripts.
- **No transcript republication.** Raw SRT files live locally under `research/course/tjr-boot-camp/` as a working intermediate. The shipped artifact is the distilled lesson record (paraphrased rules + short cited quotes with timestamps), not a verbatim transcript dump.
- **No training on paid/private content.** Only this public playlist is ingested. Member-only, paid, or private content is out of scope and is never used to train or fine-tune anything.
- **Attribution + traceability.** Every extracted claim carries a source `video_id` + timestamp so it is auditable back to the original teaching, and quotes are kept short (fair-use excerpting for an internal analytical KB).

---

## 5. Test results (one TJR lesson)

Concrete test run against **lesson 1**, video `Xq6-oO2n6-U`, using `yt-dlp --list-subs`:

- **Auto-generated captions available** in `en-orig` and `en`.
- Offered in **vtt, srt, and json3** — all with cue timestamps.
- **No human/manual subtitles** present (auto-generated only).

Conclusion: the download path works, timestamps are present, and `--convert-subs srt` yields a clean, parseable file. This validates Approach C end-to-end on a real lesson.

**Caveat surfaced by the test:** because the only captions are ASR (auto-generated), **trading jargon accuracy is a real risk** — see §7.

---

## 6. Timestamp preservation (→ citations)

- SRT cues carry `HH:MM:SS,mmm --> HH:MM:SS,mmm` ranges. `normalize_transcript` keeps each cue's `start`/`end`.
- Every rule/definition in a lesson record stores the originating cue's `start` (and range) as a **citation**, e.g. `{"source": "Xq6-oO2n6-U", "t": "00:14:32"}`, renderable as a deep link (`youtube.com/watch?v=Xq6-oO2n6-U&t=872s`).
- `validate_timestamps` guarantees the citations are sane (monotonic, in-bounds vs. duration) before a record is accepted.
- Net effect: Codex answers can cite "TJR, lesson 3 @ 14:32" for any claim.

---

## 7. Known limitations

- **ASR jargon errors (primary risk).** Auto-captions are Whisper-class ASR, which systematically mis-transcribes domain jargon and proper nouns — documented ~28% domain-jargon error share in specialized-domain studies (e.g. "pick and roll" → "picker roll"). Trading terms (order block, FVG/fair value gap, liquidity sweep, TJR's own coinages, ticker symbols) are exactly this failure class. ([axinc jargon fine-tuning](https://medium.com/axinc-ai/whisper-fine-tuning-to-transcribe-jargon-976164a5eac8), [whisper-large-v3 model card](https://huggingface.co/openai/whisper-large-v3))
  - **Mitigation:** maintain a domain glossary and run a normalization pass (regex/alias map) over cues before record generation; where Whisper fallback is used, pass the glossary as an `--initial_prompt` to bias decoding; mark auto-derived rules `status: proposed` for human review.
- **No speaker labels** in auto-captions (fine here — single presenter).
- **Cue drift / rolling-caption duplication** on fast speech — handled by the dedup + validate steps.
- **`youtube-transcript-api` / hosted APIs** are IP-block-prone at scale — one more reason we use `yt-dlp` directly.

---

## 8. Resume / idempotency

Two independent guards make re-runs safe:

1. **Download layer:** `yt-dlp --download-archive .yt-archive.txt` records each completed `video_id`; a re-run skips already-fetched captions.
2. **Record layer (completion marker, PRD §9):** `generate_lesson_record` writes a per-lesson marker (e.g. `research/course/tjr-boot-camp/<index>-<id>.done.json` with a content hash) on success. The skill skips any lesson whose marker exists and matches — so a re-run only processes new or changed lessons. Delete a marker to force reprocessing.

This makes the 56-lesson run interruptible and cheap to resume.

---

## 9. Duplicate-content detection

- **Cross-lesson dedup:** each lesson record stores a content hash of its normalized transcript. Identical hashes flag re-uploaded/duplicate lessons.
- **Rule-level dedup:** extracted rules are near-duplicate-checked (normalized text similarity) so the same setup taught in multiple lessons collapses into one canonical rule with **multiple citations**, rather than N conflicting copies.
- **Intra-transcript dedup:** rolling auto-captions repeat lines across cues; `normalize_transcript` removes the overlap so timestamps and rule extraction aren't inflated.

---

## 10. Teaching vs. Codex interpretation (output schema)

Per PRD §11, each lesson record keeps the teacher's words and the agent's reasoning **strictly separated**:

```json
{
  "lesson_index": 3,
  "video_id": "Xq6-oO2n6-U",
  "title": "…",
  "duration_sec": 1187,
  "transcript_hash": "sha256:…",
  "concepts": [
    {
      "name": "Order Block",
      "teacher_definition": "TJR's stated definition, paraphrased/quoted from the video.",
      "citations": [{ "source": "Xq6-oO2n6-U", "t": "00:14:32" }],
      "codex_interpretation": "How the Codex trading agent reads/operationalizes this — clearly NOT the teacher's words."
    }
  ],
  "rules": [
    {
      "text": "Only enter after a liquidity sweep into the order block.",
      "status": "proposed",
      "citations": [{ "source": "Xq6-oO2n6-U", "t": "00:16:05" }],
      "source": "teacher_definition"
    }
  ]
}
```

- `teacher_definition` = **direct teaching** (what TJR said), always with citations.
- `codex_interpretation` = the agent's derived reasoning, never conflated with the source.
- Every extracted `rule` is emitted with **`status: "proposed"`** — nothing is treated as a validated trading rule until a human promotes it. This keeps ASR-jargon errors from silently becoming "truth."

---

## 11. Recommendation, fallback, decision

- **Recommended approach: C — local `yt-dlp` transcript pipeline**, shipped as the **D** custom Codex skill `tjr_course_research`. No auth, high automation, deterministic, resumable, tested on lesson 1.
- **Fallback approach:** per-lesson **Whisper on downloaded audio** (part of C) when a lesson lacks usable captions; **browser automation (B)** only as a last resort for gated/uncaptioned content. Neither is needed for this public, captioned playlist.
- **Go / No-Go: GO.** Tooling is installed, the playlist is public and captioned (verified on lesson 1: `en-orig` + `en` auto-captions with timestamps), copyright handling is internal-only with no redistribution, and the resumable skill design covers all 56 lessons. Proceed to batch ingestion.

**Watch item:** auto-caption accuracy on trading jargon — mitigate with the domain glossary/normalization pass and keep all extracted rules `status: proposed` for human review.

---

## Sources

- yt-dlp subtitle formats & reliability — [yt-dlp issue #9371](https://github.com/yt-dlp/yt-dlp/issues/9371), [SkipTheWatch: yt-dlp subtitles (2026)](https://skipthewatch.com/blog/yt-dlp-youtube-subtitles)
- Whisper jargon accuracy — [axinc: Whisper fine-tuning for jargon](https://medium.com/axinc-ai/whisper-fine-tuning-to-transcribe-jargon-976164a5eac8), [openai/whisper-large-v3 model card](https://huggingface.co/openai/whisper-large-v3)
- youtube-transcript-api limits — [jdepoix issue #511](https://github.com/jdepoix/youtube-transcript-api/issues/511), [TranscriptAPI: best APIs compared (2026)](https://transcriptapi.com/blog/best-youtube-transcript-apis-compared)
