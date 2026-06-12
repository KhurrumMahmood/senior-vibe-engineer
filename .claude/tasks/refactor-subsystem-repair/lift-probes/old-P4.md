# Probe P4 — old skill, resume mid-run (`extraction-pipeline`)

**Scenario:** Fresh session, no memory. Human: "Resume the refactor for spec
`extraction-pipeline` — it's mid-run." First five concrete actions before
touching any code.

**Skill basis:** The old SKILL.md has **no dedicated resume protocol**. Resumption
therefore falls out of the skill's own state-recovery machinery: the spec *is* the
plan (Core belief 1 / R1), `specs.py coverage` is the drift gate, the
`reports/refactor/<spec-id>/` directory is the phase record, and the §4.3 Sign-off
block is the only license to be in Phase 5 at all. The pre-Phase-1 guards (worktree
confirmation, cleanliness guard, venv check) are unconditional, so a fresh session
runs them again.

## The first five actions, in order

### 1. Confirm where I am — worktree and branch

```bash
git rev-parse --show-toplevel
git branch --show-current
git log --oneline -15
```

Mandated by §Scope: "Worktree: run wherever invoked. Confirm with
`git rev-parse --show-toplevel` before Phase 1." Mid-run this is doubly load-bearing:
the prior session may have been operating in a dedicated worktree/branch, and the
`git log` tail shows which `[batch-tag]`-prefixed Phase 5 commits (if any) already
landed — the first evidence of how far execution got.

### 2. Load the spec — `specs.py show`

```bash
python3 scripts/specs.py show extraction-pipeline
```

Mandated by §Scope ("Validate with `python3 scripts/specs.py show <id>`") and
Phase 1.1. Record from the output: `code_roots`, spec `status`, and the
`[ ]` / `[~]` / `[x]` state of every IM/AR/EX/LR-T item. Per Core belief 1, the
checkbox map is the authoritative record of what the previous session finished
(`[x]`), had in flight (`[~]`), and never started (`[ ]`).
Branching per Phase 0: exit 1 ("no spec with id") → read `knowledge/bootstrap.md`
and scaffold (shouldn't happen for a mid-run spec — treat as a red flag and ask);
any other non-zero exit → abort and report.

### 3. Run the cleanliness guard on `code_roots` + verify the venv

```bash
git status --porcelain -- <each code_roots path>     # must be empty

if [ -z "${PYTHON_VENV_PATH:-}" ] && [ ! -x .venv/bin/python ]; then
  echo "ERROR: no venv. Install dependencies per CLAUDE.md."
fi
```

Mandated by §Scope: "`code_roots` must be clean (no unrelated uncommitted edits)
before Phase 1 AND before every Phase 5 batch" — and the venv check is the Phase 1.1
snippet. On a mid-run resume the cleanliness guard is the critical tripwire: a dirty
`code_roots` means the previous session died **mid-batch**. Per R6
(commit-or-revert atomicity) that half-applied batch must be resolved — revert it
(or, with the human, commit it if genuinely complete and green) before any further
work. Do not build on partially-applied state.

### 4. Run the drift gate and the ledger listing

```bash
python3 scripts/specs.py coverage extraction-pipeline
python3 scripts/ledger.py list --decision split_queued,monitor
```

Both are the remaining Phase 1.1 commands. `coverage` is the skill's purpose-built
mid-run state detector — its three drift classes localize exactly where the prior
session stopped:

- `checkmark_lag` — item marked `[x]` but no `# spec` code ref → marker flipped but
  code never landed (or landed wrong);
- `orphan_refs` — `# spec:` comment in code with no matching spec item;
- `implementation_ahead` — code refs exist but item still `[ ]` → Phase 5 landed a
  batch and died before flipping the marker.

Phase 1.1 is explicit: "If `coverage` reports drift … **fix the drift first** —
either as a sub-task or abort and report. A spec that already drifts is not a safe
refactor target." So drift repair precedes any resumed execution.

### 5. Read the run's report directory to fix the resume point — Sign-off first

```bash
ls -la reports/refactor/extraction-pipeline/
```

Then read, in order of decision weight:

1. `reports/refactor/extraction-pipeline/phase-3-plan.md` — and specifically check
   for the **`## Sign-off`** section (§4.3). This is the fork: if no sign-off (or
   only a partial-scope sign-off) is recorded, the run is at Phase ≤ 4 and I must
   NOT execute anything — Phase 4.2 forbids proceeding without an explicit,
   unconditional approval recorded from the human. If a sign-off exists, its
   "Approved scope" / "Not approved (deferred)" lists bound what resumed Phase 5
   work may touch.
2. `phase-1-inventory.md`, `phase-1-inventory-gate.md`, `convention-sources.md`,
   `extracted-behaviors.md`, `findings.md` — presence/completeness of each gate
   artifact (including the three-outputs-per-chunk rule, Phase 1.5 gate) locates the
   furthest **completed** phase gate. Resume at the first phase whose gate artifacts
   are missing or incomplete; re-dispatch incomplete scouts rather than trusting
   partial outputs (Core belief 5 / R2).

## What happens next (beyond the five, for context)

Only after the resume point is fixed: if resuming Phase 5, read
`knowledge/execution-playbook.md` in full (mandatory per Phase 5), re-run the
concurrency/cleanliness check at the start of the next batch (R6), and verify the
characterization tests still pass on current HEAD before moving more code. No
production code is touched before all five steps above complete.
