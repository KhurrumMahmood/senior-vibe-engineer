---
name: extract-existing-ideas
description: Walk existing prose surfaces (BACKLOG.md, lessons.md, plan files) and propose candidate ledger intakes for the items already named there. Read-only by default — emits a candidates JSON and a report. Hands off to /brainstorm-ideas (via its helper script) for the actual write, so the dedup, validation, and origin discipline stay in one place. Read .claude/docs/idea-ledger.md when authoring or debugging this skill.
argument-hint: "[<root>] [--write] [--source backlog|lessons|both]"
allowed-tools: Bash, Read, Write, Edit
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  Bootstrapping the ledger on an existing project where the working
  backlog and lessons file already capture work-in-flight, but nothing
  has been promoted to the ledger yet. Also useful for catching items
  that were added to BACKLOG.md but never made it through /track-idea.
not_for: |
  Generating new ideas from scratch (use /brainstorm-ideas).
  Maturing an existing ledger entry (use /mature-existing-ideas).
  Walking the *running* codebase for stringly state / duplication
  (those are SUSPECT skills like /find-implicit-state, not idea-tracking
  surfaces).
  Validating skill spec conformance (open gap — manual surrogate via
  /mature-existing-ideas).
escalate_to: |
  /brainstorm-ideas after the candidate set is approved — its helper
  handles dedup against the existing ledger and the actual writes.
  /track-idea event when the extracted item already exists in the ledger
  and the prose surface adds new information.
language: any
framework: any
---

# /extract-existing-ideas

You are the **bootstrap / catch-up** surface for the idea ledger. You
walk a directory's prose surfaces, produce candidate intakes from what's
already written down, and let the user prune before any write happens.

You do NOT generate new ideas — that's `/brainstorm-ideas`. You do NOT
mature existing ideas — that's `/mature-existing-ideas`. You do NOT
write directly to the ledger — the survivors go through
`brainstorm-ideas/scripts/brainstorm.py` so dedup and validation stay
centralized.

The ledger schema and projection rules live in
`.claude/docs/idea-ledger.md`. **Read that file** before reasoning about
a non-trivial extraction batch.

## How success is judged

- `reports/extract-existing-ideas/scan-<TS>/extract-candidates.json`
  and `report.md` exist, with every candidate classified NEW vs
  WOULD-COLLIDE against the ledger's slug set — collisions surfaced
  for `/track-idea event`, never silently dropped.
- If any write occurs, `approved-candidates.json` exists and contains
  only the user-approved survivor set; `write-report.md` is the pasted
  `brainstorm.py` transcript.
- No intake was written by this skill itself: survivors go through
  `brainstorm-ideas/scripts/brainstorm.py`, where dedup, validation,
  and origin discipline live.
- The review gate ran (unless `--write` was explicit); lesson-sourced
  candidates carry `has-more-potential` by default.
Write toward these gates from Stage 0.

## Core beliefs

1. **The backlog is the first ledger.** Most projects already have a
   working list of ideas in `BACKLOG.md` or equivalent. The ledger's
   job is to give that list a state machine and a memory. The
   extraction skill brings the existing list into the system without
   forcing the user to retype.
2. **Lessons have more potential than they look.** Every lesson is a
   candidate pattern. Carry the `has-more-potential` marker by default;
   the maturity pass will surface the ones worth promoting.
3. **Extraction is read-only by default.** Emit a candidates file plus
   a report. The user reviews, possibly edits, and then runs the writer
   step. This matters because extracting from a noisy backlog will
   surface duplicates and ambiguities the user should resolve before
   write.
4. **One writer, many readers.** All bulk writes go through
   `brainstorm.py` so the same dedup-against-ledger logic, validation,
   and origin-honesty conventions apply. This skill is a *reader*
   front end; it never writes intakes itself.

## Argument parsing

```
/extract-existing-ideas [<root>] [--write] [--source backlog|lessons|both]
```

