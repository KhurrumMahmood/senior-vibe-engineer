All evidence gathered. One note on method: the sandboxed `--help` run was blocked by the permission gate twice, so I derived the script contract from the argparse source directly (`scripts/log_effectiveness.py:46-73`), which is strictly more complete than the help text. Here is the review.

---

# Frame review — /fix-workflow

**Date:** 2026-06-12
**Files reviewed:** `.claude/skills/fix-workflow/SKILL.md`, `knowledge/fix-shapes.md`, `knowledge/learnings.md` (complete file list, verified by `ls`). Rubric: `.claude/skills/repair-skill/knowledge/frame-review-rubric.md`, all six lenses plus the two execution-time classes.
**Script contract:** derived from the argparse source at `scripts/log_effectiveness.py:46-73` (the sandboxed `--help` invocation was blocked by the permission gate in this session; the source is the authoritative superset of the help text).

## Findings (severity-ordered)

### F1 — CRITICAL (artifact-reality drift): the load-bearing knowledge file does not exist; eight references point at a bare directory

The skill's verification machinery — test matrix, concurrency-guard commands, commit-verb conventions and commit-message template, and the jscpd re-scan command — is delegated to a knowledge file that is not in the directory. `knowledge/` contains exactly `fix-shapes.md` and `learnings.md` (verified by `ls`), yet eight references point at a bare `knowledge/` with the filename visibly stripped mid-sentence:

- `.claude/skills/fix-workflow/SKILL.md:42-43` — "`knowledge/` — worktree paths, test matrix, commit verb conventions, concurrency guard commands"
- `.claude/skills/fix-workflow/SKILL.md:116-117` — cleanliness guard: "`knowledge/` has the exact commands and abort conditions"
- `.claude/skills/fix-workflow/SKILL.md:199` — "The matrix lives in `knowledge/` (baseline + per-subsystem rows)"
- `.claude/skills/fix-workflow/SKILL.md:206` — jscpd re-scan: "Command + rationale in `knowledge/`"
- `.claude/skills/fix-workflow/SKILL.md:219-221` — "Verb conventions … and the commit-message template live in `knowledge/`"
- `.claude/skills/fix-workflow/SKILL.md:334` — non-goal: "use `knowledge/` subsystem mapping"
- `.claude/skills/fix-workflow/knowledge/learnings.md:112` — R10: "the test matrix in `knowledge/` — it maps cluster subsystems to test modules"
- `.claude/skills/fix-workflow/knowledge/fix-shapes.md:66` — "see `knowledge/` test matrix"

**Execution-time failure:** Step 3 is the skill's only commit gate ("targeted test suites green"). A real executor reaches Step 3, is told the matrix lives in `knowledge/`, opens the directory, finds no matrix — and invents a test selection that it then reports as "the matrix says". The same happens at the cleanliness guard (improvised or skipped, since the "exact commands and abort conditions" don't exist) and at the R14 jscpd re-scan, which `learnings.md:154-157` calls "the only way to confirm the clone actually dropped" but whose command exists nowhere. The skill's strongest property checks all dead-end into hallucination at exactly the moments they are load-bearing.

**Smallest fix:** restore the missing file (e.g. `knowledge/worktree-and-tests.md`) containing the four blocks — cleanliness-guard commands + abort conditions, test matrix, commit template + verbs, jscpd re-scan command — and re-point all eight references at it by full filename. If the content is unrecoverable, inline the four blocks into SKILL.md; a 60-line SKILL.md growth is cheaper than eight hallucination invitations.

### F2 — HIGH (artifact-reality drift): the advertised `layer:` entry point has no route, no report mapping, and no shape

`SKILL.md:13` advertises `layer:LV-2` in `best_for`, and `/find-layer-violation` hands off with exactly that syntax (`.claude/skills/find-layer-violation/SKILL.md:241`, also lines 12, 27, 55), writing its report to `reports/layer-violation/latest/` (`find-layer-violation/SKILL.md:97-99`). But Form A's pattern list (`SKILL.md:54-56`) recognizes only `cluster:`, `delete:`, `fix:`, `semantic:`, and short IDs; the report-loading table (`SKILL.md:58-68`) has no `layer:` row; and the Step-1 shape table (`SKILL.md:128-139`) has no extract-service shape.

