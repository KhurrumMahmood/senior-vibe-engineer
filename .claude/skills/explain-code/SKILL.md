---
name: explain-code
description: Read-only EXPLAIN skill that converts a file, directory package, or named subsystem into an annotated behavior doc at reports/explanations/<target>.md. Fans out scout sub-agents per public symbol to capture intent, pre/postconditions, invariants, callers, and unexplained regions. Complements /map-subsystem (inventory) by producing the behavioral annotation that lets a human trust the code well enough to change it. Hands off to /fix-workflow or /refactor-subsystem when the unexplained regions resolve into concrete smells.
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
language: python
framework: django
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

Procedural detail lives in the knowledge files:

- `knowledge/` — shared conventions pointer +
  explanation-specific rules.
- `knowledge/explanation-format.md` — the exact shape of
  `reports/explanations/<target>.md`.
- `agents/annotate.md` — scout brief for per-symbol behavior capture.

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

## Scope

- **Project root:** this worktree's root.
- **Python:** `python3` for `scripts/inventory_symbols.py` (stdlib-
  only); `.venv/bin/python` only if a scout needs to import Django
  models (uncommon in EXPLAIN work — annotations are source-level).
- **Output:** `reports/explanations/<target-slug>.md` and
  `reports/explanations/<target-slug>/annotations/<symbol>.md`. Never
  touches any other file.
- **Project-specific conventions** (subsystem name resolution,
  unexplained-region heuristics): `knowledge/`.
  Scouts read that file; the orchestrator does not.

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
`knowledge/` for the ranking rule). If the target
exceeds that, the Stage-1 ranking surfaces the most useful 15 and
the rest are listed as follow-on candidates in the summary.

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed. **Post:** `$REPORT_DIR` exists,
`latest` symlink updated.

```bash
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

2. **No map page.** Run the AST inventory helper:

   ```bash
   python3 .claude/skills/explain-code/scripts/inventory_symbols.py \
     --target "<target-path>" \
     --output "${REPORT_DIR}/targets.json" \
     --max 15
   ```

   The helper walks the AST, enumerates public symbols (functions,
   classes, class methods — no leading underscore, not in a module
   `__all__` that excludes them), computes LOC + branch-count
   approximation + `has_docstring` flag, and ranks by
   `(no_docstring, branch_count, LOC > 50)` descending. Output schema
   is documented in the helper's module docstring.

If the inventory returns zero symbols, abort with a one-line error:
the target is either empty, private-only, or misresolved.

### Stage 2 — Annotate (parallel fan-out)

**Pre:** `targets.json`. **Post:**
`${REPORT_DIR}/annotations/<symbol-key>.md` for every target (up to 15).

For each target, expand `agents/annotate.md` (substitute
`{{target_slug}}`, `{{symbol_key}}`, `{{file_path}}`, `{{symbol}}`,
`{{kind}}`, `{{project_root}}`, `{{skill_root}}`, `{{output_path}}`)
and dispatch each scout with `subagent_type=general-purpose`. Send
every Agent call in a **single message** so they run concurrently.

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

Read every annotation file. Write the top-level doc following
`knowledge/explanation-format.md`. Structure (see knowledge file for
the exact template):

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

### Stage 4 — Effectiveness log

**Pre:** explanation doc written. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

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
PUBLIC=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["targets"]))' "${REPORT_DIR}/targets.json")

python3 scripts/log_effectiveness.py \
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
- Touching production code.
- Running tests — the explanation is source-level.

## When things go sideways

| Symptom | Action |
|---|---|
| Target path doesn't exist | Abort with a one-line error + suggestion to re-run with the correct path |
| AST walk errors on a non-Python file | Skip it, flag in the doc's "Files" metadata |
| `targets.json` lists 0 symbols | Target is empty or private-only — abort with a one-line message |
| Scout returns `annotation_incomplete` on first try | Re-dispatch once with a stricter "respond only with file-write confirmation" nudge |
| Two scouts produce contradictory caller lists | Both may be right (method name shadowed across classes) — note the conflict in the doc and move on |
| Map-page reference for a subsystem with no `.claude/docs/subsystems/<name>.md` | Fall back to AST inventory; do not silently produce a different output |
| `--refresh` semantics | Not supported — re-runs always overwrite. The git history of `<target-slug>.md` is the diff. |

## Repository layout

```
.claude/skills/explain-code/
├── SKILL.md                         # this file — orchestrator
├── scripts/
│   └── inventory_symbols.py         # Stage 1 AST inventory (stdlib-only)
├── agents/
│   └── annotate.md                  # Stage 2 scout brief
└── knowledge/                       # scout context, never loaded by orchestrator
    └── explanation-format.md        # output doc structure + worked example
```

The orchestrator (you) **never reads files in `knowledge/`**. Those
are for the scout sub-agents. Keeping them out of your context is the
whole point of this architecture.
