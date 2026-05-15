---
name: fix-workflow
description: Execute a cleanup surfaced by /find-duplication, /find-dormant, or /find-semantic-duplication. Accepts a cluster ID from a triage report (e.g. `cluster:P0-1`, `delete:foo`, `semantic:SC-1`), a file path, or a raw natural-language description. Loads context, writes a regression test first, refactors in a behavior-preserving commit, adds a separate bug-fix commit if latent bugs surface, runs the verification test matrix, updates `reports/duplication/learnings.md`, and recommends the next cluster. Runs in the current worktree with full commit discipline.
argument-hint: "<cluster-id> | semantic:<id> | delete:<id> | <file-path> | <free-form description>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: refactor
best_for: |
  Executing a cleanup cluster surfaced by a SUSPECT skill — accepts
  cluster IDs (`cluster:P0-1`, `delete:foo`, `semantic:SC-1`,
  `layer:LV-2`), file paths, or free-form descriptions. Writes
  regression test first, refactors behavior-preservingly, then
  separately commits any latent bug fixes.
not_for: |
  Detection (use /find-duplication / /find-dormant /
  /find-semantic-duplication / /find-layer-violation / etc.).
  Multi-file subsystem refactors with multiple commits (use
  /refactor-subsystem). Authoring decisions (use /decide).
language: python
framework: django
---

# /fix-workflow

You are the **orchestrator** for a cleanup cluster. Unlike
`/find-duplication`, `/find-dormant`, and `/find-semantic-duplication`
— which are detection pipelines — this is the execution skill. It
writes code, runs tests, and produces commits.

**Invocation is not blanket authorization.** For Form A (cluster ID
from a triage report), the user has authorized the specific cluster
by referencing it. For Forms B and C, you must present an explicit
plan and wait for user confirmation before any edits — see
Argument Parsing below. Authorization for one cluster is never
authorization for follow-on clusters or adjacent fixes.

Procedural detail lives in three knowledge files:

- `knowledge/fix-shapes.md` — Step-2 playbooks for the seven shapes.
  Read only the section matching the classified cluster.
- `knowledge/` — worktree paths, test matrix,
  commit verb conventions, concurrency guard commands.
- `knowledge/learnings.md` — 14 rules from prior clusters (R1–R14).
  Read on ambiguity; don't front-load.
- `.claude/skills/_common/interface-depth.md` — read when the cluster
  extracts a helper/service, promotes a canonical interface, or adds an
  adapter seam.

## Argument parsing

The argument takes three forms. Detect which and route:

### Form A — Cluster ID from a triage report
Pattern: `cluster:<name>`, `delete:<name>`, `fix:<name>`,
`semantic:<name>`, or a short id like `P0-1`, `P1-agent-extract`.

- `delete:<name>` / `fix:<name>` → load `reports/dormant/latest/report.md`
- `semantic:<name>` → load `reports/semantic-duplication/latest/triage.md`
  (emitted by `/find-semantic-duplication`; finding IDs look like
  `semantic:SC-1`, `semantic:SC-2` — the prefix is `SC-` because
  the collapse stage in that skill re-numbers globally, see
  `.claude/skills/find-semantic-duplication/scripts/collapse_candidates.py`).
  The shape is always semantic-duplication — route to
  `fix-shapes.md §2a` (pure / three-way clone) or §2b (shadow
  helper), using the triage's `capability_matrix` + `confirm`
  notes to decide which canonical survives and which are shadows.
- `cluster:<name>` or P0/P1/P2 ID → load `reports/duplication/latest/triage.md`

If the referenced report file does not exist, abort and tell the user
which detection skill to run first (`/find-dormant`,
`/find-duplication`, or `/find-semantic-duplication`) — do NOT fall
back to scanning the codebase.

Find the matching cluster, extract file list + fix shape + helper
name. Proceed to Step 1.

### Form B — File path
Pattern: starts with `core/` or matches an existing path. Example:
`core/services/parse_json_body_helper.py`.

Treat the file as the scope. No triage context — investigate from
scratch. Run the Investigation sub-steps of `/find-duplication` on
just that file. **Before any edits**, present the plan (file list,
fix shape, helper name) to the user and wait for confirmation.

### Form C — Free-form description
Anything else — a sentence describing what to clean up.

The description is your brief. Produce an execution plan with:
- Explicit list of files that will be modified
- Fix shape (from the table in Step 1)
- Expected changes per file

**Present this plan and wait for explicit user confirmation before
making any edits.** Ask for clarification if target file(s) or fix
shape can't be inferred.

### Approval-token contract (Forms B & C)

When waiting for user confirmation, accept the reply as approval only
if the **first non-whitespace token** is one of: `approved`,
`approve`, `go`, `ship it`, `lgtm`, `proceed`, `yes`. Substring
matches on the approval word elsewhere in the sentence do NOT count
("looks ok but defer the helper rename" is a change request, not
approval). Any conjunction on the same turn (`but`, `except`,
`however`, `only if`, `defer`) flips the reply to a change request.
When in doubt, ask for a clean approval token — do not guess intent.

