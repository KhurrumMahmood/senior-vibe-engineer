---
name: propose-boundary
description: Turn a confirmed or suspected missing-boundary into a read-only boundary-extraction proposal. Consumes a target (file path, directory, or skill directory) and emits reports/propose-boundary/<target-slug>/proposal.md with candidate seams, proposed public API, backward-compat shim shape, caller-impact summary, and characterization-test matrix. Read-only — no edits. Hands off to /refactor-subsystem (decomposition mode).
argument-hint: "<target-path-or-name> [--candidates N]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: explain
best_for: |
  A file or directory where distinct domain concerns live side-by-side
  with no defined public contract — sibling modules reach into each
  other's private helpers, change-amplification touches the same N
  files for every feature, test setup explodes because exercising one
  cluster requires fixturing the others. Produces candidate seams +
  proposed public API + shim shape + characterization-test matrix.
  Read-only. Works on `.claude/skills/<name>/` directories too —
  sub-phases (parsed from SKILL.md `## Phase N` headings) are treated
  as symbols, naming-prefix alignment as the cluster signal.
not_for: |
  Detection of which subsystems exist (use /map-subsystem first).
  Intra-file responsibility split where the smell is one file with
  three domains (use /find-omnibus then /refactor-subsystem). Folder-
  topology promotion / demotion (use /find-folder-topology-drift +
  /propose-folder-reorganization). Refactor execution (use
  /refactor-subsystem in decomposition mode). Cross-subsystem boundary
  proposals — v1 is intra-subsystem only; cross-subsystem stays in the
  System-tier chain (/scope-feature → /impact-feature → /architecture-
  fit → /plan-spec).
language: python
framework: any
---

# /propose-boundary

You are the **orchestrator** for turning a suspected missing-boundary
target into a read-only boundary-extraction proposal. The user has named
a file or directory where distinct concerns live together without an
explicit contract; your job is to score the candidate seams, propose
the public API surface, sketch the backward-compat shim, and emit a
proposal the human reviews before handing off to `/refactor-subsystem`.

You do NOT move files, rename modules, edit any source, or touch
imports in this skill. The only artifact you produce is
`reports/propose-boundary/<target-slug>/proposal.md` plus its
supporting `inspection.json`.

## Core beliefs

1. **This is boundary *proposal*, not boundary *decision*.** The skill
   surfaces candidate seams + their evidence; the human picks. Over-
   surface and let the human prune — same posture as
   `/find-orphaned-ideas --todo`.
2. **Heuristics are evidence, not verdict.** Co-edit frequency, mutual
   import directionality, naming alignment, and cross-cluster call-edge
   density are signals. Each candidate seam carries the raw scores so
   the human can judge whether the cluster is coherent or coincidental.
3. **Backward-compat shim is the migration's safety net.** Every
   proposal sketches a re-export `__init__.py` that keeps existing call
   sites working after the move. If a caller reaches into a *private*
   helper across the proposed boundary, the shim won't cover it — that
   caller becomes a Phase 1 blocker, not a Phase 2 cleanup.
4. **Characterization tests pin behavior before the move.** Every
   public-API symbol gets 2–4 pin tests (input → expected output /
   side-effect) that must pass before AND after the refactor. Same
   discipline as a behavior-preserving two-commit refactor.
5. **The skill ecosystem is a valid target.** Large composite skills
   (a seven-phase orchestrator, a cross-cutting aggregator) are
   themselves boundary-design candidates. When the target is a skill
   directory, sub-phases (parsed from SKILL.md `## Phase N` headings)
   are treated as symbols, the phase number as the cluster signal, and
   the proposal includes an "Orchestration shim shape" section
   sketching how the original skill name keeps working after split.

## Scope

- **Project root:** the working directory.
- **Python:** the host project's venv python (`.venv/bin/python` or
  equivalent) for the helper script — it AST-parses Python sources and
  shells out to `git log` for co-edit frequency; stdlib + git only.
- **Output:** `reports/propose-boundary/<target-slug>/`. Never touches
  any other file.