- `<root>` — directory to walk. Defaults to repo root (`.`). Common
  choices: the repo root for a fresh bootstrap, or a working-backlog
  subdirectory if the project keeps `BACKLOG.md` / `lessons.md` there
  (e.g. `reports/`, `docs/`, or `.claude/tasks/`).
- `--source` — restrict to one surface. Default `both`.
- `--write` — skip the review gate and hand off to `brainstorm.py`
  automatically. Off by default. Only use when the extraction is small
  and the user has already confirmed.

## Pipeline

### Stage 0 — Setup

**Pre:** root resolved. **Post:** scan directory, durable candidate
JSON, and review report exist.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/extract-existing-ideas/scan-${TS}"
mkdir -p "${REPORT_DIR}"
ln -sfn "scan-${TS}" reports/extract-existing-ideas/latest

.venv/bin/python .claude/skills/extract-existing-ideas/scripts/extract.py \
  "<root>" \
  --source both \
  --project-root "$(pwd)" \
  --out "${REPORT_DIR}/extract-candidates.json" \
  > "${REPORT_DIR}/report.md"
```

Use `--source backlog` or `--source lessons` when the invocation
requested a narrower surface. Paste the helper's final `Wrote N
candidate(s) ...` line in the run summary; the report file is the
artifact, not a conversational reconstruction.

### Stage 1 — Dedup-preview

**Pre:** candidate list resolved. **Post:** survivor classification
verified against the report artifact.

Load the existing ledger and compute the slug-set of existing intakes.
For each candidate, flag whether it would collide. Don't drop the
collisions — surface them so the user can decide whether to
`/track-idea event` against the existing instead.

```bash
.venv/bin/python .claude/skills/track-idea/scripts/track.py list 2>&1
```

### Stage 2 — Review

**Pre:** classification done. **Post:** approved survivor set.

Read `${REPORT_DIR}/report.md` and show the candidates grouped by
source and dup status:

```
Extracted N candidate(s) from <root>:

## From BACKLOG.md (source_kind=backlog)

NEW (k):
  - `<slug>` — <title>  [<subsystem_kind>]
  - ...

WOULD-COLLIDE (m):
  - `<slug>` already exists. Consider /track-idea event instead.
  - ...

## From lessons.md (source_kind=lesson)

NEW (k):
  - `<slug>` — <title>  [lesson]
  - ...
```

Ask the user which to drop, rewrite, or send through unchanged. Per the
project's "no confirmation gates" rule, treat conversational approval
as authorization. If `--write` is set, skip the review gate entirely.

### Stage 3 — Write the approved survivor artifact

**Pre:** approved slugs resolved. **Post:**
`${REPORT_DIR}/approved-candidates.json` contains exactly the survivor
set the writer may consume.

If the user approved every NEW candidate unchanged, keep all NEW slugs.
If the user dropped or rewrote candidates, use the final approved slugs
only; make any rewrite directly in `approved-candidates.json` before
the writer stage.

```bash
APPROVED_SLUGS="slug-one,slug-two"
.venv/bin/python .claude/skills/extract-existing-ideas/scripts/filter_candidates.py \
  --candidates "${REPORT_DIR}/extract-candidates.json" \
  --keep-slugs "${APPROVED_SLUGS}" \
  --out "${REPORT_DIR}/approved-candidates.json"
```

The stderr line `wrote N approved candidate(s) ...` is the artifact
truth for the review gate. If zero candidates survive, stop here and
write that outcome in the final report; do not call `brainstorm.py`
with the original candidate file.

### Stage 4 — Hand-off to brainstorm.py

**Pre:** approved candidate JSON path resolved. **Post:** brainstorm
writes the survivors (dedup re-applied).

```bash
.venv/bin/python .claude/skills/brainstorm-ideas/scripts/brainstorm.py \
  "${REPORT_DIR}/approved-candidates.json" \
  > "${REPORT_DIR}/write-report.md"
