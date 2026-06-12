---
name: unify-shadows
description: Turn a semantic-duplication finding into an implementation-ready proposal. Consumes a confirmed finding from /find-semantic-duplication (shape = keep_separate_document_why | share_utilities | complete_migration | merge_at_workflow) and emits reports/unify-shadows/<finding-id>/proposal.md with the migration plan, caller impact, test matrix, and stop condition. Hands off to /fix-workflow semantic:<id>.
argument-hint: "<semantic:SC-N or explicit target spec>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: explain
best_for: |
  A confirmed semantic-duplication finding from
  /find-semantic-duplication (shape =
  keep_separate_document_why | share_utilities | complete_migration |
  merge_at_workflow). Produces an implementation-ready proposal at
  `reports/unify-shadows/<finding-id>/proposal.md` with migration
  plan, caller impact, test matrix, and stop condition.
not_for: |
  Detection of semantic duplication (use /find-semantic-duplication).
  Lexical near-clones (use /find-duplication then /fix-workflow).
  Refactor execution (use /fix-workflow semantic:<id> after proposal
  approval).
language: python
framework: django
---

# /unify-shadows

You are the **orchestrator** that narrows a semantic-duplication finding into
an actionable proposal. `/find-semantic-duplication` classified the cluster's
**shape** (keep separate / share utilities / complete migration / merge at
workflow) and wrote a capability matrix. Your job is to produce the
implementation spec `/fix-workflow semantic:<id>` will execute.

You do not write production code in this skill — you read the shadows in
full, dispatch a scout per member to profile signature / callers / return
contract / retry-and-resource semantics, and consolidate into a proposal.
The human reviews the proposal before authorizing `/fix-workflow`.

## How success is judged

- `reports/unify-shadows/<finding-id>/proposal.md` exists with every
  shadow member profiled at `profiles/<member-key>.md` — divergences
  in signature, callers, return contract, and retry/resource semantics
  are documented per member, never asserted equivalent without
  evidence.
- The scan's `consolidation_shape` is respected; in-tree "INTENTIONAL
  shadow" comments are cited, not overridden.
- One proposal per finding; the handoff target `/fix-workflow
  semantic:<id>` can execute it. Zero production-code edits here.
Write toward these gates from Stage 0.

## Core beliefs

1. **Shape is load-bearing.** The scan's `consolidation_shape` field decides
   what "done" looks like. Don't propose merging shadows the scan classified
   `keep_separate_document_why` — the team already made that decision and
   documented it in-tree. Known project-specific examples and exceptions
   live in `knowledge/`, not in this skill file.
2. **One proposal per finding.** If you open a second cluster mid-run,
   stop — emit a follow-on finding and let the user invoke the skill
   again.
3. **Respect in-tree comments.** "INTENTIONAL shadow — Do not unify"
   comments are authoritative; the proposal cites them rather than
   overriding.
4. **Scouts read, orchestrator consolidates.** Each shadow gets its own
   scout (`agents/shadow-profiler.md`). The orchestrator merges profiles
   into the proposal.
5. **Share utilities must be deep enough.** A tractable helper should
   hide repeated behavior without forcing a shape collapse. Apply the
   deletion test from `.claude/skills/_common/interface-depth.md` before
   proposing any new shared helper or seam.

## Scope

- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` for Django-touching reads; `python3` for
  `scripts/collect_shadows.py` (stdlib-only).
- **Worktree guard:** `/fix-workflow` will check the worktree before
  editing; this skill is read-only — no guard required here.
- **Project-specific defaults** (known shadow patterns, fix-shape
  mapping): `knowledge/`. Scouts read that file; the
  orchestrator does not.

## Argument parsing

Two forms:

### Form A — Semantic finding ID
Pattern: `semantic:SC-N` or `SC-N`. Resolves against
`reports/semantic-duplication/latest/triage.md`. The skill reads:

- member list (file path, symbol, line, caller count)
- `consolidation_shape`
- `capability_matrices/<id>.md`
- the triage's `notes` block

If the scan file is missing, abort and tell the user to run
`/find-semantic-duplication` first — do NOT fall back to scanning.

### Form B — Explicit target spec
A JSON-ish block the user writes when the scan is stale or the pattern
wasn't surfaced. Required fields:

```json
{
  "id": "adhoc-<short-name>",
  "shape": "share_utilities",
  "members": [
    {"file": "core/services/foo.py", "symbol": "Cls.method", "lineno": 123},
    ...
  ],
  "notes": "Why this cluster matters, link to commit or memory if relevant."
}
```

Present the parsed spec back to the user and wait for approval (same
approval-token contract as `/fix-workflow`: first non-whitespace token
must be `approved`, `approve`, `go`, `lgtm`, `proceed`, `yes`).

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed. **Post:** `${REPORT_DIR}` exists, `latest` symlink.

```bash
FINDING_ID="<sc-N or adhoc-...>"
REPORT_DIR="reports/unify-shadows/${FINDING_ID}"
mkdir -p "${REPORT_DIR}/profiles"
ln -sfn "${FINDING_ID}" reports/unify-shadows/latest
```

`reports/unify-shadows/` uses finding IDs directly (not timestamps) so
successive runs against the same cluster overwrite — the shape is
stable per cluster, and re-runs should converge.

### Stage 1 — Collect targets

**Pre:** argument parsed. **Post:** `${REPORT_DIR}/targets.json` with
one entry per shadow (file, symbol, lineno, caller_count, shape, scan
notes).

For **Form A**:

```bash
python3 .claude/skills/unify-shadows/scripts/collect_shadows.py \
  --triage reports/semantic-duplication/latest/triage.md \
  --finding-id "${FINDING_ID}" \
  --output "${REPORT_DIR}/targets.json"
