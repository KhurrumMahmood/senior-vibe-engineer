---
name: explain-code
description: Read-only EXPLAIN skill that converts a Python target or a TypeScript/TSX target's direct public exports into an annotated behavior doc at reports/explanations/<target>.md. TypeScript v1 visibly leaves aliases and re-exports unexplained rather than claiming module resolution.
argument-hint: "<file-path-or-directory-or-subsystem-name>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: explain
best_for: |
  Producing an annotated behavior doc for a file, directory package,
  or named subsystem — pre/postconditions, invariants, callers,
  unexplained regions. Read-only. Complements /map-subsystem inventory
  by adding the behavioral annotation that lets a human trust the code
  enough to change it.
not_for: |
  Pure inventory without behavioral annotation (use /map-subsystem).
  Cross-workflow product topology (use /map-product-workflow).
  Refactor execution (use /fix-workflow or /refactor-subsystem).
language: any
framework: any
scans: [python, typescript]
---

# /explain-code

You are the **orchestrator** for an EXPLAIN skill. Given a target path,
a directory package, or a `/map-subsystem` name, you produce
`reports/explanations/<target-slug>.md` — an annotated behavior doc
that lets a human (or future agent) *trust* the code well enough to
change it.

You do not edit production code. You do not refactor. You do not
propose structural changes. This skill writes down what the code
**does** today so that downstream SUSPECT and REFACTOR skills have a
reliable contract to reason against.

`/map-subsystem` answers *what's in this subsystem?* — file list,
public surface, responsibility table, dependency graph.
`/explain-code` answers *what does it enforce?* — per-symbol intent,
pre/postconditions, invariants, callers, and the unexplained regions
that remain. The two skills are complementary; run MAP first when the
inventory is stale, then EXPLAIN when the behavior is unclear.

Procedural detail lives in the skill-local files:

- `knowledge/explanation-format.md` — the exact shape of
  `reports/explanations/<target>.md`. The orchestrator reads it in
  Stage 3 before synthesizing the top-level explanation.
- `agents/annotate.md` — scout brief for per-symbol behavior capture.

## How success is judged

- Every ranked symbol in `targets.json` (up to the 15-symbol cap) has
  a scout annotation at `annotations/<symbol-key>.md` synthesized into
  `reports/explanations/<target-slug>.md` — symbols over budget are
  listed as follow-on candidates, never silently omitted.
- Unexplained regions are first-class output: a branch the scout
  could not explain is recorded as such, never papered over with an
  invented behavior claim.
- Zero edits outside `reports/explanations/` — the doc is the
  contract downstream `/fix-workflow` / `/refactor-subsystem` work
  reasons against.
- Artifact truth, not run claims: the closing summary cites the
  inventory command output, the annotation count command, the sidecar
  `wc -l` output, and the effectiveness-log command output when it
  runs. A claim that a doc or sidecar was written is invalid without
  the pasted command output or file path.
Write toward these gates from Stage 0.

## Core beliefs

1. **Explanation is a proposal artifact.** The doc is written once,
   reviewed, and referred back to — it lives at a target-keyed path
   (`reports/explanations/<target-slug>.md`) so re-runs overwrite
   and the git history is the record.
2. **Public symbols get the budget.** Private helpers are inventory;
   public symbols are the contract. Budget is spent annotating
   public symbols, not private helpers.
3. **Unexplained regions are first-class output.** A scout that can't
   explain a branch without reading three more files says so — that
   block becomes a follow-on `/explain-code` candidate, not a guess.
4. **Symbolic names, never raw line numbers** (see `_common/skill-conventions.md`
   "No raw line numbers in prose").
5. **Scouts read, orchestrator consolidates.** Each target symbol gets
   its own scout (`agents/annotate.md`). The orchestrator merges
   annotations into the top-level explanation doc.

## TypeScript v1 contract

For a `.ts` or `.tsx` file (or directory), the supported invariant is:
**each named, direct, top-level export receives the same complete explanation
document and sidecars as a Python public symbol.** Direct exported functions,
classes, enums, interfaces, types, namespaces, and variables are eligible.

The collector is intentionally lexical. It does not resolve imports, aliases,
barrels, `export { ... }`, `export *`, `export type *`, or default expressions.
Those forms are written to `targets.json`'s `unexplained` list and must appear
in the final document and `unexplained.txt`; do not replace that region with an
inferred contract. A re-export-only target therefore has zero scout targets but
still proceeds to synthesis so its unresolved public surface remains visible.
Before writing inventory, a bounded lexical integrity check rejects unterminated
comments, strings, templates, or regex literals and unbalanced delimiters. This
is not a TypeScript grammar or type check. The collector ignores test,
generated, declaration, vendor, build, and
`node_modules` descendants relative to the requested target. The TypeScript
v1 contract makes no React, Node, framework, type-checker, or module-resolution
claim.