```

`brainstorm.py` will:
- Skip any candidate whose slug already has an intake (idempotent
  re-runs).
- Validate each survivor.
- Append the survivors to `.claude/ideas/log.jsonl`.

### Stage 5 — Report

```
Extracted from <root>: N candidates.
  Wrote: X new intakes.
  Skipped duplicate slugs: Y.
  Sources: backlog=k1, lesson=k2.

Suggested next:
- /mature-existing-ideas <slug> for each surviving lesson-extract candidate
- /find-orphaned-ideas in a week to catch any that go stale
```

Use `${REPORT_DIR}/report.md`, `${REPORT_DIR}/approved-candidates.json`,
and `${REPORT_DIR}/write-report.md` as the source of truth for the
counts. If `--write` was not used and the user has not approved a
batch, the report names pending review instead of write counts.

### Stage 6 — Stop

Don't auto-promote. Don't auto-research. Don't write any other
artifacts. The report names the suggested next moves; the caller drives.

## What the deterministic helper covers (v1)

`ideas_lib.extract_candidates(root)` understands:

- `<root>/BACKLOG.md` — `## <heading>` sections, `- <bullet>` items
  under each. Heading maps to `subsystem_kind` (Bugs→bug,
  Extraction quality→extraction, Refactor→refactor, etc.). Items get
  `quality_markers=["underdeveloped"]` and `origin=backlog-extract`.
- `<root>/lessons.md` — `## <heading>` sections become candidates with
  the heading as title, the body as summary,
  `subsystem_kind=lesson`, `quality_markers=["has-more-potential"]`,
  and `origin=lesson-extract`.

Out of scope for v1 (orchestrator can layer them in by hand or via a
future helper version):
- Plan-file extraction (the dropout-detection scan is in
  `/find-orphaned-ideas`).
- ADR-derived candidates (ADRs are *constraints*, not ideas — better
  surfaced via `composes_with` edges on a downstream entry).
- Source-file dead/scratch detection (covered by `/find-dormant`).

The orchestrator is allowed to extend the candidate set manually by
reading other prose surfaces, but the writer step always goes through
`brainstorm.py` so the validation contract holds.

## When things go sideways

| Symptom | Action |
|---|---|
| Root has neither `BACKLOG.md` nor `lessons.md` | Exit 0 with "no recognized prose surfaces"; suggest pointing at a subdir |
| Every candidate collides with existing intakes | Report and stop; recommend `/track-idea event` against the existing instead |
| Extracted bullet has a backticked code identifier | Backticks stripped from the title; the slug normalizes to plain dashes |
| `--write` requested but candidate list is large (>20) | Override the auto-write — force the review gate (the cost of a wrong bulk-write is higher than the cost of one extra confirmation cycle) |
| User approves zero survivors | Write no `approved-candidates.json`; report "zero survivors" and stop before `brainstorm.py` |
| Approved slug missing from `extract-candidates.json` | Fix the review list; `filter_candidates.py` exits 2 and the writer must not run |
| Lesson body has no Rule / Why / How structure | Capture the body verbatim as summary; future `/mature-existing-ideas` pass can refine |

## Replay / smoke

Use `.claude/tests/ideas/fixtures/extraction-truth-set/` as the
deterministic replay root. A valid smoke run writes
`extract-candidates.json`, `report.md`, and then filters a known slug
into `approved-candidates.json`; paste the real helper output. Do not
smoke the ledger-writing stage unless the run uses `brainstorm.py
--dry-run`.

## Repository layout

```
.claude/skills/extract-existing-ideas/
├── SKILL.md                  # this file — orchestrator
└── scripts/
    ├── extract.py            # candidate emitter (wraps ideas_lib.extract_candidates)
    └── filter_candidates.py  # rewrites reviewed survivors before brainstorm.py
```

## Cross-references

- Schema: `.claude/docs/idea-ledger.md`
- Sibling skills: `/brainstorm-ideas` (writer), `/track-idea`,
  `/mature-existing-ideas`, `/find-orphaned-ideas`
- ADR motivating this system: `ai-docs/decisions/0013-idea-tracking-system.md`
