# Stage 5 verification - fix-workflow repair

Date: 2026-06-12
Verifier: Codex lane
Independence note: verified from the declared spec, scout anchors, frame review, implementation notes, current working tree, and the frozen pre-repair copy. I assumed the implementation might be wrong and treated the declared verdict block as the judging contract.

## Overall verdict: PASS (round 2)

Round 1 failed items first:

- Round 1 C2 PARTIAL / C5 PARTIAL: the repair introduced a broken internal shape-count and shape-map cross-reference. `SKILL.md` now has nine Step-1 shape rows, but the procedural-detail text says "seven shapes" and "the eighth", and the repository tree says "7 of the 8 shapes". The `knowledge/fix-shapes.md` map also omits the new `Extract service (layer violation)` shape.

Evidence for the new defect:

```markdown
.claude/skills/fix-workflow/SKILL.md:52-54
- `knowledge/fix-shapes.md` — Step-2 playbooks for the seven shapes
  routed there (the eighth — workflow registry cleanup — uses the
  inline checklist in this file).
```

```markdown
.claude/skills/fix-workflow/SKILL.md:153-161
| **Pure duplication** | 2+ methods, 90%+ identical | `fix-shapes.md` §2a |
| **Three-way+ clone** | 3+ near-identical copies | `fix-shapes.md` §2a |
| **Policy-flag clone** | 2 methods, differ on one branch | `fix-shapes.md` §2a |
| **Template triplication** | same pattern N≥3 with minor vars | `fix-shapes.md` §2a |
| **Shadow helper** | function mirrors canonical | `fix-shapes.md` §2b |
| **Dead code** | zero inbound references | `fix-shapes.md` §2c |
| **Quasi-dead / broken** | silently-broken, no tests | `fix-shapes.md` §2d |
| **Workflow registry cleanup** | workflow step, boot payload, or endpoint knowledge repeated across executable layers | checklist below |
| **Extract service (layer violation)** | entry point owns business logic — from `/find-layer-violation` | `fix-shapes.md` §2a applied at service scope + `_common/interface-depth.md`; if the extraction spans multiple commits/files, hand off to `/refactor-subsystem` |
```

```markdown
.claude/skills/fix-workflow/SKILL.md:423-426
└── knowledge/                  # loaded on demand, not front-to-back
    ├── fix-shapes.md           # Step-2 playbooks (7 of the 8 shapes)
    ├── verification.md         # guard commands, test matrix, commit template, jscpd
    └── learnings.md            # R1–R14 from prior clusters
```

```markdown
.claude/skills/fix-workflow/knowledge/fix-shapes.md:3-14
The orchestrator reads only the section matching the classified
shape. Shapes map to sections:

| Shape                                   | Section         |
|-----------------------------------------|-----------------|
| Pure duplication / three-way clone      | [2a](#2a-extract-helper-shapes) |
| Policy-flag clone                       | [2a](#2a-extract-helper-shapes) |
| Template triplication                   | [2a](#2a-extract-helper-shapes) |
| Shadow helper                           | [2b](#2b-shadow-helper-shapes) |
| Dead code                               | [2c](#2c-dead-code-deletion) |
| Quasi-dead / broken                     | [2d](#2d-quasi-dead--broken-fix) |
| Workflow registry cleanup               | inline checklist in `SKILL.md` Step 2 |
```

## C-item table

| Item | Verdict | Reason |
|---|---|---|
| C1 | RESOLVED | New verification file exists with all four required blocks; all eight bare refs were re-pointed. |
| C2 | PARTIAL | Literal `layer:` route edits are present, but adding the new Step-1 shape introduced the shape-map/count defect above. |
| C3 | RESOLVED | Dead cross-cluster learnings path was removed from this skill; Step 5 now uses the current-run cluster entry. |
| C4 | RESOLVED | All host-bound command sites received absence/substitution fallback language; the declared NO-EDIT was honored. |
| C5 | PARTIAL | The workflow-registry stop condition and requested count edits are present, but the count edits are now false against the nine-row Step-1 table. |
| C6 | RESOLVED | Form B now inlines the investigation questions and removes the phantom `/find-duplication` stage pointer. |
| C7 | RESOLVED | Missing exact ID match now aborts instead of fuzzy-matching. |
| C8 | RESOLVED | Shape-to-bucket mapping is present and covers the Step-1 shapes, including the new layer-violation shape. |
| C9 | RESOLVED | Forms B/C now run Step 1 before approval and avoid a second confirmation after approval. |
| C10 | RESOLVED | The "How success is judged" block is present at the declared insertion point. |
| C11 | RESOLVED | The class-lift gate is inserted; "Next cluster" was renumbered; item 1's threshold language was preserved. |