**Execution-time failure:** `/fix-workflow layer:LV-2` falls through to Form C (free-form). The executor never loads the layer-violation report the upstream skill prepared, re-derives scope from the bare token "layer:LV-2" (which contains no information), and either stalls asking the user what LV-2 means or guesses at a target. The detection skill's whole evidence package is dropped on the floor at the handoff boundary.

**Smallest fix:** add one Form A bullet — `layer:<id>` → load `reports/layer-violation/latest/` — plus either an extract-service row in the shape table pointing at a playbook, or an explicit rule that `layer:` clusters re-route to `/refactor-subsystem` (and then delete `layer:LV-2` from `best_for`).

### F3 — HIGH (artifact-reality drift): the mandated learnings artifact has no producer and no skeleton

Step 5 (`SKILL.md:235`) mandates appending a cluster entry to `reports/duplication/learnings.md` and (`SKILL.md:262-263`) updating "the running LOC delta table at the bottom" of it. `reports/duplication/` does not exist in this repo, and a grep across all skills and scripts shows no producer: the only files referencing the path are this skill and `/refactor-subsystem`. `/find-duplication` creates `reports/duplication/latest/` scan dirs but never `learnings.md`.

**Execution-time failure:** on a fresh host (or any host where `/fix-workflow` runs before a dedup cluster has ever been closed), the executor must append to a file that doesn't exist and update a "running table at the bottom" whose columns are specified nowhere. It invents a table schema; the next run invents a different one; the "cross-cluster log" the skill distinguishes so carefully from `knowledge/learnings.md` (`SKILL.md:262-267`) never converges to one format. Secondary wrinkle: dormant, semantic, layer, and free-form clusters all write under a path named `duplication/`.

**Smallest fix:** add to Step 5: "if the file does not exist, create it with this skeleton" and include the LOC-delta table header (columns: cluster, date, commit, LOC before/after, delta).

### F4 — HIGH (unexecutable-against-reality): §2c's stop condition is unsatisfiable outside the original host project

The dead-code playbook hardcodes the birth host: the re-grep roots `core/ templates/ static/ urls.py admin.py management/commands/ frontend/` (`knowledge/fix-shapes.md:145-156`), the baseline test command `manage.py test tests.test_site_capabilities tests.test_hydration_detector --settings=app.settings_test_sqlite` (`fix-shapes.md:182-187`), and `manage.py check` (`fix-shapes.md:189-192`). The stop condition itself (`fix-shapes.md:194-199`) requires "`manage.py check` passes" and "Baseline + subsystem tests pass". None of `manage.py`, `core/`, or `testing/` exists in this repo (verified). The same class appears in SKILL.md: Form B's detection pattern "starts with `core/`" (`SKILL.md:80`), and the workflow-registry checklist's `testing/test_site_pages.py` (`SKILL.md:188-189`) and `core/services/ai_sidecar/` (`SKILL.md:190-191`).

**Execution-time failure:** every `delete:` cluster on a non-original host hits a stop condition that literally cannot be checked. The executor either aborts every dead-code deletion (skill is dead weight) or — the worse and likelier outcome — substitutes its own commands and reports the named boxes as checked, i.e. fabricates "manage.py check passes" on a repo with no manage.py. The frontmatter's `framework: django` declares an assumption but provides no absence fallback, which is exactly the rubric's unexecutable-against-reality class.

**Smallest fix:** one fallback sentence per command block: "if the host lacks `manage.py`/these paths, substitute the host's equivalent (per the project adapter or `docs/testing.md`) and name the substitution explicitly in the execution plan" — and rewrite the stop-condition lines to name the property ("framework's dangling-reference check passes") rather than the host command.

