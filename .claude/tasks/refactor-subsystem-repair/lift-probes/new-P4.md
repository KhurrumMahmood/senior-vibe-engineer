# Probe P4 — fresh-session resume of spec `extraction-pipeline` (new skill)

Scenario: fresh context, human says "resume the refactor for spec
`extraction-pipeline` — it's mid-run." The governing section is SKILL.md
**"Resuming mid-refactor"** (lines 133–153), which maps onto five concrete
actions before any code is touched.

## First five concrete actions, in order

### 1. Infer the current phase — run the two state probes the protocol names

```bash
python3 scripts/specs.py coverage extraction-pipeline
ls reports/refactor/extraction-pipeline/
```

(Plain `python3`, not the venv — `scripts/specs.py` is stdlib-only per
`knowledge/operations.md` §Scripts. I also run
`python3 scripts/specs.py show extraction-pipeline` here to recover
`code_roots`, which action 5's guard regex needs; `git rev-parse
--show-toplevel` confirms the worktree per SKILL.md §Scope.)

The coverage output (`[ ]`/`[~]`/`[x]` states, checkmark_lag, orphan_refs)
plus the artifacts present in the report directory tell me which phase last
completed, decoded against the "Report directory layout" table in
`knowledge/operations.md` — e.g. `phase-1-inventory.md` only → resume at
Phase 2; `extracted-behaviors.md` + `findings.md` but no `phase-3-plan.md`
→ Phase 3; `phase-3-plan.md` with a §Sign-off block and some batch commits
→ mid–Phase 5.

### 2. Read the report-layout / operations reference to decode the artifacts

```text
Read .claude/skills/refactor-subsystem/knowledge/operations.md
```

Resume step 1 explicitly points at this file ("see
`knowledge/operations.md` 'Report directory layout'"), and step 5 needs its
cleanliness-guard commands. SKILL.md also mandates it as the
start-of-Phase-1 read, so it is required at every resume point.

### 3. Re-read the inferred phase's knowledge file — IN FULL, not from memory

```text
If the artifacts say Phase 5 (mid-execution, the likely "ended partway
through" case):
  Read .claude/skills/refactor-subsystem/knowledge/execution-playbook.md  (in full)
If Phase 1/2: operations.md (already read in action 2) suffices.
If the spec turned out not to exist at all (specs.py show exit 1):
  Read .claude/skills/refactor-subsystem/knowledge/bootstrap.md instead.
```

SKILL.md is explicit: "Phase 5 means `knowledge/execution-playbook.md` IN
FULL — not from memory" and "Do not resume a Phase 5 batch with the
playbook unread."

### 4. Restate the approved scope and waivers before any edit

```text
Read reports/refactor/extraction-pipeline/phase-3-plan.md   (§Sign-off block)
```

Restate in the conversation: approved split-plan scope, the explicit list
of approved remove candidates, findings triage (which P1s → fix commits),
convention-enforcement scope (subsystem-only vs repo-wide), and anything
listed under **Not approved (deferred)**. Sign-off scope is honored
token-for-token; nothing executes beyond it. While doing this I re-arm
beliefs 3 and 4 (resume step 4): unknown code STAYS; deletion requires the
recorded human approval in this block. If the run hasn't reached Phase 4
yet (no §Sign-off), there is no approved scope — execution is off the
table and the resume target is the earlier phase's outputs instead.

### 5. Re-run the cleanliness guard before touching anything

```bash
cd "$(git rev-parse --show-toplevel)"
git status --porcelain | grep -E '<code_roots regex from specs.py show>' \
  && echo "DIRTY — resolve before proceeding" || echo "clean"
```

(Exact commands from `knowledge/operations.md` §Cleanliness guard, check
1 — the current-worktree dirty check.) Any hit = unrelated uncommitted
edits overlap the refactor's scope → STOP and have the human commit or
stash before proceeding. If resuming a Phase 5 batch, the playbook's §5.2
step 0 main-worktree collision check (R6) also re-runs at the top of the
batch.

## Only after all five

…do I pick up the actual work: re-dispatch incomplete scouts, finish the
in-flight batch per the playbook protocol, or whatever the inferred phase
dictates — never editing code before the sign-off scope is loaded and the
guard reports clean.
