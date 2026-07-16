---
name: fix-workflow
description: Execute a cleanup surfaced by /find-duplication, /find-dormant, or /find-semantic-duplication. Accepts a cluster ID from a triage report (e.g. `cluster:P0-1`, `delete:foo`, `semantic:SC-1`), a file path, or a raw natural-language description. Loads context, writes a regression test first, refactors in a behavior-preserving commit, adds a separate bug-fix commit if latent bugs surface, runs the verification test matrix, writes a cluster learnings entry, and recommends the next cluster. Runs in the current worktree with full commit discipline.
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
framework: any
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

## How success is judged

- A regression/characterization test exists **before** the fix and
  is green at commit time (R2; §2d writes the failing test first).
- The behavior-preserving refactor commit is separate from any
  bug-fix commit (R1).
- The verification matrix ran green for the touched subsystem
  (Step 3) — plus the jscpd re-scan for dedup shapes (R14).
- The playbook's stop condition has every box checked; no commit
  otherwise.
Work toward these gates from Step 1.

Procedural detail lives in three knowledge files:

- `knowledge/fix-shapes.md` — Step-2 playbooks. Every shape routes
  there except workflow registry cleanup, which uses the inline
  checklist in this file. Read only the section matching the
  classified cluster.
- `knowledge/verification.md` — worktree + cleanliness guard
  commands, test matrix (host-adapter), commit verbs + message
  template, jscpd re-scan command.
- `knowledge/learnings.md` — 14 rules from prior clusters (R1–R14).
  Read on ambiguity; don't front-load.
- `.claude/skills/_common/interface-depth.md` — read when the cluster
  extracts a helper/service, promotes a canonical interface, or adds an
  adapter seam.

## Argument parsing

The argument takes three forms. Detect which and route:

### Form A — Cluster ID from a triage report
Pattern: `cluster:<name>`, `delete:<name>`, `fix:<name>`,
`semantic:<name>`, `layer:<name>`, or a short id like `P0-1`,
`P1-agent-extract`.

- `delete:<name>` / `fix:<name>` → load `reports/dormant/latest/report.md`
- `layer:<name>` → load `reports/layer-violation/latest/report.md`
  (emitted by `/find-layer-violation`; per-candidate evidence at
  `scout/<candidate_id>.json`, machine view in `findings.json`).
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
`/find-duplication`, `/find-semantic-duplication`, or
`/find-layer-violation`) — do NOT fall back to scanning the codebase.

Find the matching cluster, extract file list + fix shape + helper
name. Proceed to Step 1. If no exact ID match exists in the loaded
report, list the available IDs and abort — do not fuzzy-match to the
closest-looking entry.

### Form B — File path
Pattern: matches an existing path in the repo (birth-host example:
`core/services/parse_json_body_helper.py`).

Treat the file as the scope. No triage context — investigate from
scratch, answering at minimum: who calls each suspect symbol (grep
all call sites); where the duplicate or suspect bodies actually
diverge; whether a canonical equivalent already exists; and what
tests cover the area. **Before any edits**, run Step 1 on that scope
and present its execution plan (file list, fix shape, helper name)
to the user; wait for confirmation.

### Form C — Free-form description
Anything else — a sentence describing what to clean up.

The description is your brief. Run Step 1 on it — the execution
plan it produces (file list, fix shape, expected changes per file)
is what you present. **Present this plan and wait for explicit
user confirmation before making any edits.** Ask for clarification
if target file(s) or fix shape can't be inferred.

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
  uncommitted edits before starting. `knowledge/verification.md`
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
| **Extract service (layer violation)** | entry point owns business logic — from `/find-layer-violation` | `fix-shapes.md` §2a applied at service scope + `_common/interface-depth.md`; if the extraction spans multiple commits/files, hand off to `/refactor-subsystem` |

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
**Forms B/C** → the plan was already produced and approved during
argument parsing (Step 1 ran early); don't re-present it or wait
for a second confirmation.

