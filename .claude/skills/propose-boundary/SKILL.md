---
name: propose-boundary
description: Turn a confirmed or suspected missing-boundary into a read-only boundary-extraction proposal. Python uses its existing AST helper; TypeScript/TSX v1 uses a host-resolved symbol/import/call graph and emits reports/propose-boundary/<target-slug>/proposal.md with candidate seams, public API, compatibility/barrel plan, caller impact, and characterization/native-verification plan. Read-only — no edits. Hands off to /refactor-subsystem (decomposition mode).
argument-hint: "<target-path-or-name> [--candidates N]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: explain
best_for: |
  A TypeScript target needing resolved symbol, import, and call-graph evidence
  for a public API, barrel compatibility, and caller-impact proposal.
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
  /refactor-subsystem in decomposition mode). Proposals spanning multiple
  subsystems are outside v1 and stay in the
  System-tier chain (/scope-feature → /impact-feature → /architecture-
  fit → /plan-spec).
language: any
framework: any
scans: [python, typescript]
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

## How success is judged

- `proposal.md` is complete per the template: candidate seams with raw
  scores, proposed public API table, backward-compat shim shape,
  caller-impact summary, and characterization-test matrix.
- When `inspection.json` carries `defer_signals`, the proposal front
  matter records `recommendation: defer_<reason>` — never a forced
  refactor recommendation.
- Zero production edits — the run writes only under
  `reports/propose-boundary/<target-slug>/`; the hand-off to
  `/refactor-subsystem` is named, not executed.

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

## TypeScript / TSX v1

Use this branch only when the target host supplies one named, project-local `tsconfig.json`
and its own installed `typescript` package. The bundled runner
uses that host's Compiler API to resolve eligible static module specifiers,
top-level target symbols, and target-local call targets. The final artifact is
an `inspection.json` plus `proposal.md`, not a lexical suggestion: it cites
the resolved direct, alias, and barrel import evidence it used.

This is the minimum framework-neutral TypeScript contract:

- Propose a boundary only when two or more coherent top-level symbol domains
  form a partition within the target. Public API candidates are exported,
  non-underscore symbols; underscore-prefixed reaches are explicit Phase 1
  blockers rather than compatibility coverage.
- Record resolved inbound and outbound static imports, target-local resolved
  calls, direct/alias/barrel caller impact, and a compatibility plan that keeps
  the existing `index.ts`/`index.tsx` barrel as a temporary re-export surface.
- Give a characterization matrix and cite the host's native typecheck/test
  commands for the human-approved move. The proposal never edits source or
  runs a codemod.
- Defer explicitly when the target has unresolved or ambiguous module/symbol
  facts. A cohesive one-domain target also defers rather than inventing a
  split. Excluded generated/vendor/test/declaration/minified/build trees stay
  excluded even when named directly.

TypeScript v1 does not infer framework semantics: React, Node, ORM, route,
dependency-injection, runtime loading, dynamic import, reflection, decorator,
or other framework behavior. It does not follow directory symlinks and rejects a direct symlink
target. A missing or invalid `tsconfig`, missing project-local TypeScript, or
syntax error stops clearly with exit code 2. Type errors outside the selected
proposal graph are not converted into framework facts.

The resolver lives in this skill because its output contract is specific to
boundary proposals. Do not extract it into a shared TypeScript platform until
another accepted consumer proves the same resolution and deferral contract.

### Installed TypeScript proposal command

Run this from the target host root after installing only this selected skill.
It writes only under `reports/propose-boundary/` and has no repository-level
Python, `_common`, or sibling-skill import.

To make the stock Codex location from a released source, set
`PROPOSE_BOUNDARY_SOURCE` to that pinned source/ref and run:

<!-- installed-command:stock-install:start -->
```bash
: "${PROPOSE_BOUNDARY_SOURCE:?Set this to the pinned skill source/ref}"
npx --yes skills@1.5.19 add "${PROPOSE_BOUNDARY_SOURCE}" \
  --skill propose-boundary --agent codex --copy -y
```
<!-- installed-command:stock-install:end -->

<!-- installed-command:typescript-proposal:start -->
```bash
PROPOSE_TARGET="${PROPOSE_TARGET:-src/legacy}"
PROPOSE_TSCONFIG="${PROPOSE_TSCONFIG:-tsconfig.json}"
PROPOSE_NAME="${PROPOSE_NAME:-typescript-legacy}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/propose-boundary" \
  ".claude/skills/propose-boundary"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "propose-boundary is not installed in .agents/skills or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/propose_typescript.mjs" \
  --target "${PROPOSE_TARGET}" \
  --project-root "$(pwd)" \
  --tsconfig "${PROPOSE_TSCONFIG}" \
  --candidates 2 \
  --inspection "reports/propose-boundary/${PROPOSE_NAME}/inspection.json" \
  --proposal "reports/propose-boundary/${PROPOSE_NAME}/proposal.md"
```
<!-- installed-command:typescript-proposal:end -->

## Python scope

- **Project root:** the working directory.
- **Python:** the host project's venv python (`.venv/bin/python` or
  equivalent) for the helper script — it routes Python parsing through
  the shared per-language adapter registry (ADR 0032; Python-only here,
  skipping files whose adapter can't supply the raw AST) and shells out
  to `git log` for co-edit frequency; stdlib + git only.
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
read-only scout via `.claude/skills/_common/dispatch_scout_cheap.sh`
(Bash + grep — no Agent tool; the allowed-tools list stays
read-only-tight) to confirm the call sites in
`callers_into_private_helpers`. The orchestrator may skip this if the
helper's static analysis already covered the project root. This cheap-dispatch path requires the host `tools.code_agent` backend (`<!-- host-adapter -->`); use inline scouting when that backend is absent.

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