- **Read-only.** No file moves, no edits, no Edit tool. The
  orchestrator's `allowed-tools` list intentionally excludes Edit.

## Argument parsing

Two forms.

### Form A — file or directory target

```
/propose-boundary <path>
```

e.g. `/propose-boundary <project>/tasks/shared_helpers.py` or
`/propose-boundary <project>/services/sites/`. The target may be a
single Python file, a directory containing Python files, or a skill
directory (`.claude/skills/<name>/`). The helper auto-detects which.

### Form B — subsystem name

```
/propose-boundary <subsystem-name>
```

If `.claude/docs/subsystems/<subsystem-name>.md` exists, the helper
reads it for the file list and uses that as the target. Otherwise the
orchestrator treats the argument as a path and falls through to Form A.

### Optional flag — `--candidates N`

```
/propose-boundary <target> --candidates 3
```

Requests N alternative boundary cuts (default: 1). The helper scores
every candidate seam against the full criterion set and the proposal
ranks the top N. The human picks one (or none) before hand-off.

If the target doesn't exist, has fewer than 2 Python files AND fewer
than 6 public symbols total, the orchestrator stops, logs
`target_not_found` or `target_below_threshold` to the proposal, and
returns.

## Pipeline

Stage 0 — **resolve target.** Parse the argument. Detect target kind:
`file` | `directory` | `skill_directory`. Compute the target slug
(replace `/` with `-`, drop leading dots and `.py`).

Stage 1 — **inspect.** Run the helper:

```bash
.venv/bin/python .claude/skills/propose-boundary/scripts/propose.py \
  --target <path> \
  --project-root . \
  --candidates <N> \
  --output reports/propose-boundary/<target-slug>/inspection.json
```

The helper writes `inspection.json` with:

- `target` — resolved path + target kind.
- `files` — every Python file in scope with line count and public
  symbols list.
- `symbols` — `{name, file, kind, public}` for every top-level symbol
  (functions, classes, module-level constants). For skill-directory
  targets, also includes virtual `phaseN_*` / `phaseN_M_*` symbols
  parsed from SKILL.md `## Phase N` / `### N.M` headings.
- `co_edit_pairs` — top symbol pairs by co-edit frequency, from a
  `git log --name-only` walk over the last 90 days (configurable).
- `naming_clusters` — lexical-prefix clusters; each cluster names
  members and a proposed cluster name.
- `call_edges` — `{caller, callee, count}` for every cross-symbol call
  resolved within the target.
- `candidate_seams` — list of `{cluster_id, members, rationale,
  proposed_public_api, callers_into_private_helpers, scores}` for the
  top N candidate boundary cuts.
- `defer_signals` — guardrail trips (`target_below_threshold`,
  `single_cluster_no_seam`, `scratch_code`).

Stage 2 — **scout callers (optional).** For each `proposed_public_api`
symbol in the top candidate seam, the orchestrator dispatches a cheap
read-only scout (Bash + grep) to confirm the call sites in
`callers_into_private_helpers`. The orchestrator may skip this if the
helper's static analysis already covered the project root.

Stage 3 — **synthesize.** The orchestrator reads `inspection.json` and
writes `proposal.md` per the template below. This is judgment work, not
mechanical — Claude does it, not a script.

Stage 4 — **stop or hand off.** If `defer_signals` are non-empty, the
proposal records `recommendation: defer_<reason>` in the front matter.
Otherwise the proposal recommends `recommendation: refactor` and names
`/refactor-subsystem --target <target-slug>` as the next step.

## Proposal template

The proposal markdown has these sections, in order:

