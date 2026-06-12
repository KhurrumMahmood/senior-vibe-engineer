# Operations — paths, environment, archaeology, report layout

The orchestrator reads this file at the start of Phase 1. It holds the
operational detail SKILL.md summarizes: worktree and venv rules, the
cleanliness guard, the git-archaeology recipe and report schema, the
report directory layout, and the verification test matrix. Where a
value is host-project-specific, an explicit `host-adapter` slot marks
it — substitute the host project's value deliberately; never improvise
one silently.

## Worktree and venv rules

- **Run wherever invoked.** Confirm the worktree with
  `git rev-parse --show-toplevel` before Phase 1; pass the result to
  every scout brief as `{{worktree}}`.
- **Never fall back to a sibling worktree's venv** (L-1). The venv
  must belong to the worktree being edited.
- **Interpreters:** `.venv/bin/python` for Django commands; plain
  `python3` for `scripts/specs.py`, `scripts/ledger.py`, and
  `scripts/chunk_file.py` (all stdlib-only).
- **Venv resolution** — verify before any Django command, falling
  back to `$PYTHON_VENV_PATH` only when the worktree lacks its own
  `.venv` (L-16: don't silently fall back to `.venv/` in the wrong
  worktree):

  ```bash
  if [ -z "${PYTHON_VENV_PATH:-}" ] && [ ! -x .venv/bin/python ]; then
    echo "ERROR: no venv. Install dependencies per CLAUDE.md."
    exit 1
  fi
  ```

  Scout briefs receive the resolved interpreter as `{{venv}}` (e.g.
  `.venv/bin/python` or `$PYTHON_VENV_PATH/bin/python`).

## Scripts

All stdlib-only — invoke with plain `python3`:

- `scripts/specs.py show|coverage|inventory-check|solid|violations
  <spec-id>` — spec gates. `solid --json` and `violations --json`
  write to **stdout**; redirect to the report file yourself (paths in
  the layout table below).
- `scripts/ledger.py list --decision split_queued,monitor` and
  `scripts/ledger.py update <file> --decision <d> --rationale <r>
  [--next-review-days <int>]` — refactor ledger. `update` is an
  upsert; there is no separate `add` subcommand.
- `scripts/chunk_file.py <file> --token-budget 8000 --loc-budget 2500
  [--loc-hints <start:end,...>] --format json|markdown
  --output <path>` — Phase 1.3.0 chunker.

## Cleanliness guard

`code_roots` must be clean — no unrelated uncommitted edits — before
Phase 1 AND before every Phase 5 batch. Two distinct checks; do not
conflate them:

1. **Current-worktree dirty check** (the guard itself). Run from the
   repo root of the worktree being edited:

   ```bash
   cd "$(git rev-parse --show-toplevel)"
   git status --porcelain | grep -E '<code_roots regex>' \
     && echo "DIRTY — resolve before proceeding" || echo "clean"
   ```

   Any hit means unrelated uncommitted edits overlap the refactor's
   scope. Stop; have the human commit or stash them first.

2. **Main-worktree collision check** (execution-playbook §5.2 step 0,
   R6 / L-4). A *different* check: it watches the MAIN worktree's
   dirty set for mid-refactor collisions and re-runs before every
   Phase 5 batch. Commands and stop rules live in the playbook.

## Git archaeology recipe (Phase 1.4)

**Triggers and ownership** (split by churn — L-7; the owner travels
in the chunk map's `Archaeology owner` column and the
`archaeology_owner` key of `inventory/chunks.jsonl`):

- **≤ 500 LOC AND ≤ 20 commits** → the scout runs it inline for its
  file (the brief's archaeology section activates when
  `{{archaeology_owner}} == "scout"`).
- **Everything else** → the orchestrator runs it in parallel with
  scout dispatch.
- **≥ 50 commits** → archaeology is **mandatory** (R17, R4). The
  archaeology file must contain at least 3 load-bearing LR-T
  candidates with `<!-- archaeology: <hash> -->` tags.

**Commands.** These are the scout-side commands — the only concrete
commands the source material preserves. R4's base command is
`git log --follow -p`. No distinct orchestrator-side variant exists;
the orchestrator runs the same commands:

```bash
git log --follow --oneline <file> | head -50
git log --follow -p <file> | head -500
```

**Subject-word filter.** Bias the scan toward high-signal commits by
filtering commit subjects for failure/defense vocabulary, applied to
the `--oneline` subject list:

```bash
git log --follow --oneline <file> | grep -iE 'fix|retry|timeout|crash'
```

<!-- host-adapter: extend subject-word list. Only the four terms
fix|retry|timeout|crash survive from the original recipe — the full
list is lost. Add the host project's failure vocabulary here. -->

