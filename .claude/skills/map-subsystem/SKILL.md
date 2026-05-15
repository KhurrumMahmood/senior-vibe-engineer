---
name: map-subsystem
description: Produce or refresh a durable inventory doc for a subsystem at .claude/docs/subsystems/<name>.md. Covers file list, public surface, responsibility table, dependency graph, convention-compliance score. No refactor intent — MAP skill in the maintenance nervous system.
argument-hint: "<subsystem-name-or-path> [--refresh]"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: map
best_for: |
  Producing or refreshing a durable inventory doc for a subsystem at
  `.claude/docs/subsystems/<name>.md` — file list, public surface,
  responsibility table, dependency graph, convention-compliance
  score. MAP skill in the maintenance nervous system.
not_for: |
  Cross-subsystem product workflows (use /map-product-workflow).
  Per-symbol behavior annotation (use /explain-code). Refactor
  execution (use /refactor-subsystem with a spec).
language: python
framework: django
---

# /map-subsystem

You are the **orchestrator** for a MAP skill. Given a subsystem name or
path, you produce (or refresh) a durable inventory doc at
`.claude/docs/subsystems/<name>.md`. You do not edit production code
and you do not refactor.

This is the MAP job in the five-jobs nervous system (see
`.claude/docs/skill-catalog.md`). The output feeds every downstream
SUSPECT / EXPLAIN / REFACTOR invocation on the same subsystem — so it
needs to be accurate, re-readable without the skill loaded, and
cheaply refreshable.

Procedural detail lives in two knowledge files:

- `knowledge/` — shared conventions pointer +
  subsystem-naming rules for this repo.
- `knowledge/output-format.md` — the exact shape of
  `.claude/docs/subsystems/<name>.md` + worked example.

## Core beliefs

1. **The map is a living doc, not a one-shot dump.** On refresh, diff
   against the prior version and call out what *changed* (symbols
   added/removed, responsibility clusters split, imports redirected).
   A user reading this doc should be able to infer the subsystem's
   direction, not just its current state.
2. **Public surface is load-bearing.** What outside callers see is
   the real contract. Private helpers are inventory; public symbols
   are the contract. The doc must distinguish them.
2a. **Product workflow participation is context.** If the subsystem
   owns routes, templates, JavaScript, status providers, or docs for a
   mapped product workflow, cross-link the relevant
   `.claude/docs/workflows/<name>.md` map. A file can be locally tidy
   while still contributing to topology drift.
3. **Responsibility count beats LOC count.** A 500-LOC file with one
   responsibility is fine; a 200-LOC file with three is the problem.
   Apply the SRP "and" sentence test (from
   `refactor-subsystem` §1.2.5).
4. **No judgment calls in the map.** The doc reports: X is 2,400 LOC,
   imports from 14 modules, has 3 responsibility clusters. It does
   NOT say "should be split" — that's a SUSPECT skill's job.
5. **Reusable infra only.** Reuse `scripts/chunk_file.py`,
   `scripts/duplication_audit.py`, existing ruff config. Do not
   introduce new scanners here — the MAP job is aggregation, not
   detection.

## Argument parsing

Two forms:

### Form A — subsystem name (preferred)
`views-crawling`, `services-ai-training`, `services-discovery-field-matcher`.
Names use kebab-case, match `<layer>-<domain>`.

Resolve to a path using the naming table in
`knowledge/`. If the name doesn't resolve, ask once
for a path; don't guess.

### Form B — explicit path
`core/views/crawling.py`, `core/services/discovery_field_matcher/`,
`core/tasks/exports.py`.

Directories and files both work. The subsystem name is derived from
the path (path segments joined with `-`, minus `core-`).

### `--refresh` flag
Indicates a re-run against an existing `.claude/docs/subsystems/<name>.md`.
The skill MUST produce a diff section at the top of the new doc
summarizing what changed since the previous version's "Regenerated"
timestamp.

## Scope

- **Target:** a single subsystem (one file or one directory package).
- **Worktree:** current working directory.
- **Python:** `.venv/bin/python` (never bare `python`).
- **Output:** `.claude/docs/subsystems/<name>.md`. Never touches any
  other file.

## Pipeline stages

Each stage has a contract — what it reads, what it writes. Scripts run
with `.venv/bin/python` and capture stderr.

### Stage 0 — Resolve target + setup

**Pre:** argument parsed. **Post:** `$OUTPUT_PATH` resolved,
`reports/map/<name>/` scratch dir exists.

```bash
NAME="<resolved subsystem name>"
OUTPUT_PATH=".claude/docs/subsystems/${NAME}.md"
SCRATCH=$(mktemp -d)
PRIOR="$([ -f "$OUTPUT_PATH" ] && cat "$OUTPUT_PATH" || echo "")"
```

If `$OUTPUT_PATH` exists and `--refresh` was not passed, warn and
exit with guidance to re-run with `--refresh`.

### Stage 1 — File inventory

**Pre:** target resolved. **Post:** `$SCRATCH/files.jsonl` — one line
per file in the subsystem with `{path, loc, last_commit, last_author}`.

Use `find` (well — `Glob`) for the file list and
`git log --format=...` for per-file last-commit info. Skip `.venv/`,
`__pycache__/`, migrations.

### Stage 2 — Public surface + AST inventory

**Pre:** file list. **Post:** `$SCRATCH/symbols.jsonl` — one line per
top-level declaration with `{file, name, kind, is_public, decorators,
lineno, loc}`. `is_public` = not leading underscore AND not in a
module-level `__all__` that excludes it.

Reuse `scripts/chunk_file.py --format json` for files > 2,000 LOC (it
emits declarations). For smaller files, run an AST walk directly.