## Scope

- **Worktree:** run wherever invoked. Confirm with `git rev-parse
  --show-toplevel` before starting.
- **Python:** `.venv/bin/python`. Never bare `python`.
- **Cleanliness guard:** target files must not carry unrelated
  uncommitted edits before starting. `knowledge/`
  has the exact commands and abort conditions.

## Step 1 — Load context and classify the cluster

**Pre:** a cluster reference (Form A/B/C resolved).
**Post:** a written plan with target files, shape, helper name,
test modules.

Read the target files in full (not just the triage line ranges).
Don't trust triage as exhaustive.

Classify into one of these shapes:

| Shape | Detection | Playbook |
|---|---|---|
| **Pure duplication** | 2+ methods, 90%+ identical | `fix-shapes.md` §2a |
| **Three-way+ clone** | 3+ near-identical copies | `fix-shapes.md` §2a |
| **Policy-flag clone** | 2 methods, differ on one branch | `fix-shapes.md` §2a |
| **Template triplication** | same pattern N≥3 with minor vars | `fix-shapes.md` §2a |
| **Shadow helper** | function mirrors canonical | `fix-shapes.md` §2b |
| **Dead code** | zero inbound references | `fix-shapes.md` §2c |
| **Quasi-dead / broken** | silently-broken, no tests | `fix-shapes.md` §2d |
| **Workflow registry cleanup** | workflow step, boot payload, or endpoint knowledge repeated across executable layers | checklist below |

Write a one-paragraph **execution plan** to stdout:

- Target file(s) and line ranges
- Fix shape (from table)
- Helper name (if any) + where it lives (module vs class)
- Interface-depth note for any new helper/service/adapter: deletion
  test, caller knowledge removed, intended test surface, adapter count
- Test file(s) covering the area, new tests to add
- Expected LOC delta
- Adjacent dead code spotted while reading — do NOT fold in; emit
  as a follow-on finding

**Form A** → plan is a self-check; proceed after writing it.
**Forms B/C** → plan is an internal record; the user already
approved scope during argument parsing. Don't wait for a second
confirmation.

## Step 2 — Execute the fix shape

**Pre:** plan written.
**Post:** code edits + test runs complete; no commit yet.

Read the matching section of `knowledge/fix-shapes.md` (2a / 2b /
2c / 2d) and follow it end to end. Each playbook has an explicit
**stop condition** — do not commit unless you can check every box.

### Workflow registry cleanup checklist

Use this checklist when the cleanup centralizes product workflow
authority rather than local code clones:

- Write boot-payload characterization tests before production edits.
  For endpoint registries, assert every key equals `reverse(...)`.
- Keep URL route definitions and view names unchanged unless the user
  explicitly authorized route migration.
- Migrate only active consumers loaded by current templates; name any
  deferred dynamic, field-specific, or ai-sidecar endpoints as
  follow-up scope rather than pulling them in.
- For site-scoped API consumers, add registry-owned static endpoints
  and, when needed, template endpoints with explicit placeholder names.
  Frontend JS should call boot helpers instead of string-building
  `/api/sites/<site_id>/...`.
- Preserve responsive desktop/mobile behavior and existing template
  ownership. Bump cache-busting query strings for every touched JS
  include.
- Add or update a diff-scoped guard when the migrated pattern can
  recur, e.g. JS endpoint-sprawl lint with good/bad fixtures.
- Verification must include the site workflow Django tests and, when a
  dev server is running, `testing/test_site_pages.py`.
- Do not touch `core/services/ai_sidecar/` or unified AI
  workflow behavior unless the user explicitly scopes that work in.

## Step 3 — Verification test matrix

**Pre:** edits complete, playbook's stop condition satisfied.
**Post:** targeted test suites green.

Run the **right** tests for the cluster, not every test in the repo.
The matrix lives in `knowledge/` (baseline + per-
subsystem rows). If unsure, run the superset for the file's subsystem.

### Post-cluster jscpd re-scan (dedup-shape clusters only)

After the refactor lands, re-run jscpd on the touched subdir and
diff the clone count against `reports/duplication/latest/jscpd/`.
Command + rationale in `knowledge/`. Fewer clones
= the refactor landed (R14).

## Step 4 — Commit discipline

**One commit per logical unit.** Two-commit clusters happen when:
- A refactor surfaces a latent bug (refactor commit + separate fix
  commit — R1).
- A canonical gap needs filling (Promote commit + Migrate commit —
  §2b-ii).
- Dead-code deletion reveals a dependent cleanup (Delete commit +
  dependent cleanup commit).

Verb conventions (`Dedup` / `Delete` / `Fix` / `Promote` /
`Migrate`) and the commit-message template live in
`knowledge/`.

**Git safety:**
- Never `--amend` a previous commit unless the user asked. New
  commit instead.
- Never `--no-verify`. Fix the hook failure.
- Never `reset --hard` or `checkout --`. Stage/commit only the files
  you intended to touch.
- Never push to remote.
- Run `git status` + `git diff --stat` before committing to confirm
  the file list matches your plan.