Python remains the reference inventory path and has the same stable
`targets.json` schema, but the installed router must advertise this revision as
TypeScript-only until it can express multi-language eligibility. Do not infer
that a successful TypeScript run supports another language.

## Scope

- **Project root:** this worktree's root.
- **Executor:** `${PYTHON:-python3}`. Both helpers are stdlib-only and run
  from a copied installed skill with `python3 -I -S`; use the repository's
  `.venv/bin/python` while validating this source checkout.
- **Output:** `reports/explanations/<target-slug>.md` and
  `reports/explanations/<target-slug>/annotations/<symbol>.md`. Never
  touches any other file.
- **Output-format conventions:** `knowledge/explanation-format.md`.
  The orchestrator reads this file in Stage 3. Scouts do not read
  `knowledge/`; they follow `agents/annotate.md`.

## Argument parsing

Two forms:

### Form A — target path
File: `core/services/agentic_discovery_service.py`.
Directory package: `core/services/discovery_field_matcher/`.
Module within a package: `core/views/brand_downloads/exports.py`.

Derive the slug from the path: strip `core/`, replace `/` with `-`,
strip `.py`. Examples:
- `core/services/agentic_discovery_service.py` → `services-agentic-discovery-service`
- `core/services/discovery_field_matcher/` → `services-discovery-field-matcher`
- `core/views/brand_downloads/` → `views-brand-downloads`

### Form B — subsystem name
Pattern: kebab-case, `<layer>-<domain>` (e.g. `services-agentic-discovery-service`,
`views-crawling`). Resolves against `.claude/docs/subsystems/<name>.md` if
a map exists; the map's "target" front-matter field gives the path.

If neither a map page nor a matching path resolves, ask the user once
to confirm the path. Do NOT guess.

### Budget cap
Cap at **15 annotated symbols per run** (see
the Stage-1 ranking rule below). If the target
exceeds that, the Stage-1 ranking surfaces the most useful 15 and
the rest are listed as follow-on candidates in the summary.

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed. **Post:** `$REPORT_DIR` exists,
`latest` symlink updated.

```bash
PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
SKILL_ROOT="${SKILL_ROOT:-.claude/skills/explain-code}"
TARGET_SLUG="<derived slug>"
REPORT_DIR="reports/explanations/${TARGET_SLUG}"
mkdir -p "${REPORT_DIR}/annotations"
ln -sfn "${TARGET_SLUG}" reports/explanations/latest
```

Target-keyed path (not timestamped) — the same rationale as
`/unify-shadows`: re-runs against the same target converge, and the
git history of `<target-slug>.md` is the historical record.

### Stage 1 — Inventory

**Pre:** argument parsed. **Post:** `${REPORT_DIR}/targets.json`
listing the annotatable symbols, ranked.

Two paths:

1. **Map page exists.** Read `.claude/docs/subsystems/<name>.md`.
   Lift the public-surface symbols from the "Public surface" section
   and the open-questions list from "Open questions". Produce
   `targets.json` with those symbols, prioritizing any that appear
   under "Open questions".

2. **No map page.** Run the standalone inventory helper. It uses the Python
   AST reference path for `.py`, and a direct-export lexical path for `.ts` /
   `.tsx`:

   ```bash
   "${PYTHON:-python3}" "${SKILL_ROOT}/scripts/inventory_symbols.py" \
     --target "<target-path>" \
     --output "${REPORT_DIR}/targets.json" \
     --max 15
   ```

   The Python reference path walks the AST; the TypeScript path collects only
   named direct exports after its bounded lexical integrity check. Both compute
   a stable LOC + branch-count approximation and rank by `(no_docstring,
   branch_count, LOC > 50)` descending. Before dispatching scouts, read
   `targets.json`: every `unexplained` export is a mandatory final-doc region,
   not a scout target.

If the inventory returns neither symbols nor unexplained regions, abort with a
one-line error: the target is either empty, private-only, or misresolved. If it
returns only unexplained regions, skip scout dispatch and proceed to synthesis.

### Stage 2 — Annotate (parallel fan-out)

**Pre:** `targets.json`. **Post:**
`${REPORT_DIR}/annotations/<symbol-key>.md` for every target (up to 15).

