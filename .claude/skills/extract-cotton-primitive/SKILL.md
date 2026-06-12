---
name: extract-cotton-primitive
description: Turn a confirmed frontend duplication candidate into a cotton primitive proposal. Consumes a finding from /find-frontend-duplication (or an explicit category target like `modal-shell`) and emits reports/extract-cotton-primitive/<target>/proposal.md with the `<c-vars>` declaration, primitive body, callsite migration table, JS-partner notes, and stop condition. Read-only — no template/JS edits. Hands off to /refactor-subsystem or manual extraction.
argument-hint: "<frontend-dup:ID or candidate-category>"
allowed-tools: Bash, Read, Grep, Glob, Write, Agent
user-invocable: true
tier: maintenance
job: explain
best_for: |
  A confirmed frontend-duplication candidate ready for a cotton
  primitive proposal — produces the `<c-vars>`/body/slot shape, the
  callsite migration table, and the JS-init contract (idempotent guard,
  data-attr binding). Read-only. Decided in: cotton-components
  doctrine.
not_for: |
  Detection (use /find-frontend-duplication first). JS-only helper
  forks like `escapeHtml` / `siteEndpoint` (those need a manual
  consolidation in `static/js/site-config-core.js`, not a cotton
  primitive). CSRF wrapper extraction (also a JS-side fix, not
  cotton). Refactor execution (use /refactor-subsystem).
language: python
framework: django
---

# /extract-cotton-primitive

You are the **orchestrator** for turning a duplicated UX shell into a
cotton primitive proposal. `/find-frontend-duplication` already
flagged the candidate; your job is to read the representative
callsites in full, dispatch a scout to design the primitive's
`<c-vars>` API + body shape + migration table, and consolidate into a
proposal the human reviews before handing off to manual extraction or
`/refactor-subsystem`.

You do NOT write production templates or JS in this skill. You never
edit `templates/cotton/`, the callsites, or any JS partner. The only
artifact you produce is
`reports/extract-cotton-primitive/<target-slug>/proposal.md` plus its
supporting `targets.json` and `profile.md`.

## How success is judged

- `proposal.md` is complete per the Stage 3 structure: `<c-vars>`
  declaration and primitive body from `primitive.md`, the census
  reconciliation, callsite migration table (before/after per site),
  JS-partner notes with the idempotent-init guard, and stop condition.
- The three-callsite, two-template rule held — below threshold the
  proposal says `defer_low_callsite_count`, never forces a primitive.
- Zero edits to `templates/cotton/`, callsites, or JS — execution is
  `/refactor-subsystem`'s or the human's, after review.
Write toward these gates from Stage 0.

## Core beliefs

1. **Three-callsite, two-template rule.** A primitive lands only if
   3+ structural callsites span 2+ templates with stable structure.
   The scout enforces this via `knowledge/cotton-conventions.md`. If
   the candidate falls below threshold, the proposal recommends
   `defer_low_callsite_count` instead of an extraction.
2. **Cotton conventions are non-negotiable.** A new primitive must
   declare `<c-vars>`, pass `{{ attrs }}` through on the root, use the
   `tone` prop pattern for color variants, and (if it carries JS)
   guard init with `if (window.__appFooInit) return; ...` — see
   `knowledge/cotton-conventions.md`.
3. **One target per run.** If profiling surfaces a *separate*
   primitive opportunity in the same candidate (e.g. the modal panel
   and the modal close-button could each be their own primitive), log
   it under follow-on findings and stop. Running the skill twice is
   cheaper than one over-scoped proposal.
4. **The proposal is read-only.** No template edits, no JS edits, no
   migration files. The execution skill handles that after human
   review.
5. **Migration is a per-callsite rewrite, not a bulk replace.** Each
   callsite in the migration table gets a before / after snippet so
   the human can sanity-check that the primitive captures intent
   without losing per-callsite specifics.

## Scope

- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` (never bare `python`).
- **Read-only:** no production edits.
- **Project-specific defaults:** in `knowledge/cotton-conventions.md`
  and `knowledge/migration-patterns.md`. The scout reads those; the
  orchestrator does not.

## Argument parsing

Two forms:

### Form A — Candidate ID from /find-frontend-duplication

Pattern: `frontend-dup:<id>` or `<id>` where `<id>` matches a
12-char hex from a `/find-frontend-duplication` run. Resolves
against `reports/frontend-duplication/latest/findings.json`. The
orchestrator reads the candidate's `category`, `evidence`,
`existing_primitive`, and `primitive_bypass`. If
`primitive_bypass: true`, the proposal is an *adoption* plan, not an
*extraction* plan — the existing primitive already covers the case.

If the findings file is missing, abort and tell the user to run
`/find-frontend-duplication` first — do NOT fall back to scanning.

### Form B — Explicit category target

Pattern: `modal-shell` / `dropdown-menu` / `filter-pill` / etc. The
orchestrator runs the scanners directly to gather evidence for the
named category, then proceeds. Use this when you already know what
you want to extract.

For Form B, parse the category, present the inferred target back to
the user (`category`, `expected_callsite_count_floor`), and wait for
approval (same approval token contract: first non-whitespace token is
`approved`, `approve`, `go`, `lgtm`, `proceed`, `yes`).

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed, approval received (Form B only). **Post:**
`${REPORT_DIR}` exists, `latest` symlink.

```bash
TARGET_SLUG="<category>"   # e.g. "modal-shell", or "<id>" for Form A
REPORT_DIR="reports/extract-cotton-primitive/${TARGET_SLUG}"
mkdir -p "${REPORT_DIR}"
ln -sfn "${TARGET_SLUG}" reports/extract-cotton-primitive/latest
```

`reports/extract-cotton-primitive/` uses target slugs directly so
successive runs against the same candidate overwrite.

### Stage 1 — Profile

**Pre:** argument parsed. **Post:** `${REPORT_DIR}/profile.json` —
each representative callsite's surrounding markup bundled for the
scout to read.

```bash
.venv/bin/python .claude/skills/extract-cotton-primitive/scripts/profile.py \
  ${FINDING_ID:+--from-finding "${FINDING_ID}"} \
  ${CATEGORY:+--category "${CATEGORY}"} \
  --findings reports/frontend-duplication/latest/findings.json \
  --candidates reports/frontend-duplication/latest/candidates.json \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/profile.json"
```

The profiler writes to stderr a one-line summary:
`<category> — N representative callsites across K files`. If zero
callsites can be loaded, exit 1 — the candidate references files that
don't exist.

### Stage 1.5 — Census (variant histogram)

**Pre:** argument parsed. **Post:** `${REPORT_DIR}/census.json` —
canonical-variant histogram of every occurrence the candidate carries.
Skipping this stage is the bug Phase G's `<c-alert>` sweep paid for:
the primitive shipped with `px-4 py-3` (5 callsites) but 104
hand-rolled callsites used `p-4`; the doctrine call (change the
default to `p-4` *before* sweep) only became visible after a
frequency rank.

```bash
.venv/bin/python .claude/skills/extract-cotton-primitive/scripts/census.py \
  ${FINDING_ID:+--from-finding "${FINDING_ID}"} \
  ${CATEGORY:+--category "${CATEGORY}"} \
  --candidates reports/frontend-duplication/latest/candidates.json \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/census.json"