## C-item evidence quotes

### C1 - RESOLVED

New file and four required blocks:

```markdown
.claude/skills/fix-workflow/knowledge/verification.md:1-6
# Verification & commit reference

Verification machinery `SKILL.md` delegates here: worktree +
cleanliness guard commands, the test matrix, commit verbs + message
template, and the jscpd re-scan command. Host-specific content is
marked with a host-adapter slot, never guessed.
```

````markdown
.claude/skills/fix-workflow/knowledge/verification.md:8-28
## Worktree & cleanliness guard

Run wherever invoked; confirm the root first:

```bash
git rev-parse --show-toplevel
```

Target files must not carry unrelated uncommitted edits:

```bash
git status --porcelain -- <target files>
```

Abort conditions:

- Any target file shows edits you did not make → abort and report
  the dirty files. Do not stash, discard, or commit around them.
- `git status` shows conflicting edits to the same files from
  another worktree (concurrency collision) → abort. Do not rebase
  or merge.
````

```markdown
.claude/skills/fix-workflow/knowledge/verification.md:30-50
## Verification test matrix

Baseline + per-subsystem rows. The matrix is host-specific.

<!-- host-adapter: fill this table for the host project — one
baseline row (fast cross-cutting suite) plus one row per subsystem
mapping source paths to test modules, including any test-settings
flag. Birth-host example: baseline = tests.test_site_capabilities +
tests.test_hydration_detector under --settings=app.settings_test_sqlite. -->

| Subsystem / path | Test modules | Notes |
|---|---|---|
| _(unfilled — apply the absence fallback below)_ | | |

**Absence fallback (mandatory when the table is unfilled):** the
matrix does not exist on this host yet. Do NOT invent rows or report
"the matrix says". Run the narrowest meaningful suite for the
touched files (the host's `docs/testing.md` or project adapter names
it), and state in the execution plan that the matrix was absent and
which suite you chose. If unsure, run the superset for the file's
subsystem.
```

````markdown
.claude/skills/fix-workflow/knowledge/verification.md:52-65
## Commit verbs & message template

Verbs: `Dedup` / `Delete` / `Fix` / `Promote` / `Migrate`. The
commit title starts with the verb (the §2c and §2d stop conditions
check this).

```
<Verb> <what>: <cluster name or target>

- Behavior preserved (R1); a latent bug left in place is named:
  "Behavior preserved, including <bug>".
- Reordered side effects name the new order and the crash
  implication (R8).
```
````

````markdown
.claude/skills/fix-workflow/knowledge/verification.md:67-77
## Post-cluster jscpd re-scan (dedup shapes — R14)

```bash
.venv/bin/python scripts/lint/run_jscpd.py <touched-subdir> \
  --output reports/duplication/rescan --offline-ok
```

Diff the clone count against `reports/duplication/latest/jscpd/`.
Fewer clones = the refactor landed. Same-or-more = it didn't;
investigate before closing. Record the before/after counts in the
cluster entry's Tests section so a skipped re-scan is visible.
````

All eight re-pointed references:

```markdown
.claude/skills/fix-workflow/SKILL.md:56-58
- `knowledge/verification.md` — worktree + cleanliness guard
  commands, test matrix (host-adapter), commit verbs + message
  template, jscpd re-scan command.
```

```markdown
.claude/skills/fix-workflow/SKILL.md:136-138
- **Cleanliness guard:** target files must not carry unrelated
  uncommitted edits before starting. `knowledge/verification.md`
  has the exact commands and abort conditions.
```

```markdown
.claude/skills/fix-workflow/SKILL.md:237-241
The matrix lives in `knowledge/verification.md` (baseline +
per-subsystem rows). If the host table is unfilled, follow its
absence fallback — run the narrowest meaningful suite for the
touched subsystem and name the choice in your plan. If unsure, run
the superset for the file's subsystem.
```

```markdown
.claude/skills/fix-workflow/SKILL.md:245-248
After the refactor lands, re-run jscpd on the touched subdir and
diff the clone count against `reports/duplication/latest/jscpd/`.
Command + rationale in `knowledge/verification.md`. Fewer clones
= the refactor landed (R14).
```