For each target, expand `agents/annotate.md` (substitute
`{{target_slug}}`, `{{symbol_key}}`, `{{file_path}}`, `{{symbol}}`,
`{{kind}}`, `{{project_root}}`, `{{skill_root}}`, `{{output_path}}`)
and dispatch each scout with `subagent_type=general-purpose`. Send
every Agent call in a **single message** so they run concurrently.
The dispatch prompt must include the scout's declared verdict: the run
is judged on whether `{{output_path}}` exists, uses the exact annotation
sections from `agents/annotate.md`, cites real caller evidence, and
records unexplained regions honestly instead of inventing behavior.

Each annotation captures:

- **Intent** — one-paragraph description of what this does.
- **Contract** — preconditions (what callers must ensure before
  calling), postconditions (what's returned / what side-effects
  happen), raises.
- **Invariants** — assertions that hold throughout execution, often
  implicit (e.g. "`state['budget']['pages_remaining']` is decremented
  exactly once per page fetch").
- **Callers** — who invokes this and what they expect back. Scouts
  grep the codebase.
- **Unexplained regions** — branches or blocks the scout cannot
  explain without reading more code. Each becomes a follow-on
  `/explain-code` candidate for a deeper target.
- **Surprising behavior** — anything a new reader would not predict
  from the symbol's name (silent fallbacks, return-None paths that
  look like raises, state mutation in a `get_*` method, etc.).

If a scout returns `annotation_incomplete`, re-dispatch once with a
nudge ("return ONLY the annotation file path written — no other
text"). If it fails twice, proceed with partial annotations and flag
the gap in the synthesized doc.

### Stage 3 — Synthesize

**Pre:** all annotations on disk. **Post:**
`reports/explanations/${TARGET_SLUG}.md`.

Read `knowledge/explanation-format.md`, then read every annotation
file. Supply a truthful ≤5-sentence summary and render the top-level doc with
the installed helper. It verifies every selected annotation uses the scout's
required sections and writes the mandatory sidecars:

```bash
"${PYTHON:-python3}" "${SKILL_ROOT}/scripts/render_explanation.py" \
  --targets "${REPORT_DIR}/targets.json" \
  --annotations-dir "${REPORT_DIR}/annotations" \
  --output "reports/explanations/${TARGET_SLUG}.md" \
  --summary "<what it does; what it enforces; what it does not enforce>" \
  --project-root "$PROJECT_ROOT"
```

The renderer never invents behavioral claims. It aggregates each scout's
annotation and the inventory's unresolved export records. For the lexical
TypeScript path, describe type signatures as source declarations only: no
compiler ran, so never say the skill enforces, validates, or type-checks them.
Structure:

1. Target metadata (path, LOC, public symbol count, regenerated
   timestamp).
2. Summary (≤5 sentences) — what it does, what it enforces, what it
   doesn't enforce.
3. Public contracts — one subsection per annotated symbol, pulling
   the fields above from the per-symbol annotations.
4. Unexplained regions — aggregated from the scouts' outputs. Each
   entry is a one-liner describing why it's unexplained plus a
   suggested deeper target for a re-run.
5. Follow-on findings — adjacent rot surfaced during annotation
   (candidates for any SUSPECT skill: `/find-dormant`,
   `/find-duplication`, `/find-semantic-duplication`, `/find-omnibus`,
   `/find-implicit-state`, `/find-query-mutation`,
   `/find-layer-violation`).
6. How to regenerate — literal single-line command.

Also write the two sidecar files consumed by Stage 4:

- `${REPORT_DIR}/unexplained.txt` — one `- <symbol> — <reason>` line
  per unexplained region, empty file when none exist.
- `${REPORT_DIR}/surprises.txt` — one `- <symbol> — <surprise>` line
  per surprising behavior item, empty file when none exist.

These files are mandatory Stage 3 outputs. Stage 4's missing-file
fallback is defensive recovery for interrupted runs, not permission to
omit the sidecars.

### Stage 4 — Optional host effectiveness log

**Pre:** explanation doc written. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl` only when the host separately owns an
effectiveness logger. This is not part of the copied TypeScript v1 closure:
the selected skill must not reach back into toolkit-level `scripts/` merely to
log telemetry.

```bash
ANNOTATED=$(ls "${REPORT_DIR}/annotations/" 2>/dev/null | wc -l | tr -d ' ')
if [ -f "${REPORT_DIR}/unexplained.txt" ]; then
  UNEXPLAINED=$(grep -c '^- ' "${REPORT_DIR}/unexplained.txt" || true)
else
  UNEXPLAINED=0
fi
if [ -f "${REPORT_DIR}/surprises.txt" ]; then
  SURPRISES=$(grep -c '^- ' "${REPORT_DIR}/surprises.txt" || true)
else
  SURPRISES=0
fi
PUBLIC=$("${PYTHON:-python3}" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["targets"]))' "${REPORT_DIR}/targets.json")