```

Stderr summary: `<category> — N occurrences in V variant(s); dominant
P% (tight | HIGH-VARIANCE) [sample-only: M/N]`. The scout reads this
file before designing the primitive — it informs whether the proposal
needs a "change primitive defaults first" call before migration.

If `sample_only` is true (the candidate's per-occurrence sample is
smaller than the full scan count), the scout should treat dominance as
a lower-bound estimate and consider re-grepping the chain across the
full template tree before committing to a doctrine call.

### Stage 2 — Propose the primitive (single scout)

**Pre:** `profile.json` and `census.json` exist. **Post:**
`${REPORT_DIR}/primitive.md` exists with the `<c-vars>` declaration,
proposed body, migration table, and primitive-default reconciliation.

Dispatch ONE scout (not fan-out) with `agents/propose.md`. Substitute
placeholders:

- `{{target_slug}}`, `{{category}}` — from the resolved target
- `{{project_root}}` — `$(pwd)` absolute
- `{{profile_path}}` — absolute path to `${REPORT_DIR}/profile.json`
- `{{census_path}}` — absolute path to `${REPORT_DIR}/census.json`
- `{{output_path}}` — absolute path to `${REPORT_DIR}/primitive.md`
- `{{skill_root}}` — absolute path to
  `.claude/skills/extract-cotton-primitive/`

Use `subagent_type=general-purpose`.

If the scout returns `profile_incomplete` or
`conventions_violation`, re-dispatch once with a stricter brief. If
it fails twice, proceed with a partial primitive and flag the gap in
the proposal.

### Stage 3 — Synthesize the proposal

**Pre:** `primitive.md` exists. **Post:** `${REPORT_DIR}/proposal.md`
written.

Read `profile.json` + `census.json` + `primitive.md`. Write
`proposal.md` with this structure:

```markdown
# Proposal — extract-cotton-primitive: <category>

## Target
<category> shell duplicated <N>× across <K> templates. From
`/find-frontend-duplication` candidate `<id>`.

## Distinct callsites profiled (<R> representatives)
<bullet list from profile.json: file:line, one-line role description>

## Census
<from census.json: total occurrences, dominant variant + share, tail
count, high-variance flag, sample-only flag if applicable>

## Primitive defaults reconciliation
<from primitive.md "Primitive defaults reconciliation" section: does
the dominant variant match the (existing or proposed) primitive
defaults? If not, this section calls out which doctrine change must
ship *before* the migration sweep. Phase G's `<c-alert>` lesson —
extracting against a non-dominant default forces every callsite to
re-justify the diff.>

## Proposed primitive

`templates/cotton/<name>.html`:

\`\`\`html
<c-vars ... />

<root-element {{ attrs }} class="...">
    {{ slot }}
</root-element>
\`\`\`

(Body and `<c-vars>` from primitive.md.)

## JS partner (if any)
<from primitive.md, including idempotent-init guard and data-attr
contract>

## Callsite migration table
<table from primitive.md: file:line | before | after>

## Doctrine compliance check
- [x] `<c-vars>` declared — yes
- [x] `{{ attrs }}` pass-through on root — yes
- [x] Tone prop using `{tone}-` Tailwind family — yes
- [x] No raw `alert()` / `confirm()` / `prompt()` — yes
- [x] Idempotent JS init guard if scripts present — N/A or yes
- [x] 3+ callsites across 2+ templates — yes (<N> across <K>)

## Lint coverage
After this primitive lands, add a diff-scoped lint to prevent
regressions:

\`\`\`bash
.venv/bin/ruff check --add-select <rule-code> ...
# or stdlib lint at scripts/lint/no_inline_<category>.py
\`\`\`

(Concrete rule path from primitive.md if scout proposed one.)

## Stop condition
- Primitive added at `templates/cotton/<name>.html`.
- Every callsite in the migration table replaced with the primitive.
- New lint guards new bypasses.
- Targeted Playwright suite passes (`testing/test_site_pages.py`).
- Always-suite passes (`tests.test_site_capabilities
  tests.test_hydration_detector`).

## Follow-on findings
<other primitive opportunities surfaced during profiling; NOT part of
this proposal — each is a new `/extract-cotton-primitive` invocation>

## Authorization
Human review required before execution. If approved, hand the proposal
to `/refactor-subsystem` (multi-file migration) or perform a manual
single-PR extraction following the migration table.
```