```markdown
.claude/skills/fix-workflow/SKILL.md:260-262
Verb conventions (`Dedup` / `Delete` / `Fix` / `Promote` /
`Migrate`) and the commit-message template live in
`knowledge/verification.md`.
```

```markdown
.claude/skills/fix-workflow/SKILL.md:390-393
- Starting the next cluster automatically.
- Refactoring code adjacent to the cluster target.
- Running the full repo test suite (use `knowledge/verification.md`
  subsystem mapping).
```

```markdown
.claude/skills/fix-workflow/knowledge/fix-shapes.md:67-70
5. **Run the targeted test suite** (see `knowledge/verification.md`
   test matrix) before committing. If any test fails, **do not commit** —
   fix the issue first. If you can't figure out the fix, abort and
   report the exact test+assertion to the user.
```

```markdown
.claude/skills/fix-workflow/knowledge/learnings.md:111-113
Don't run the full repo test suite for a single-file refactor. Use
the test matrix in `knowledge/verification.md` — it maps cluster subsystems
to test modules and is fast under the SQLite test settings.
```

Repository layout includes the new file:

```markdown
.claude/skills/fix-workflow/SKILL.md:423-426
└── knowledge/                  # loaded on demand, not front-to-back
    ├── fix-shapes.md           # Step-2 playbooks (7 of the 8 shapes)
    ├── verification.md         # guard commands, test matrix, commit template, jscpd
    └── learnings.md            # R1–R14 from prior clusters
```

### C2 - PARTIAL

Literal route edits are present:

```markdown
.claude/skills/fix-workflow/SKILL.md:70-77
Pattern: `cluster:<name>`, `delete:<name>`, `fix:<name>`,
`semantic:<name>`, `layer:<name>`, or a short id like `P0-1`,
`P1-agent-extract`.

- `delete:<name>` / `fix:<name>` → load `reports/dormant/latest/report.md`
- `layer:<name>` → load `reports/layer-violation/latest/report.md`
  (emitted by `/find-layer-violation`; per-candidate evidence at
  `scout/<candidate_id>.json`, machine view in `findings.json`).
```

```markdown
.claude/skills/fix-workflow/SKILL.md:89-92
If the referenced report file does not exist, abort and tell the user
which detection skill to run first (`/find-dormant`,
`/find-duplication`, `/find-semantic-duplication`, or
`/find-layer-violation`) — do NOT fall back to scanning the codebase.
```

```markdown
.claude/skills/fix-workflow/SKILL.md:160-161
| **Workflow registry cleanup** | workflow step, boot payload, or endpoint knowledge repeated across executable layers | checklist below |
| **Extract service (layer violation)** | entry point owns business logic — from `/find-layer-violation` | `fix-shapes.md` §2a applied at service scope + `_common/interface-depth.md`; if the extraction spans multiple commits/files, hand off to `/refactor-subsystem` |
```

Partial reason: the new shape row is not reflected in the count/map quotes listed under the overall FAIL section.

### C3 - RESOLVED

```markdown
.claude/skills/fix-workflow/SKILL.md:3
description: Execute a cleanup surfaced by /find-duplication, /find-dormant, or /find-semantic-duplication. Accepts a cluster ID from a triage report (e.g. `cluster:P0-1`, `delete:foo`, `semantic:SC-1`), a file path, or a raw natural-language description. Loads context, writes a regression test first, refactors in a behavior-preserving commit, adds a separate bug-fix commit if latent bugs surface, runs the verification test matrix, writes a cluster learnings entry, and recommends the next cluster. Runs in the current worktree with full commit discipline.
```

```markdown
.claude/skills/fix-workflow/SKILL.md:274-279
## Step 5 — Write the cluster learnings entry

Write a cluster entry and present it in your closing reply — it is
the run's record: Step 6 adds follow-on findings to it, and Step 7's
recommendation and the user's next-cluster choice consume it.
Entry format:
```

```markdown
.claude/skills/fix-workflow/SKILL.md:306-308
If the cluster taught something not already in the skill's
`knowledge/learnings.md` R1–R14, call it out in the entry — the
user decides whether to update the skill.
```

The implementation note's added `Entry format:` label is cosmetic: it introduces the unchanged template block and adds no new obligation.

### C4 - RESOLVED