### Stage 3 — Responsibility clusters (SRP-lite)

**Pre:** symbols.jsonl. **Post:** `$SCRATCH/clusters.jsonl` — one line
per cluster with `{cluster, symbols, loc_sum, domain_hint}`.

Group top-level symbols by noun extraction on the function/class name
(e.g. `upload_*`, `download_*`, `process_*` become three clusters).
Apply the SRP sentence test over the cluster names — if three or more
"and"-joinable domains show up, flag the file as omnibus-candidate.

Do **not** run a full SOLID audit here — the full audit lives in
`refactor-subsystem` §1.2.5. The MAP skill just counts clusters.

### Stage 4 — Dependency graph

**Pre:** file list. **Post:** `$SCRATCH/deps.json` with
`{internal_imports, external_imports, inbound}` — inbound edges come
from a repo-wide grep for `from <subsystem> import` plus `import <subsystem>`.

Bounded cost: use `Grep` with glob-filtering, cap at 200 files per
direction.

### Stage 5 — Convention-compliance score

**Pre:** file list. **Post:** `$SCRATCH/compliance.json` with per-rule
counts.

Run:
- `.venv/bin/ruff check <target> --select F,E,B,BLE --output-format=json`
- `.venv/bin/python scripts/lint/silent_catch.py <target>` (count
  violations).
- Future: new rule counters as `/prevent-regression` adds them.

Record raw counts. Do not fail the skill on non-zero counts — that's
guard territory.

### Stage 6 — Render the subsystem doc

**Pre:** stages 1–5 outputs. **Post:** `$OUTPUT_PATH` written.

Format per `knowledge/output-format.md`. Structure:

1. Front-matter header (subsystem name, path, regenerated timestamp,
   prior-run timestamp if `--refresh`).
2. **Diff section** (only on `--refresh`) — symbols added/removed,
   cluster count delta, compliance-score delta.
3. **Files** — table from Stage 1.
4. **Public surface** — grouped by file, from Stage 2's `is_public`.
5. **Responsibility clusters** — table from Stage 3.
6. **Dependency graph** — internal and external, rendered as a markdown
   list; link inbound edges to the calling subsystem's map page if it
   exists.
7. **Workflow participation** — links to product workflow maps when
   this subsystem appears in their route, template, JS, status, or docs
   inventory.
8. **Convention compliance** — table from Stage 5 with one row per
   rule and raw counts.
9. **Open questions** — auto-generated from unexplained regions (top-
   level symbols with no docstring + complex bodies). These are
   hints for a follow-on `/explain-code` run.

### Stage 7 — Append to effectiveness log

**Pre:** doc written. **Post:** one new line in
`reports/_meta/effectiveness.jsonl`.

Schema:
```json
{"skill":"map-subsystem","scan_id":"map-<name>-<ts>","ts":"...",
 "findings_total":<cluster_count>,
 "buckets":{"files":N,"public_symbols":N,"clusters":N,"compliance_violations":N},
 "target":"<subsystem name>"}
```

### Stage 8 — Summarize to user

Report in ≤10 lines:
- name, output path, timestamp.
- file count, public-symbol count, cluster count.
- compliance-violation count (per rule, if non-zero).
- **one-sentence hint** pointing at the next job in the loop, chosen
  from the SUSPECT/EXPLAIN catalog in `.claude/docs/skill-catalog.md`:
  - compliance violations present → cite the affected canonical
    pattern in CLAUDE.md and, if the cleanup is in scope, suggest
    running `/fix-workflow` on the affected cluster.
  - clear duplication signals in the files table (same function names
    across files, near-duplicate symbol lists) → suggest
    `/find-duplication` or `/find-semantic-duplication` on the target.
  - potential dead code (public symbols with no inbound references in
    the dependency graph) → suggest `/find-dormant`.
  - SRP "and"-count ≥ 3 in a single file → suggest `/find-omnibus`.
  - stringly-typed `status` fields or tuple-inferred identity signals
    → suggest `/find-implicit-state`.
  - read-named methods that mutate → suggest `/find-query-mutation`.
  - view/task modules owning business logic → suggest
    `/find-layer-violation`.
  - subsystem appears in a workflow map with duplicated route/template/
    JS ownership → suggest the product-topology skills:
    `/find-route-sprawl`, `/find-workflow-duplication`, or
    `/find-frontend-contract-drift`.
  - a specific file needs to be understood before it can be changed →
    suggest `/explain-code`.
  - otherwise → nothing; the map is the artifact.

The doc is the source of truth — do not enumerate its contents in the
summary.

## Non-goals

- Refactoring.
- Detecting smells (that's SUSPECT skills).
- Proposing fixes.
- Editing any file except `$OUTPUT_PATH` and the effectiveness log.
- Running tests.
- Generating diagrams that require non-repo tooling (graphviz, mermaid
  renderers). Plain markdown only.

## When things go sideways

| Symptom | Action |
|---|---|
| Target path doesn't exist | Abort with a one-line error + suggestion to re-run with the correct path |
| `scripts/chunk_file.py` errors on a non-Python file | Flag in the doc's Files section; skip AST inventory for that file |
| Existing doc + no `--refresh` flag | Warn and exit; don't overwrite |
| `reports/_meta/` missing | Create it — `reports/_meta/README.md` is already tracked so the dir exists in committed state |

## Repository layout

```
.claude/skills/map-subsystem/
├── SKILL.md                      # this file — orchestrator
├── scripts/
│   └── render_doc.py             # Stages 6-7 — renders the doc + appends log
├── agents/                       # (reserved for future scout-assisted excavation)
└── knowledge/
    └── output-format.md          # doc structure + worked example
```