```

For **Form B**: hand-write the targets.json file from the user's spec.
Validate the same fields the Form A path produces.

### Stage 2 — Profile each shadow (parallel fan-out)

**Pre:** `targets.json`. **Post:**
`${REPORT_DIR}/profiles/<member-key>.md` for every member.

For each target, expand `agents/shadow-profiler.md` (substitute
`{{finding_id}}`, `{{member_key}}`, `{{file_path}}`, `{{symbol}}`,
`{{lineno}}`, `{{shape}}`, `{{project_root}}`, `{{skill_root}}`,
`{{output_path}}`, `{{capability_matrix_path}}`) and dispatch each scout
with `subagent_type=general-purpose`. Send every Agent call in a
**single message** so they run concurrently.

Each profile captures:

- **Signature** — parameters, types, defaults.
- **Return contract** — success shape, failure shape, raises.
- **Callers** — list of `file:symbol` plus "what they expect back".
- **Resource ownership** — does the shadow own its own client / semaphore /
  DB rows, or is it a pure function over inputs?
- **Retry + error policy** — provider rotation, typed exceptions, silent
  catch, etc.
- **Load-bearing divergence** — the one-line reason merging costs more
  than it saves (cites the capability matrix).
- **Tractable share opportunity** — the chunk that COULD be extracted
  without forcing a shape collapse. Cite the exact symbols.

If a scout returns `profile_incomplete`, re-dispatch once. If it fails
twice, proceed with partial profiles and flag the gap in the proposal.

### Stage 3 — Synthesize the proposal

**Pre:** all profiles on disk. **Post:** `${REPORT_DIR}/proposal.md`.

Read every profile plus the capability matrix. Write `proposal.md` with
this structure — see `knowledge/` for the exact
per-shape body templates:

```markdown
# Proposal — {{finding_id}}: {{cluster_title}}

## Shape
{{shape}} — from scan-<timestamp>.

## Summary (≤5 sentences)
What the cluster is, why the shape was chosen, what the proposal does.

## Members
- `path/to/file.py:lineno` — `Cls.method` ({{caller_count}} callers)
- ...

## Load-bearing divergence
One paragraph citing the capability matrix's non-merge-safe axes.

## Proposed action
<shape-specific body — keep_separate_document_why | share_utilities |
complete_migration | merge_at_workflow>

## Caller impact
Table: caller file → what changes, zero if none.

## Test matrix
Baseline + per-subsystem suites from `.claude/skills/_common/skill-conventions.md`.
New test modules required, if any.

## Stop condition
What has to be true before `/fix-workflow semantic:{{finding_id}}` can
commit. A checklist.

## Follow-on findings
Adjacent rot the profiling pass surfaced but this proposal does NOT
address. These are seeds for future `/find-*` runs, not TODOs.

## Authorization
One line: "Human review required before `/fix-workflow semantic:{{finding_id}}`."
```

### Stage 4 — Effectiveness log

**Pre:** proposal written. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

```bash
python3 scripts/log_effectiveness.py \
  --skill unify-shadows \
  --scan-id "${FINDING_ID}" \
  --target "$(python3 -c 'import json,sys; print(",".join(m["file"] for m in json.load(open(sys.argv[1]))["members"]))' "${REPORT_DIR}/targets.json")" \
  --findings-total "$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["members"]))' "${REPORT_DIR}/targets.json")" \
  --buckets "{\"shape\": \"$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["shape"])' "${REPORT_DIR}/targets.json")\"}"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- Finding ID + shape.
- Members (count; one-line list).
- Load-bearing divergence (one sentence).
- Proposed action (one sentence).
- Path to `${REPORT_DIR}/proposal.md`.
- Recommended next command: `/fix-workflow semantic:{{finding_id}}`.

Do NOT start `/fix-workflow` yourself. The proposal is the handoff
artifact; the human authorizes the execution step separately.

## Non-goals

- Executing the refactor (that's `/fix-workflow`).
- Detecting new duplication (that's `/find-semantic-duplication`).
- Overriding `keep_separate_document_why` with a merge proposal when
  the scan classified the cluster that way. The proposal documents the
  separation and may propose a narrow share-utility — it does not
  silently re-open the merge debate.
- Touching files outside `reports/unify-shadows/<id>/`.
- Running tests — the proposal lists the matrix; `/fix-workflow` runs it.

## When things go sideways

| Symptom | Action |
|---|---|
| Triage file missing for Form A | Abort; tell user to run `/find-semantic-duplication` |
| `targets.json` lists 0 members | Finding ID wrong — list the IDs present in the triage so user can pick again |
| Scout returns `profile_incomplete` on first try | Re-dispatch once with a stricter "respond only with file-write confirmation" nudge |
| Two scouts produce contradictory caller lists | Both may be right (private method shadowed under same name) — note the conflict in the proposal and move on |
| Capability matrix missing | Proceed without — base the divergence paragraph on the triage's `load_bearing_divergence` field and note the matrix gap |
| Shape is `keep_separate_document_why` but no in-tree comment | The proposal's primary action is "add the documenting comment" plus the optional share-utility; DO NOT invert to a merge |

## Repository layout

```
.claude/skills/unify-shadows/
├── SKILL.md                         # this file — orchestrator
├── scripts/
│   └── collect_shadows.py           # Stage 1 (stdlib-only)
├── agents/
│   └── shadow-profiler.md           # Stage 2 scout brief
└── knowledge/                       # scout context, never loaded by orchestrator
    └── (host-overlay specifics).md
```

The orchestrator (you) **never reads files in `knowledge/`**. Those are
for the scout sub-agents. Keeping them out of your context is the whole
point of this architecture.