```markdown
# Boundary proposal — <target>

> **Detected by:** `/propose-boundary` (read-only; no edits applied)
> **Decided in:** <host project's ADR on staged boundary
> rearchitecting, if one exists — see the host decision registry>
> **Executed by:** `/refactor-subsystem` (decomposition mode)

**Recommendation:** refactor | defer_<reason>
**Target kind:** file | directory | skill_directory
**Total LOC:** <N>
**Public symbols:** <K>
**Candidate seams scored:** <C> (top <N> presented)

## Current shape

(File tree + documented or detected domains.)

## Candidate seam 1 — <cluster_id> (score: <S>)

**Members.** <symbol list>.

**Rationale.** <why this cluster is coherent — naming alignment,
co-edit frequency above threshold, low cross-cluster call density,
docstring evidence>.

**Proposed public API.**

| Symbol | Signature | Purpose |
|---|---|---|

**Backward-compat shim shape.**

(Python `__init__.py` re-export block keeping existing call sites
working after extraction.)

**Caller-impact summary.**

| Importer | Statement | Shim covers? |
|---|---|---|

**Characterization-test matrix.**

| Public-API symbol | Pin test 1 | Pin test 2 |
|---|---|---|

## Candidate seam 2 — <cluster_id> (score: <S>)

(Same structure, included only when `--candidates N` with N ≥ 2.)

## Orchestration shim shape (skill-directory targets only)

(How the original skill name keeps working after split — thin
orchestrator that invokes new sub-skills in sequence.)

## Migration sequencing (per candidate seam)

1. Pre-move pin-tests.
2. Phase 1: migrate reach-into-private callers.
3. Phase 2: extract cluster (`/refactor-subsystem` decomposition mode).
4. Phase 3: clean up dead re-exports.

## Stop condition

(Behavior preservation + test suite green + every importer routed
through new boundary.)

## Spec hand-off (for /refactor-subsystem)

\`\`\`yaml
---
spec_id: boundary-<target-slug>-<cluster_id>
status: STUB
target: refactor-subsystem
code_roots:
  - <target>
strategy: decomposition
boundary_proposal: reports/propose-boundary/<target-slug>/proposal.md
---
\`\`\`

## Notes (orchestrator judgment)

A short prose section.
```

## Defer signals

- `target_below_threshold` — fewer than 2 Python files AND fewer than 6
  public symbols. Proposal recommends `defer_below_threshold`.
- `single_cluster_no_seam` — every candidate seam scores below the
  threshold; the target's symbols are tightly co-coupled (high cross-
  cluster call density everywhere). Proposal recommends
  `defer_no_seam` and points the human at the SUSPECT step
  (`/find-omnibus` for an intra-file split).
- `scratch_code` — the target matches a known scratch-code path
  (host-project-configured prefix list). Proposal recommends
  `defer_scratch_code`.

## Calibration

- **Co-edit window** defaults to 90 days. Override with
  `--co-edit-days N`.
- **Naming-cluster minimum** defaults to 3 members. Override with
  `--min-cluster-size N`.
- **Seam-score threshold** defaults to 0.4. Override with
  `--seam-threshold T`.
- The skill is intentionally over-permissive on emit; the human
  prunes. Same posture as `/find-orphaned-ideas --todo`.

## Re-runs are idempotent

The helper reads the filesystem and `git log` only. Re-running with
the same target overwrites `inspection.json` and is safe. The proposal
is NOT auto-overwritten — Claude inspects the existing proposal first
and only rewrites the sections that changed.

## Repository layout

```
.claude/skills/propose-boundary/
├── SKILL.md          # this file — orchestrator
└── scripts/
    └── propose.py    # detector + scoring helper (stdlib + git only)
```

## Next skills

- **`/refactor-subsystem`** in decomposition mode — executes the
  proposal under a behavior-preserving two-commit discipline. One
  candidate seam per PR.
- **`/decide`** if the proposal surfaces a tradeoff the host
  project's decision registry doesn't yet cover.
- **`/map-subsystem`** to refresh the subsystem map after the
  extraction lands.

## Related

- `architectural-smells.md` smell 9 (missing-boundary) — detector
  entry that names this skill as the SUSPECT.
- `/map-subsystem` — Stage 4 dep-graph output hints at low-density
  inter-cluster edges that may indicate a missing boundary.
- Host-project ADR on staged boundary rearchitecting (when authored)
  — names the when-to-phase decision framework this skill pairs with.
