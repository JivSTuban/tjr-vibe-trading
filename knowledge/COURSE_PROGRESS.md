# COURSE_PROGRESS — TJR Boot Camp (PRD FR-001)

> Tracks course research progress. All counts computed directly from the extracted files under
> `research/course/tjr-boot-camp/NN-<slug>/`, not estimated.
> STATUS: research synthesis DRAFT. **Rules extracted: 274. Rules approved: 0.** Nothing is approved.

## Lesson coverage

| Metric | Count |
| --- | ---: |
| Lessons discovered | 56 |
| Lessons processed (non-empty extraction) | 55 |
| Lessons skipped | 1 |

- **Skipped:** `48-live-daily-bias-ppi` (L48) — no captions/empty extraction; its content is covered by `49-live-daily-bias-ppi-pt2` (L49, PPI live daily-bias analysis pt.2).
- Folder index `NN` maps to manifest title "Boot Camp Day NN-1" (e.g. folder 54 = "Day 53: $19k GBPJPY").

## Corpus totals (computed)

| Artifact | Count |
| --- | ---: |
| Total concepts (`concepts.yaml`) | 462 |
| Total proposed rules (`proposed-rules.yaml`) | 274 |
| Lessons containing ≥1 machine rule | 53 |
| Total examples (`examples.yaml`) | 105 |
| Lessons containing walked examples | 28 |
| Total open ambiguities / verification items (aggregated) | 312 |
| Deduped open questions (see `conflicts/OPEN_QUESTIONS.md`) | 23 |

## Rules approved / awaiting review

| State | Count |
| --- | ---: |
| Approved | 0 |
| Proposed / awaiting human review | 274 |

## Rules-by-category (rough tally, keyword-classified — not authoritative)

| Category | Rules |
| --- | ---: |
| Bias (daily/HTF/top-down/trend) | 86 |
| Setup (liquidity/OB/FVG/equilibrium/BOS/structure) | 52 |
| Entry (trigger/execution/entry model) | 43 |
| Risk (lot size/risk %/de-risk) | 19 |
| Target (take-profit/RR) | 9 |
| Stop (stop-loss/invalidation) | 7 |
| Management (break-even/scale/journaling) | 2 |
| Psychology (discipline/patience/mindset) | 30 |
| Other/uncategorized | 26 |
| **Total** | **274** |

> Classification is heuristic (keyword-based on rule id + machine rule text); boundaries between
> setup/entry/bias overlap. Treat as an approximate distribution, not a schema.

## Manifest primary-topic distribution (56 lessons)

| Topic | Lessons |
| --- | ---: |
| psychology | 19 |
| concept | 18 |
| process | 10 |
| example | 6 |
| risk | 3 |

## Gate

Research is aggregated but **UNAPPROVED**. Before any A+ scorer / detector / backtest work:
resolve all 23 items in `knowledge/conflicts/OPEN_QUESTIONS.md` and flip `tjr-v0.1-DRAFT` out of DRAFT via human review. No rule may be marked `approved` by an automated step.