```markdown
.claude/skills/fix-workflow/knowledge/fix-shapes.md:140-146
1. **Re-verify freshness AND dispatch-registry references.** The
   dormant report is a snapshot — new callers may have landed since
   it was written, and some dispatch paths use string literals that
   `git grep -w` alone can miss. Run BOTH checks. The roots below
   are the birth host's (Django) — if the host lacks them,
   substitute the host's source/template/static roots and name the
   substitution in your execution plan:
```

```markdown
.claude/skills/fix-workflow/knowledge/fix-shapes.md:170-176
3. **Prune alongside:**
   - `__all__` entries in the module
   - Import sites that pull the now-dead name
   - URL patterns in the host's URL modules (birth host:
     `core/urls.py`) if it was a view
   - Admin registrations (birth host: `core/admin.py`) if it was a
     model admin
```

```markdown
.claude/skills/fix-workflow/knowledge/fix-shapes.md:186-190
5. **Run the full baseline test matrix** — dead code deletion is
   high blast radius. The command below is the birth host's; no
   `manage.py` on the host → run the host's baseline equivalent per
   the `knowledge/verification.md` absence fallback and name the
   substitution:
```

````markdown
.claude/skills/fix-workflow/knowledge/fix-shapes.md:198-204
6. **Run the framework's dangling-reference check** (birth host:
   `django-admin check`) to catch dangling URL patterns:
   ```bash
   .venv/bin/python manage.py check
   ```
   No host equivalent → state that explicitly in the stop-condition
   check; do not claim the check passed.
````

```markdown
.claude/skills/fix-workflow/knowledge/fix-shapes.md:208-213
- Fresh re-grep returned zero new inbound references.
- The framework's dangling-reference check passes (birth host:
  `manage.py check`) — or the named host substitute, or its absence
  is stated.
- Baseline + subsystem tests pass (substitutions named).
- Commit title starts with `Delete`.
```

```markdown
.claude/skills/fix-workflow/SKILL.md:99-101
### Form B — File path
Pattern: matches an existing path in the repo (birth-host example:
`core/services/parse_json_body_helper.py`).
```

```markdown
.claude/skills/fix-workflow/SKILL.md:212-217
- Verification must include the host's site-workflow tests (birth
  host: the site workflow Django tests and, when a dev server is
  running, `testing/test_site_pages.py`).
- Do not touch the host's AI-sidecar surface (birth host:
  `core/services/ai_sidecar/`) or unified AI workflow behavior
  unless the user explicitly scopes that work in.
```

NO-EDIT honored:

```markdown
.claude/skills/fix-workflow/knowledge/learnings.md:142-151
## R13 — Trust the existing test suite for well-covered areas

If `tests_custom_site` has 32 tests and your refactor passes all of
them, you don't need to add tests for the refactor itself — they'd
be redundant. Add tests only where coverage is missing (typically
the Cluster 1b / sub-agent-discovered-bug scenario).

**How to apply:** Check the test module's assert count. If it's
>=10 and all pass, skip adding refactor-proof tests. If it's <5, add
a fixture-level test that exercises the helper's main path.
```

Implementation notes recorded the NO-EDIT:

```markdown
.claude/tasks/skill-repairs/fix-workflow/implementation.md:28-31
4. **C4 NO-EDIT honored:** learnings.md R13 `tests_custom_site` and
   cluster provenance examples untouched — illustrative provenance
   (learnings.md:8), not commands.
```

### C5 - PARTIAL

The requested edits are present:

```markdown
.claude/skills/fix-workflow/SKILL.md:185-189
Read the matching section of `knowledge/fix-shapes.md` (2a / 2b /
2c / 2d) and follow it end to end. Each playbook has an explicit
**stop condition** — do not commit unless you can check every box.
(The workflow-registry shape uses the checklist below instead; its
stop condition follows the checklist.)
```

```markdown
.claude/skills/fix-workflow/SKILL.md:219-229
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
```

```markdown
.claude/skills/fix-workflow/knowledge/fix-shapes.md:13-14
| Quasi-dead / broken                     | [2d](#2d-quasi-dead--broken-fix) |
| Workflow registry cleanup               | inline checklist in `SKILL.md` Step 2 |
```

Partial reason: the requested count reconciliation is internally false after C2, as shown in the overall FAIL section.

### C6 - RESOLVED

