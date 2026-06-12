# Probe: old skill, P4 control — resume mid-run spec `extraction-pipeline`

**Scenario:** Fresh session, no memory. Human says: "Resume the refactor for
spec `extraction-pipeline` — it's mid-run, the previous session ended
partway through."

**Skill version:** /tmp/refactor-skill-old/ (SKILL.md + knowledge/ + agents/)

**Observation up front:** the old skill has **no explicit resume protocol**.
Nothing in SKILL.md, knowledge/execution-playbook.md, or
knowledge/learnings.md describes re-entering a mid-run refactor. The five
actions below are therefore derived from the skill's state-bearing
artifacts and gates: the spec is the plan (Core belief 1 / R1), batches
commit-or-revert atomically (R6), Phase 4 approval must be recorded on
disk (§4.3), and the cleanliness guard runs before Phase 1 AND before
every Phase 5 batch (Scope section, execution-playbook §5.2.0). State is
reconstructed from disk — never from the prior session's implied claims.

---

## The first five concrete actions (no code touched)

### 1. Confirm worktree, branch, and tree cleanliness

```bash
git rev-parse --show-toplevel
git branch --show-current
git status --porcelain
```

**Why first (SKILL.md §Scope; execution-playbook §5.2.0; R6).** The skill
mandates confirming the worktree with `git rev-parse --show-toplevel`
before Phase 1, and the cleanliness guard requires `code_roots` clean
before Phase 1 and before every Phase 5 batch. On a resume this is the
highest-risk check: R6 says every batch commits or reverts atomically, so
a **dirty tree means the previous session died mid-batch** — uncommitted,
possibly half-moved code. If `git status --porcelain` shows modified files,
I stop and resolve that (revert the partial batch or, if truly complete and
green, finish its commit only after the gates below confirm it was an
approved batch) before any other work. A clean tree means the last batch
either landed or was never started.

### 2. Load the spec — the plan of record

```bash
python3 scripts/specs.py show extraction-pipeline
```

**Why (SKILL.md §1.1; Core belief 1).** "The spec is the plan. If the spec
says `[x] IM-N`, the code must reflect it. If it says `[ ]`, the work
hasn't happened." This single command recovers: `code_roots` (the approved
scope), and the per-item `[ ]` / `[~]` / `[x]` states — `[~]` items mark
exactly where execution stopped, because §5.1 flips markers to `[~]` when
a batch begins and `[x]` only when it lands. If `show` exits 1 ("no spec
with id"), the human's "mid-run" claim is wrong and I'd report rather than
bootstrap (Phase 0 is for new specs, not resumes). Any other non-zero exit
is an abort signal — report and stop. (Per §1.1 I also note the venv check
here — `.venv/bin/python` or `$PYTHON_VENV_PATH` must exist before any
Django command later.)

### 3. Run the coverage drift gate

```bash
python3 scripts/specs.py coverage extraction-pipeline
python3 scripts/ledger.py list --decision split_queued,monitor
```

**Why (SKILL.md §1.1, §6.2; R1).** Coverage is the skill's spec↔code
truth-reconciler, and on a resume it pinpoints how the previous session
died:

- `checkmark_lag` — item marked `[x]` but no `# spec` comment in code: the
  prior session claimed work that never landed (or landed and was lost).
- `implementation_ahead` — `# spec:extraction-pipeline::IM-N` comments in
  code but the item still `[ ]`: a batch landed but the session died before
  flipping the marker.
- `orphan_refs` — code references an item the spec doesn't have.

§1.1 is explicit: "If `coverage` reports drift, **fix the drift first** —
either as a sub-task or abort and report. A spec that already drifts is not
a safe refactor target." The ledger listing (also §1.1) recovers any
`monitor` / `split_queued` entries the prior session recorded mid-run
(§5.5 says ledger updates are live state, so they are a reliable trace of
how far Phase 5 got).

### 4. Inventory the on-disk phase artifacts

```bash
ls -la reports/refactor/extraction-pipeline/
ls -la reports/refactor/extraction-pipeline/inventory/ \
       reports/refactor/extraction-pipeline/findings/ \
       reports/refactor/extraction-pipeline/extracted/ \
       reports/refactor/extraction-pipeline/archaeology/ 2>/dev/null
```

**Why (SKILL.md report layout throughout Phases 1–6).** Each phase writes
named artifacts, so the directory listing is a phase odometer:
`convention-sources.md` + `phase-1-inventory.md` (+ optional
`phase-1-solid-audit.md`, `phase-1-inventory-gate.md`, chunk maps) → Phase 1
done; per-chunk three-output scout files + consolidated
`extracted-behaviors.md` / `findings.md` → Phase 2 done (and §1.5 / §2.2
require re-dispatch if any chunk is missing one of its three outputs —
R2: partial scout returns are not acceptable, even inherited ones);
`phase-3-plan.md` → Phase 3 done; `phase-5-violations.json` → Phase 5
started; `phase-6-*` files → verification started. The
characterization test file `tests/test_extraction_pipeline_characterization.py`
existing (Phase 2.1) is part of this sweep.

### 5. Read the plan's §Sign-off and cross-check landed batches

```bash
# Read (not edit):
#   reports/refactor/extraction-pipeline/phase-3-plan.md   — esp. "## Sign-off"
git log --oneline -30 | grep -E '\[extraction-pipeline:(batch|convention|caller-fixup)'
```

**Why (SKILL.md §4.2–4.3; execution-playbook §5.2 step 7).** Phase 4 is the
hard human gate: "I do not proceed past Phase 4 without explicit approval."
On a resume the ONLY acceptable evidence of approval is the recorded
`## Sign-off` block in `phase-3-plan.md` (approved-by, timestamp, approved
scope, deferred items) — a fresh session must not infer approval from the
fact that execution apparently started. Three outcomes:

- **No `phase-3-plan.md` / no sign-off block** → the run stopped in
  Phases 1–3; resume there (re-validating the Phase 1.5 / 2.2 gates) and
  go to Phase 4 for approval before any execution.
- **Sign-off present** → cross-reference the plan's batch list against the
  `[extraction-pipeline:batch-N]` commit prefixes in `git log` to identify
  the next unexecuted batch — and note partial-approval scope (§4.2 rule 3):
  only execute what the recorded sign-off actually approved.
- **Sign-off present but coverage (action 3) showed drift** → fix drift
  first; resuming execution on a drifting spec is exactly what §1.1 forbids.

Only after these five actions — and after fixing any drift / dirty-tree
findings they surface — does execution resume, and then only by re-running
the §5.2.0 concurrency check at the top of the next batch.

---

## Summary of decision logic

| Evidence found | Resume point |
|---|---|
| Dirty tree in `code_roots` | Stop; resolve the half-finished batch first (R6) |
| Coverage drift (any class) | Fix drift before anything else (§1.1, R1) |
| Phase 1/2 artifacts incomplete (missing scout outputs) | Re-dispatch scouts; re-run Phase 1.5 gate (R2) |
| Plan exists, no §Sign-off | Resume at Phase 3→4; present review package, block for approval |
| §Sign-off recorded, batches partially landed | Resume Phase 5 at next unexecuted batch, after §5.2.0 concurrency re-check |
| All batches landed | Resume at Phase 6 verification gates |