### F5 — MEDIUM (workflow trap / load-bearing gap): the eighth shape has no stop condition, so its commit gate is vacuous

Step 2 (`SKILL.md:163-165`) instructs: read the matching `fix-shapes.md` section, "Each playbook has an explicit stop condition — do not commit unless you can check every box," and Step 3's precondition (`SKILL.md:195`) is "playbook's stop condition satisfied." But the **workflow registry cleanup** shape (`SKILL.md:139`) routes to the inline checklist at `SKILL.md:167-191`, which contains action items and prohibitions but no stop-condition block.

**Execution-time failure:** for registry clusters the commit gate references a stop condition that doesn't exist, so Step 3's precondition is satisfiable by assertion — the executor self-certifies and commits. This is the highest-blast-radius shape in the skill (cross-layer endpoint/boot-payload authority) running with the weakest gate.

**Smallest fix:** append a "Stop condition" block to the checklist mirroring its own mandates: boot-payload characterization tests green; every registry key asserted equal to `reverse(...)`; cache-busting bumped on every touched JS include; guard added or deferred with a named reason.

### F6 — MEDIUM (artifact-reality drift + hallucination-invited): Form B delegates to a `/find-duplication` stage that doesn't exist by that name and isn't standalone-runnable

`SKILL.md:83-84`: "Run the Investigation sub-steps of `/find-duplication` on just that file." `find-duplication/SKILL.md` has no section named "Investigation"; the nearest is "Stage 4 — Investigate" (`find-duplication/SKILL.md:112`), which is a sub-agent fan-out consuming Stage 1–3 artifacts (`${REPORT_DIR}`, `classified.json`, the `agents/investigate.md` prompt template with substitutions). It cannot run "on just that file" without the pipeline in front of it.