## Step 2 — Execute the fix shape

**Pre:** plan written.
**Post:** code edits + test runs complete; no commit yet.

Read the matching section of `knowledge/fix-shapes.md` (2a / 2b /
2c / 2d) and follow it end to end. Each playbook has an explicit
**stop condition** — do not commit unless you can check every box.
(The workflow-registry shape uses the checklist below instead; its
stop condition follows the checklist.)

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
- Verification must include the host's site-workflow tests and, when a
  development server is running, its page-level workflow suite. Use the
  selected framework binding for the concrete runner.
- Do not touch the host's AI-sidecar surface (birth host:
  `core/services/ai_sidecar/`) or unified AI workflow behavior
  unless the user explicitly scopes that work in.

### Stop condition (workflow registry cleanup)

- Boot-payload characterization tests written before production
  edits, and green.
- Every endpoint-registry key asserted equal to its `reverse(...)`
  (or the host router's equivalent).
- Cache-busting bumped on every touched JS include.
- Diff-scoped guard added, or deferred with a named reason in the
  cluster entry.
- URL routes and view names unchanged, or the user explicitly
  authorized route migration.

## Step 3 — Verification test matrix

**Pre:** edits complete, playbook's stop condition satisfied.
**Post:** targeted test suites green.

Run the **right** tests for the cluster, not every test in the repo.
The matrix lives in `knowledge/verification.md` (baseline +
per-subsystem rows). If the host table is unfilled, follow its
absence fallback — run the narrowest meaningful suite for the
touched subsystem and name the choice in your plan. If unsure, run
the superset for the file's subsystem.

### Post-cluster jscpd re-scan (dedup-shape clusters only)

After the refactor lands, re-run jscpd on the touched subdir and
diff the clone count against `reports/duplication/latest/jscpd/`.
Command + rationale in `knowledge/verification.md`. Fewer clones
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
`knowledge/verification.md`.

**Git safety:**
- Never `--amend` a previous commit unless the user asked. New
  commit instead.
- Never `--no-verify`. Fix the hook failure.
- Never `reset --hard` or `checkout --`. Stage/commit only the files
  you intended to touch.
- Never push to remote.
- Run `git status` + `git diff --stat` before committing to confirm
  the file list matches your plan.

## Step 5 — Write the cluster learnings entry

Write a cluster entry and present it in your closing reply — it is
the run's record: Step 6 adds follow-on findings to it, and Step 7's
recommendation and the user's next-cluster choice consume it.
Entry format:

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

If the cluster taught something not already in the skill's
`knowledge/learnings.md` R1–R14, call it out in the entry — the
user decides whether to update the skill.

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
`migrate`, `shadow`, mapped from the Step-1 shape:

| Step-1 shape | bucket |
|---|---|
| Pure duplication / Three-way+ clone / Policy-flag clone / Template triplication | `dedup` |
| Shadow helper | `shadow` |
| Dead code | `delete` |
| Quasi-dead / broken | `fix` |
| Workflow registry cleanup | `migrate` |
| Extract service (layer violation) | `promote` |

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
2. **Class lift.** Name the fixed defect's class in one sentence,
   define the cheapest detector for it (usually a grep), and RUN the
   detector across the codebase before closing. Paste the hit count
   in the recommendation. Siblings found → name them as one batch
   sweep candidate, not N future clusters; class mechanizable → that
   is the `/prevent-regression` candidate from item 1 (the
   two-clusters-justify-one-rule threshold gates the lint, not the
   detector run — running the detector is free).
3. **Next cluster.** Then pick one of:
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
- Running the full repo test suite (use `knowledge/verification.md`
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
    ├── fix-shapes.md           # Step-2 playbooks (registry checklist lives above)
    ├── verification.md         # guard commands, test matrix, commit template, jscpd
    └── learnings.md            # R1–R14 from prior clusters
```