```markdown
.claude/skills/fix-workflow/SKILL.md:103-109
Treat the file as the scope. No triage context — investigate from
scratch, answering at minimum: who calls each suspect symbol (grep
all call sites); where the duplicate or suspect bodies actually
diverge; whether a canonical equivalent already exists; and what
tests cover the area. **Before any edits**, run Step 1 on that scope
and present its execution plan (file list, fix shape, helper name)
to the user; wait for confirmation.
```

### C7 - RESOLVED

```markdown
.claude/skills/fix-workflow/SKILL.md:94-97
Find the matching cluster, extract file list + fix shape + helper
name. Proceed to Step 1. If no exact ID match exists in the loaded
report, list the available IDs and abort — do not fuzzy-match to the
closest-looking entry.
```

### C8 - RESOLVED

```markdown
.claude/skills/fix-workflow/SKILL.md:326-336
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
```

### C9 - RESOLVED

```markdown
.claude/skills/fix-workflow/SKILL.md:114-118
The description is your brief. Run Step 1 on it — the execution
plan it produces (file list, fix shape, expected changes per file)
is what you present. **Present this plan and wait for explicit
user confirmation before making any edits.** Ask for clarification
if target file(s) or fix shape can't be inferred.
```

```markdown
.claude/skills/fix-workflow/SKILL.md:175-178
**Form A** → plan is a self-check; proceed after writing it.
**Forms B/C** → the plan was already produced and approved during
argument parsing (Step 1 ran early); don't re-present it or wait
for a second confirmation.
```

Form B's Step-1-before-approval quote is included under C6.

### C10 - RESOLVED

```markdown
.claude/skills/fix-workflow/SKILL.md:38-48
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
```

### C11 - RESOLVED

```markdown
.claude/skills/fix-workflow/SKILL.md:360-366
1. **Prevent recurrence.** If the fix shape generalizes (silent-catch,
   bare-int-on-request, shadow helper, etc.), suggest:
   `/prevent-regression cluster:<id>` — it produces a proposal for a
   diff-scoped lint rule + fixture + CLAUDE.md Canonical Patterns
   entry, bundled into one commit. Skip this recommendation when the
   fix was obviously one-off (a single-site data bug, a typo) — two
   clusters justify one rule, not a family.
```

```markdown
.claude/skills/fix-workflow/SKILL.md:367-375
2. **Class lift.** Name the fixed defect's class in one sentence,
   define the cheapest detector for it (usually a grep), and RUN the
   detector across the codebase before closing. Paste the hit count
   in the recommendation. Siblings found → name them as one batch
   sweep candidate, not N future clusters; class mechanizable → that
   is the `/prevent-regression` candidate from item 1 (the
   two-clusters-justify-one-rule threshold gates the lint, not the
   detector run — running the detector is free).
3. **Next cluster.** Then pick one of:
```

## No-invention diff audit

Result: PASS. I found no added sentence in the skill diff or new `knowledge/verification.md` that lacks a source in the change spec, a scout-quoted fragment, or pre-existing skill text.

Trace summary:

- New `knowledge/verification.md`: matches C1 content block; its guard commands trace to the pre-repair Scope and Failure modes; matrix language traces to C1/R10/fix-shapes baseline-test context; commit verbs/template trace to pre-existing Step 4, R1, R8, and C1; jscpd command traces to C1 and the real wrapper named in scout.
- C2/C7 route and abort additions: trace to C2 and C7.
- C3 Step 5 rewrite: traces to C3 and pre-existing Step 5 template. The added `Entry format:` fragment is connective tissue only, not a new sentence or obligation.
- C4 host fallback edits: trace to C4 and scout's host-bound-command findings.
- C5 stop-condition edits: trace to C5 and the pre-existing registry checklist. The count text traces to C5 but is defective after the C2 shape addition; this is a new-defect finding, not an invention finding.
- C6/C9 approval-order edits: trace to C6 and C9.
- C8 bucket table: traces to C8.
- C10 success block: traces to C10 and D2 comparator.
- C11 class-lift block: traces to C11 and D3.

## New-defect sweep

Result: FAIL.

Findings:

- Broken internal shape count: `SKILL.md` has nine Step-1 shape rows, but says "seven shapes", "the eighth", and "7 of the 8 shapes". Evidence is in the overall FAIL section.
- Broken shape map: `knowledge/fix-shapes.md` says "Shapes map to sections:" but does not include `Extract service (layer violation)`, even though the current Step-1 table added that shape. Evidence is in the overall FAIL section.

Clean checks in the requested same-class sweep:

