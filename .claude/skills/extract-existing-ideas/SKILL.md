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

- A candidates JSON plus a report exist, with every candidate
  classified NEW vs WOULD-COLLIDE against the ledger's slug set —
  collisions surfaced for `/track-idea event`, never silently dropped.
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

**Pre:** root resolved. **Post:** candidate list in hand.

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0, '.claude/skills/_common')
import ideas_lib, json
print(json.dumps(ideas_lib.extract_candidates('<root>'), indent=2))
" > /tmp/extract-candidates.json
```

Or call `extract_candidates(root)` directly from a helper script.

### Stage 1 — Dedup-preview

**Pre:** candidate list resolved. **Post:** survivors classified
(new vs. dup-against-existing).

Load the existing ledger and compute the slug-set of existing intakes.
For each candidate, flag whether it would collide. Don't drop the
collisions — surface them so the user can decide whether to
`/track-idea event` against the existing instead.

```bash
.venv/bin/python .claude/skills/track-idea/scripts/track.py list 2>&1
```

### Stage 2 — Report and review

**Pre:** classification done. **Post:** approved survivor set.

Show the candidates grouped by source and dup status:

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

### Stage 3 — Hand-off to brainstorm.py

**Pre:** approved candidate JSON path resolved. **Post:** brainstorm
writes the survivors (dedup re-applied).

```bash
.venv/bin/python .claude/skills/brainstorm-ideas/scripts/brainstorm.py \
  /tmp/extract-candidates.json
```

`brainstorm.py` will:
- Skip any candidate whose slug already has an intake (idempotent
  re-runs).
- Validate each survivor.
- Append the survivors to `.claude/ideas/log.jsonl`.

### Stage 4 — Report

```
Extracted from <root>: N candidates.
  Wrote: X new intakes.
  Skipped duplicate slugs: Y.
  Sources: backlog=k1, lesson=k2.

Suggested next:
- /mature-existing-ideas <slug> for each surviving lesson-extract candidate
- /find-orphaned-ideas in a week to catch any that go stale
```

### Stage 5 — Stop

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
| Lesson body has no Rule / Why / How structure | Capture the body verbatim as summary; future `/mature-existing-ideas` pass can refine |

## Repository layout

```
.claude/skills/extract-existing-ideas/
├── SKILL.md                  # this file — orchestrator
└── scripts/
    └── extract.py            # candidate emitter (wraps ideas_lib.extract_candidates)
```

## Cross-references

- Schema: `.claude/docs/idea-ledger.md`
- Sibling skills: `/brainstorm-ideas` (writer), `/track-idea`,
  `/mature-existing-ideas`, `/find-orphaned-ideas`
- ADR motivating this system: `ai-docs/decisions/0013-idea-tracking-system.md`