"${PYTHON:-python3}" scripts/log_effectiveness.py \
  --skill explain-code \
  --scan-id "explanation-${TARGET_SLUG}-$(date -u +%Y%m%d-%H%M%S)" \
  --target "<original-target-path>" \
  --findings-total "${ANNOTATED}" \
  --buckets "{\"public_symbols\": ${PUBLIC}, \"annotated\": ${ANNOTATED}, \"unexplained\": ${UNEXPLAINED}, \"surprises\": ${SURPRISES}}"
```

The synthesis step writes `unexplained.txt` and `surprises.txt`
alongside the main doc — one line per item — so this step doesn't
re-parse markdown.

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- Target path + slug.
- Public symbols found / annotated (e.g. `22 public / 15 annotated`).
- Unexplained regions flagged (count + first two).
- Surprises found (count + first one).
- Path to `reports/explanations/${TARGET_SLUG}.md`.
- Recommended next step:
  - surprises are structural (layer violation, omnibus, hidden mutation) →
    cite the smell in `.claude/docs/architectural-smells.md` and
    suggest `/refactor-subsystem` driven by a spec in `ai-docs/specs/`.
  - a specific bug or narrow fix surfaced → suggest `/fix-workflow`.
  - unexplained regions remain and are the user's blocker → suggest
    re-running `/explain-code <deeper-target>` on the cited symbol.
  - otherwise → nothing; the doc is the artifact.

Do not enumerate annotations in the summary — the doc is the source
of truth.

## Non-goals

- Refactoring (that's `/fix-workflow` or `/refactor-subsystem`).
- Detecting smells (that's SUSPECT skills). The unexplained-regions
  and surprises sections are **flags**, not diagnoses.
- Proposing structural changes. The doc records the current contract;
  it does not propose a new one.
- Annotating every symbol. Budget is 15 per run; the remainder become
  follow-on candidates.
- Resolving TypeScript modules, export aliases, barrels, or default
  expressions. Keep them visibly unexplained until a separately accepted
  resolver-backed contract exists.
- Including TypeScript test, generated, declaration, vendor, build, or
  `node_modules` files in a directory inventory.
- Touching production code.
- Running tests — the explanation is source-level.

## When things go sideways

| Symptom | Action |
|---|---|
| Target path doesn't exist | Abort with a one-line error + suggestion to re-run with the correct path |
| Inventory sees an alias/re-export/default expression | Keep its `unexplained` record in the final doc; do not dispatch a scout that invents resolution |
| Target has only unsupported / ignored source files | Abort with a one-line message; do not fall back to scanning tests or vendor code |
| TypeScript lexical integrity check fails | Abort without writing `targets.json`; report the source file and malformed construct |
| `targets.json` lists 0 symbols and 0 unexplained regions | Target is empty or private-only — abort with a one-line message |
| `targets.json` lists 0 symbols but has unexplained regions | Skip scouts and render the unresolved public surface and sidecars |
| `knowledge/explanation-format.md` is missing or empty | Abort before synthesis; the top-level doc shape is undefined |
| Stage 3 cannot write `unexplained.txt` or `surprises.txt` | Stop before effectiveness logging and report the exact write failure |
| Scout returns `annotation_incomplete` on first try | Re-dispatch once with a stricter "respond only with file-write confirmation" nudge |
| Two scouts produce contradictory caller lists | Both may be right (method name shadowed across classes) — note the conflict in the doc and move on |
| Map-page reference for a subsystem with no `.claude/docs/subsystems/<name>.md` | Fall back to AST inventory; do not silently produce a different output |
| `--refresh` semantics | Not supported — re-runs always overwrite. The git history of `<target-slug>.md` is the diff. |

## Replay case

After material edits to this skill, prove the inventory boundary still
works and paste the real output:

```bash
.venv/bin/python .claude/skills/explain-code/scripts/inventory_symbols.py \
  --target .claude/skills/explain-code/scripts/inventory_symbols.py \
  --output /tmp/explain-code-targets.json \
  --max 3
```

Then verify `knowledge/explanation-format.md` is non-empty and that
Stage 3 can name both sidecars:

```bash
test -s .claude/skills/explain-code/knowledge/explanation-format.md && \
  printf 'format-present\n'
```

## Repository layout

```
.claude/skills/explain-code/
├── SKILL.md                         # this file — orchestrator
├── scripts/
│   ├── inventory_symbols.py         # Stage 1 Python/TS inventory (stdlib-only)
│   └── render_explanation.py        # Stage 3 document + sidecar renderer
├── agents/
│   └── annotate.md                  # Stage 2 scout brief
└── knowledge/                       # orchestrator output-format reference
    └── explanation-format.md        # output doc structure + worked example
```