- Bare directory references: no exact `` `knowledge/` `` hits remain. The only remaining `knowledge/` without a filename is the repository-layout directory entry, which is structural.
- Dead artifact mandate: no `reports/duplication/learnings` reference remains under `.claude/skills/fix-workflow/`.
- Host-bound commands: the `core/`, `templates/`, `static/`, `frontend/`, and `manage.py` command blocks now have explicit substitution or absence fallback text.
- Stop-condition-less shapes: workflow registry cleanup now has a stop condition; extract service routes to §2a, which has a stop condition.
- Matrix references: current references point to `knowledge/verification.md` or to the absence fallback in that file.

## Live re-run outputs

Command:

```bash
.venv/bin/python scripts/skill_meta.py lint
```

Output:

```text
OK — 74 skills, 74 declaring new contract
```

Exit: 0

Command:

```bash
grep -rn '`knowledge/`' .claude/skills/fix-workflow/
```

Output:

```text
```

Exit: 1 (grep found 0 hits)

Command:

```bash
grep -rn 'reports/duplication/learnings' .claude/skills/fix-workflow/
```

Output:

```text
```

Exit: 1 (grep found 0 hits)

## Re-verification (round 2)

Date: 2026-06-12
Verifier: Codex lane
Scope: re-verified only `.claude/skills/fix-workflow/SKILL.md`,
`.claude/skills/fix-workflow/knowledge/fix-shapes.md`, and this
verification log.

### Edited-passage evidence

Knowledge-file routing is now count-free:

```markdown
.claude/skills/fix-workflow/SKILL.md:52-55
- `knowledge/fix-shapes.md` — Step-2 playbooks. Every shape routes
  there except workflow registry cleanup, which uses the inline
  checklist in this file. Read only the section matching the
  classified cluster.
```

Repository layout comment is now count-free:

```markdown
.claude/skills/fix-workflow/SKILL.md:420-426
.claude/skills/fix-workflow/
├── SKILL.md                    # this file — orchestrator
└── knowledge/                  # loaded on demand, not front-to-back
    ├── fix-shapes.md           # Step-2 playbooks (registry checklist lives above)
    ├── verification.md         # guard commands, test matrix, commit template, jscpd
    └── learnings.md            # R1–R14 from prior clusters
```

The Step-1 classification table still has nine rows:

```markdown
.claude/skills/fix-workflow/SKILL.md:151-161
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
```

The shape map now includes both previously relevant rows:

```markdown
.claude/skills/fix-workflow/knowledge/fix-shapes.md:6-15
| Shape                                   | Section         |
|-----------------------------------------|-----------------|
| Pure duplication / three-way clone      | [2a](#2a-extract-helper-shapes) |
| Policy-flag clone                       | [2a](#2a-extract-helper-shapes) |
| Template triplication                   | [2a](#2a-extract-helper-shapes) |
| Shadow helper                           | [2b](#2b-shadow-helper-shapes) |
| Dead code                               | [2c](#2c-dead-code-deletion) |
| Quasi-dead / broken                     | [2d](#2d-quasi-dead--broken-fix) |
| Workflow registry cleanup               | inline checklist in `SKILL.md` Step 2 |
| Extract service (layer violation)       | [2a](#2a-extract-helper-shapes) applied at service scope |
```

Cross-check: `Workflow registry cleanup` maps to the inline checklist
in both files. `Extract service (layer violation)` maps to
`fix-shapes.md` §2a applied at service scope in both files; SKILL.md
also correctly keeps the extra `_common/interface-depth.md` instruction
and `/refactor-subsystem` handoff condition. No new inconsistency was
introduced by the three edits under review.

### Command outputs

Command:

```bash
grep -rn -E 'seven shapes|eighth|7 of the 8|7 shapes' .claude/skills/fix-workflow/
```

Output:

```text
```

Exit: 1 (grep no-match; 0 hits)

Command:

```bash
.venv/bin/python scripts/skill_meta.py lint
```

Output:

```text
OK — 74 skills, 74 declaring new contract
```

Exit: 0

### Round-2 verdicts

| Item | Verdict | Reason |
|---|---|---|
| C2 | RESOLVED | The layer-violation shape remains in the nine-row Step-1 table, and the shape map now includes `Extract service (layer violation)` pointing to 2a applied at service scope. |
| C5 | RESOLVED | The stale count language is gone from the two edited SKILL.md passages, and the required grep returned 0 hits under `.claude/skills/fix-workflow/`. |

Overall: PASS