**Execution-time failure:** the executor either runs the entire find-duplication pipeline against one file (heavyweight; writes a scan directory the user didn't ask for) or — more likely — performs an unspecified "investigation" of its own design and presents the result as having followed the referenced procedure.

**Smallest fix:** inline the three or four questions Form B actually needs (who calls it; where do the bodies diverge; is there a canonical equivalent; what tests cover it) and drop the cross-skill stage pointer.

### F7 — LOW-MEDIUM (workflow trap): no back-edge for "report exists but cluster ID not found"

The abort path at `SKILL.md:71-74` covers a missing report file only. `SKILL.md:75` then says "Find the matching cluster" with no instruction for an ID that isn't in the report — the common case when a user quotes an ID from an older scan after `latest` has been re-pointed.

**Execution-time failure:** the executor fuzzy-matches `cluster:P0-1` to the closest-looking entry in the current report and refactors the wrong files under Form A's no-confirmation fast path — the one path with no human checkpoint before edits.

**Smallest fix:** one sentence after line 75: "If no exact ID match exists in the loaded report, list the available IDs and abort — do not fuzzy-match."

### F8 — LOW (artifact-reality drift): the effectiveness-log bucket vocabulary doesn't cover the shape table

`SKILL.md:285-286` enumerates six bucket values (`dedup, delete, fix, promote, migrate, shadow`) keyed "on the shape", but Step 1's table (`SKILL.md:128-139`) defines eight shapes, and several (`template triplication`, `quasi-dead / broken`, `workflow registry cleanup`) have no stated mapping to a bucket.

**Execution-time failure:** different runs pick different keys for the same shape, fragmenting the trend buckets that `reports/_meta/dashboard.md` aggregates — defeating the stated purpose at `SKILL.md:269-272`. (The invocation itself is correct: every flag in the documented command at `SKILL.md:275-283` exists in the argparse contract at `scripts/log_effectiveness.py:47-67`, all four required flags are supplied, and `--buckets '{"<shape>": 1}'` passes the JSON-dict validation at lines 75-81. `python3` rather than `.venv/bin/python` is also fine here — the script is stdlib-only by design, per its docstring and the stdlib-only `skill_use` import.)

**Smallest fix:** an eight-row shape→bucket mapping next to the command (e.g. template triplication → `dedup`, quasi-dead → `fix`, registry cleanup → `migrate`).

### F9 — LOW (workflow trap, ordering): Forms B/C require Step-1 work before Step 1 runs

Form B/C approval requires presenting a plan with "Fix shape (from the table in Step 1)" (`SKILL.md:92`) before any edits, while `SKILL.md:153-156` says the Step-1 plan for Forms B/C is "an internal record; the user already approved scope during argument parsing." So the classification table and investigation that produce the approval plan live in a step that nominally runs after approval.

**Execution-time failure:** mild but real — an executor following the steps in order presents a shape-free plan for approval (under-specified consent), then classifies afterward and discovers a different shape than the user approved.

**Smallest fix:** reword the Form B/C instruction to "perform Step 1 first, present that plan for approval, then proceed to Step 2" and delete the duplicate plan description from Argument Parsing.

## What the skill gets right

This is one of the better-framed execution skills in the ecosystem, and several rubric lenses come back clean. **GOAL:** for dedup shapes the skill genuinely tests the success property, not artifact existence — the R14 jscpd re-scan checks that the clone count actually dropped, and the 2a stop condition demands byte-identical call-site log lines and a `git diff --stat` that matches the plan; these are artifact-checkable, not narrative. **FRAME:** the "invocation is not blanket authorization" frame is established up front (`SKILL.md:31-36`) and re-activated at the decision sites — the approval-token contract (`SKILL.md:99-108`) is an unusually concrete anti-misreading device (first-token match, conjunction flips to change-request), and Step 7 re-states the no-auto-continue rule at the exact point an executor would be tempted. **SURVEY:** Step 1 mandates reading targets in full and explicitly quarantines the detector's theory ("Don't trust triage as exhaustive"), and §2c's double re-grep (word-boundary plus string-literal dispatch search, with an abort on any new reference) is a model survey-before-destruction step. **Back-edges:** missing-report abort with no codebase-scan fallback (`SKILL.md:71-74`), test-failure-means-no-commit with a bounded fix budget, revert-commit-not-reset, concurrency-collision abort — the Failure Modes section covers the hypotheses-died cases most skills omit. The learnings tiers are explicitly disambiguated (`SKILL.md:262-267`), and the effectiveness log is real telemetry, not ceremony — consumed by `scripts/skill_effectiveness.py` (which renders `reports/_meta/dashboard.md`), `scripts/triage_audit.py`, `scripts/host_attest.py`, and the `/which-cleanup` scripts. The skill's failures are almost entirely drift (a deleted knowledge file, a handoff added upstream without a route here, host paths never parametrized), not frame design.

## Load-bearing table

Every mandated verification/reporting step, and whether its output is consumed downstream: the **Step-1 execution plan** is consumed — Step 4's `git diff --stat` check gates the commit against the plan's file list, and the 2a stop condition references it (wired). The **2a/2b/2c/2d stop conditions** gate Step 3's precondition (wired, except the registry shape, F5, and §2c's host-bound commands, F4). The **Step-3 test matrix** gates the commit but its source artifact doesn't exist (F1) — currently a hallucination point rather than a gate. The **jscpd re-scan** is consumed by R14's success judgment, but its command is missing (F1) and no mandated artifact records its before/after counts — an executor can skip it and nothing downstream notices; wire its output into the learnings entry's Tests section or it will be skipped under load. The **Step-5 learnings entry** is consumed by the user's next-cluster choice and hosts Step 6's follow-on findings, which Step 7's recommendation explicitly draws on (wired, human-consumed), but the **running LOC delta table** has no named consumer anywhere in the ecosystem — pure ceremony as written; either name its consumer or delete the obligation. The **effectiveness log** is the best-wired step in the skill: schema documented in `.claude/skills/_common/skill-conventions.md`, aggregated by `scripts/skill_effectiveness.py` into `reports/_meta/dashboard.md`, and read by `/which-cleanup` and `scripts/host_attest.py` (wired, multiple consumers).