### Stage 4 — Effectiveness log

**Pre:** proposal written. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

```bash
CALLSITE_COUNT=$(.venv/bin/python -c "import json,sys; print(len(json.load(open(sys.argv[1]))['callsites']))" "${REPORT_DIR}/profile.json")
FILE_COUNT=$(.venv/bin/python -c "import json,sys; print(len({c['file'] for c in json.load(open(sys.argv[1]))['callsites']}))" "${REPORT_DIR}/profile.json")

python3 scripts/log_effectiveness.py \
  --skill extract-cotton-primitive \
  --scan-id "${TARGET_SLUG}" \
  --target "${TARGET_SLUG}" \
  --findings-total "${CALLSITE_COUNT}" \
  --buckets "{\"file_count\": ${FILE_COUNT}}"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- Target (category + N callsites across K templates).
- Proposed primitive name and prop list.
- Migration scope (callsite count by file, top 3).
- Doctrine compliance result (pass/blocker count).
- Path to `${REPORT_DIR}/proposal.md`.
- Recommended next command:
  - `/refactor-subsystem` for multi-file migration, or
  - manual single-PR extraction (state if ≤6 callsites).

Do NOT start the execution step yourself. The proposal is the handoff
artifact.

## Non-goals

- Executing the extraction (that's `/refactor-subsystem` or manual).
- Detecting duplication (that's `/find-frontend-duplication`).
- JS-only helper consolidation (`escapeHtml`, `siteEndpoint`,
  `csrfFetch`) — those need manual edits in `static/js/site-config-
  core.js`, not cotton primitives.
- Touching any file outside `reports/extract-cotton-primitive/<target-
  slug>/`.
- Adding the lint that guards the new primitive — that's part of the
  execution PR. The proposal *names* the lint to add; it doesn't
  write it.

## When things go sideways

| Symptom | Action |
|---|---|
| Findings file missing (Form A) | Abort; tell user to run `/find-frontend-duplication` |
| Candidate's `category` is `helper-fork` or `csrf-fetch` | Abort; this skill is for cotton primitives — recommend manual JS edits in `static/js/site-config-core.js` |
| `profile.py` finds <3 callsites | Below threshold — proposal recommends `defer_low_callsite_count`. Do NOT propose a primitive. |
| Scout violates `<c-vars>` convention | Re-dispatch once citing `knowledge/cotton-conventions.md` directly |
| Proposed primitive needs >2 named slots with conditional rendering | django-cotton's slot model is uncomfortable here — flag as a doctrine gap, propose `defer_doctrine_gap` |
| Existing primitive covers the case (`primitive_bypass: true`) | Proposal is an *adoption* plan: migration table only, no new primitive. Hand off to `/refactor-subsystem`. |
| Census reports `high_variance: true` (dominant <60%) | The chain has no canonical shape — sweep the strict shape only and grandfather the long tail; flag the tail count in the proposal so the human sees what's deferred. |
| Census shows existing primitive defaults ≠ dominant variant | Proposal's recommendation is `change_primitive_defaults_first`: ship the default change as its own PR, then come back for the migration sweep. |
| Census `sample_only: true` (sample < scan count) | Histogram is a lower-bound estimate; scout should re-grep the chain across `templates/` before committing to dominance and reconciliation calls. |

## Repository layout

```
.claude/skills/extract-cotton-primitive/
├── SKILL.md                              # this file — orchestrator
├── scripts/
│   ├── profile.py                        # Stage 1 (stdlib-only)
│   └── census.py                         # Stage 1.5 (stdlib-only)
├── agents/
│   └── propose.md                        # Stage 2 scout brief
└── knowledge/                            # scout context, never loaded by orchestrator
    ├── cotton-conventions.md
    └── migration-patterns.md
```

The orchestrator (you) **never reads files in `knowledge/`**. Those are
for the scout sub-agent. Keeping them out of your context is the whole
point of this architecture.