## Step 5 — Update the learnings log

Append a cluster entry to `reports/duplication/learnings.md`:

```markdown
## Cluster N: <name> (P0/P1/P2)

**Date:** <YYYY-MM-DD>
**Commit:** `<sha>` — "<commit message title>"
**Type:** Duplication / Dead code / Quasi-dead / Shadow helper / ...

### What was flagged
<from /find-duplication or /find-dormant — what the detector said>

### What was actually true
<after investigation — did the detector get it right? what did the
detector miss?>

### What changed
<files, LOC delta, helpers added/removed — table if multi-file>

### Tests
<suites run, new tests added, coverage gaps that remain>

### Skill-worthy patterns
<distilled lessons for future audits. Lead with the observation,
then "Why:" and "How to apply:" where relevant.>
```

Also update the **running LOC delta table** at the bottom of
`reports/duplication/learnings.md` (the cross-cluster log — NOT the
skill-internal `knowledge/learnings.md`). If the cluster taught
something not already in the skill's `knowledge/learnings.md`
R1–R14, call it out in the entry — the user decides whether to
update the skill.

Append an effectiveness log entry so
`reports/_meta/dashboard.md` can track which shapes are being
cleaned up over time. `findings_total` is always 1 (one cluster per
run); `buckets` keys on the shape with value 1. See
`.claude/skills/_common/skill-conventions.md` for the schema.

```bash
python3 scripts/log_effectiveness.py \
  --skill fix-workflow \
  --scan-id "cluster-$(git rev-parse --short HEAD)" \
  --target <primary-target-file> \
  --findings-total 1 \
  --buckets '{"<shape>": 1}' \
  --notes "<cluster-name> → <commit-sha>"
```

Where `<shape>` is one of: `dedup`, `delete`, `fix`, `promote`,
`migrate`, `shadow`.

## Step 6 — Surface follow-on findings

While executing, you may have noticed:

- **Adjacent dead code** — emit as a `/find-dormant` candidate.
  Don't delete in this commit.
- **Drift between clone copies** (inconsistent error messages,
  inconsistent log strings) — emit as "drift cleanup candidate".
- **Silent `except Exception` near the target** — emit as "latent
  bug risk".
- **Tests that would have caught an issue but didn't exist** —
  emit as "coverage gap".

Write these to a `## Follow-on findings` section in the learnings
entry. They are **not** TODOs for you — they inform the user's
next cluster choice (R11).

## Step 7 — Recommend next action

End with a short recommendation that covers both **preventing
recurrence** and **what to fix next**:

1. **Prevent recurrence.** If the fix shape generalizes (silent-catch,
   bare-int-on-request, shadow helper, etc.), suggest:
   `/prevent-regression cluster:<id>` — it produces a proposal for a
   diff-scoped lint rule + fixture + CLAUDE.md Canonical Patterns
   entry, bundled into one commit. Skip this recommendation when the
   fix was obviously one-off (a single-site data bug, a typo) — two
   clusters justify one rule, not a family.
2. **Next cluster.** Then pick one of:
   - More clusters in the same triage → point at the next.
   - File is now fully dedup'd → suggest `/find-duplication` on an
     adjacent file or sub-package.
   - Follow-on findings surfaced → suggest `/find-dormant` to validate
     them.
   - Worktree blocking on concurrent edits in main → surface it
     explicitly.

**Do NOT start the next cluster automatically.** Each cluster is a
separate authorization — and `/prevent-regression` is its own
authorization too; it builds a proposal but does not commit.

## Non-goals

- Starting the next cluster automatically.
- Refactoring code adjacent to the cluster target.
- Running the full repo test suite (use `knowledge/`
  subsystem mapping).
- Editing files in the main worktree (concurrency guard).
- Creating documentation unless the user explicitly asks.
- Updating `.claude/skills/*/SKILL.md` as part of a cluster commit
  — skill files evolve on their own cadence.

## Failure modes and recovery

- **Test failure after refactor:** do not commit. Read the test
  output, identify the failing assertion, Read the affected code.
  <5 min fix → fix it. Otherwise abort and report the exact
  test+assertion to the user with the current file state.
- **Behavior change detected post-commit:** create a revert commit,
  not `git reset`. Reverts preserve history and signal intentional
  backout.
- **Concurrency collision with main worktree:** `git status` shows
  conflicting files. Abort. Do not rebase or merge.
- **Helper contract is wrong mid-refactor:** revise the helper. Do
  not add a flag to paper over the mismatch — the right shape may
  be two helpers (R12).
- **Silent bug survived the refactor:** means the refactor was
  behavior-preserving (correct) but the code was broken from Day 1.
  Commit the refactor; file a new cluster for the fix. Don't
  combine.

## Repository layout

```
.claude/skills/fix-workflow/
├── SKILL.md                    # this file — orchestrator
└── knowledge/                  # loaded on demand, not front-to-back
    ├── fix-shapes.md           # Step-2 playbooks for the 7 shapes
    └── learnings.md            # R1–R14 from prior clusters
```