Calibration point: on a 102-commit file the recipe yielded 7
load-bearing LR-T candidates (L-25).

**Tag convention.** Every rationale recovered from a commit message
carries `<!-- archaeology: <hash> -->` inline — in the report entry
and in the spec LR-T item it becomes — so Phase 7 crystallization
preserves the invariant's origin. Pinned archaeology hashes are a
recognized exception to staleness rules
(`.claude/skills/_common/skill-conventions.md`).

## Archaeology report schema

Orchestrator-run archaeology writes
`reports/refactor/<spec-id>/archaeology/<basename>.md`. One entry per
load-bearing rationale, matching the LR-T candidate shape from
`agents/inventory-scout.md` (Output 3, Bucket 4):

```markdown
# Archaeology — <file>

### LR-T candidate: <short name>
**File:** <path>:<line>
_<one-line purpose summary>_
**Behavior:** <the invariant and why the defensive block exists>
<!-- archaeology: <hash> -->
**Proposed text:** <LR-T item text for the spec>
```

Files with ≥ 50 commits need ≥ 3 such entries (R17). Scout-run
archaeology skips this file — its entries land directly in the
scout's Output 3 as Bucket 4 LR-T candidates. Both paths feed Phase
2.2 consolidation and the Phase 3.1 spec update; §3.3 REM entries
cite the file in their `**Archaeology:**` field.

## Report directory layout

Everything the run writes lives under `reports/refactor/<spec-id>/`:

| Artifact | Written by | Consumed by |
|---|---|---|
| `convention-sources.md` | 1.2 | scout briefs |
| `phase-1-inventory-gate.md` | 1.1.5 (drift delta log) | 1.5 delta count |
| `phase-1-solid-audit.md` | 1.2.5 (decomposition mode) | Phase 3 plan; `specs.py solid` L1 gate |
| `inventory/<basename>__chunks.json` / `__chunks.md` | 1.3.0 | chunk map; scout dispatch; 1.5 coverage gate |
| `inventory/chunks.jsonl` | 1.3.0 (orchestrator-built manifest) | §1.3 subprocess dispatch loop |
| `inventory/{chunk_id}__L{s}-L{e}.md` | 1.3 scouts (primary brief) | 1.5 gate |
| `findings/{chunk_id}__L{s}-L{e}.md` | 1.3 scouts | 2.3 consolidation |
| `extracted/{chunk_id}__L{s}-L{e}.md` | 1.3 scouts | 2.2 consolidation |
| `archaeology/<basename>.md` | 1.4 | 1.5 gate cond. 3; §3.3 archaeology field |
| `phase-1-inventory.md` | 1.5 | Phase 2 gate; Phase 3 |
| `extracted-behaviors.md` | 2.2 | 3.1 spec update; Phase 4 review |
| `findings.md` | 2.3 | Phase 4 review; 5.3.5 swarm; 5.4 adoption table |
| `phase-3-plan.md` (+ §Sign-off at 4.3) | 3.2 | Phase 4 review; 5.2 batches; 5.3/5.4/6.0 scope |
| `phase-5-violations.json` | 5.4 (redirected `violations --json`) | code_roots filter; swarm dispatch |
| `phase-6-boundary.md` | 6.0 | Phase 7 entry gate |
| `phase-6-solid.json` | 6.3 (redirected `solid --json`) | 6.3 Level-3 scout |
| `phase-6-solid-agent.md` | 6.3 Level-3 scout | 6.3 verdict read; 7.2/7.3 follow-up intake |
| `phase-6-interface-depth.md` | 6.3.5 | in-phase blocking decision; 7.3 follow-ups |

Outside the reports tree: characterization tests live at
`tests/test_<spec-id>_characterization.py` (deleted or promoted at
7.1, with golden files under `snapshots/`); the learnings entry
appends to `reports/duplication/learnings.md` (7.3); the
effectiveness line appends to `reports/_meta/effectiveness.jsonl`
(7.5).

## Verification test matrix

<!-- host-adapter: test matrix. The source material for this skill
does not preserve a full suite-per-change-shape matrix. Define the
host project's baseline suites, per-subsystem suites, and test-runner
invocation here. Worked example from the origin project: baseline =
`tests.test_site_capabilities tests.test_hydration_detector`;
runner = `.venv/bin/python manage.py test <modules>
--settings=app.settings_test_sqlite -v 2`. -->

Invariants that hold regardless of host values:

- The characterization suite must pass at HEAD (2.1), after every
  Phase 5 batch (execution-playbook §5.2), and at 6.1.
- Per-batch suites come from the plan's test strategy (item 7) and
  carry the coverage-path proof (R36): at least one named suite
  imports or patches each batch's destination modules.
- Phase 6 gates run the SQLite matrix; live integration suites are
  not a gating signal (see SKILL.md Non-goals).
