---
name: propose-boundary
description: Turn a confirmed or suspected missing-boundary into a read-only boundary-extraction proposal. Family-local evidence supports Python, TypeScript/checked-JavaScript, Go, Java 17, and bounded Rust. It emits reports/propose-boundary/<target-slug>/proposal.md with candidate seams, public API, compatibility plan, caller impact, and characterization/native-verification plan. Read-only — no edits. Hands off to /refactor-subsystem (decomposition mode).
argument-hint: "<target-path-or-name> [--candidates N]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: explain
best_for: |
  A TypeScript or checked-JavaScript target needing resolved symbol, import, and call-graph evidence
  for a stable public interface, backward-compatible barrel, and caller-impact proposal.
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
scans: [python, typescript, javascript, go, java, rust]
---

# /propose-boundary

## Rust v1

Read `knowledge/rust-v1.md`. The Rust adapter inventories one selected Cargo
target, emits distinct JSON/Markdown evidence, and stops at
`complete/review_boundary`; the human still chooses the seam. Macros, build or
generated inputs, include contents, cfg variants, traits/generics, unsafe/FFI,
and public/semver compatibility stay partial or deferred.

```bash
SKILL_ROOT=".agents/skills/on-demand/propose-boundary"
python3 "${SKILL_ROOT}/scripts/propose_rust.py" \
  --project-root "$PWD" --target crates/example \
  --inspection "$PWD/reports/propose-boundary/rust/inspection.json" \
  --proposal "$PWD/reports/propose-boundary/rust/proposal.md"
```

The canonical producer is
`.claude/skills/_common/scripts/rust_proposal_evidence.py`; a copied projection
places the same bytes beside the adapter under the alias
`rust_project_evidence.py`.

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

## TypeScript / TSX and checked-JavaScript v1

The inherited TypeScript subset was `scans: [python, typescript]`; the
frontmatter declaration adds JavaScript only for the checked-JavaScript path
described here.

Use this branch only when the target host supplies one named, project-local `tsconfig.json`
and its own installed `typescript` package. The bundled runner
uses that host's Compiler API to resolve eligible static module specifiers,
top-level target symbols, and target-local call targets. The final artifact is
an `inspection.json` plus `proposal.md`, not a lexical suggestion: it cites
the resolved direct, alias, and barrel import evidence it used.

This is the minimum framework-neutral typed-source contract. Checked JavaScript
uses `--language javascript`, a named `jsconfig.json` or `tsconfig.json`, and
`compilerOptions.allowJs` plus `checkJs` set to true. It accepts `.js`, `.jsx`,
`.mjs`, and `.cjs` (including a mixed JS/TS host) and records selected files
outside that named config as `partial`, never a clean proposal:

- Propose a boundary only when two or more coherent top-level symbol domains
  form a partition within the target. Public API candidates are exported,
  non-underscore symbols; underscore-prefixed reaches are explicit Phase 1
  blockers rather than compatibility coverage.
- Record resolved inbound and outbound static imports, target-local resolved
  calls, direct/alias/barrel caller impact, and a compatibility plan that keeps
  the existing TypeScript `index.ts`/`index.tsx` or JavaScript
  `index.js`/`index.jsx`/`index.mjs`/`index.cjs` barrel as a temporary re-export
  surface.
- In checked JavaScript, treat only same-name, top-level declaration references
  assigned through literal `exports.name`, `module.exports.name`, or
  `module.exports = { name }` forms as resolved CommonJS public API evidence.
  Computed, spread, aliased, or expression-backed CommonJS exports make the
  proposal `partial` until source/runtime confirmation establishes the public
  contract.
- Give a characterization matrix and cite the host's native typecheck/test
  commands for the human-approved move. The proposal never edits source or
  runs a codemod.
- Defer explicitly when the target has unresolved or ambiguous module/symbol
  facts. A cohesive one-domain target also defers rather than inventing a
  split. Excluded generated/vendor/test/declaration/minified/build trees stay
  excluded even when named directly.

This v1 does not infer framework semantics: React, Node, ORM, route,
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
PROPOSE_LANGUAGE="${PROPOSE_LANGUAGE:-typescript}" # typescript | javascript
PROPOSE_TSCONFIG="${PROPOSE_TSCONFIG:-tsconfig.json}"
PROPOSE_NAME="${PROPOSE_NAME:-${PROPOSE_LANGUAGE}-legacy}"
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
  --language "${PROPOSE_LANGUAGE}" \
  --tsconfig "${PROPOSE_TSCONFIG}" \
  --candidates 2 \
  --inspection "reports/propose-boundary/${PROPOSE_NAME}/inspection.json" \
  --proposal "reports/propose-boundary/${PROPOSE_NAME}/proposal.md"
```
<!-- installed-command:typescript-proposal:end -->

## Go v1

The former `scans: [python, typescript, javascript]` declaration is superseded
by the frontmatter Go entry; existing Python and TypeScript/checked-JavaScript
contracts are unchanged.

Use this branch for one package directory in one Go module. It is a deliberately
narrow, read-only proposal: host `go list -e -json -mod=readonly ./...`
establishes the module's active package/import facts, while the bundled
standard-library Go program uses `go/parser`/`go/ast` for top-level declarations
and syntax-level local-call candidates. It never downloads or imports
`go/packages`, `go/types`, a language server, or any third-party module.

Go v1 may recommend an extraction only when all of these facts are available:

- a PATH-discovered Go tool is at least Go 1.22 and the target host is one
  root `go.mod` module with no active `go.work` workspace and no `replace`
  directive (preflighted with `go env GOWORK` and `go mod edit -json`);
- `go list` establishes the target package import path and every first-party
  direct or alias importer;
- the target has two or more named top-level symbol domains, each with at
  least two declarations; and
- no build-tag/cgo source, unresolved package graph, dot/blank importer, or
  generated/vendor/test target makes the evidence incomplete.

Uppercase identifiers are the only public API candidates. Go cannot import an
unexported identifier from another package, so package-private cross-domain
calls are listed as migration blockers rather than a TypeScript-style external
private-import claim. Those calls are AST syntax candidates, not `go/types`
call identities. For each selected exported function, the proposal also lists
same-package exported named types found in its syntax-level signature so the
human can explicitly preserve their identity with a temporary type alias. The
proposal preserves the old package import path only as a human-approved
temporary forwarding/type-alias facade; it never writes one.

This v1 explicitly defers active `go.work` workspaces, modules using
`replace`, build-tagged or cgo target source, dot/blank importers, unresolved
packages, generated/vendor/test targets, and cohesive one-domain packages.
The bundled runner avoids Go 1.18-only syntax so an older toolchain reaches
the explicit Go-version deferral rather than failing to compile the runner.
Dynamic loading, reflection,
interfaces, build matrices, workspaces, external consumers, and runtime
reachability remain outside the claim. A missing or old Go tool emits an
`unsupported` inspection outcome rather than a clean proposal. Malformed Go
source emits a failed syntax outcome.

### Installed Go proposal command

Run this from the Go module root after the router has exposed the on-demand
library. It uses only the selected skill's bundled Go source and the host Go
toolchain; it does not require the toolkit Python environment, sibling skills,
or a network dependency.

<!-- installed-command:go-proposal:start -->
```bash
PROPOSE_TARGET="${PROPOSE_TARGET:-internal/legacy}"
PROPOSE_NAME="${PROPOSE_NAME:-go-legacy}"
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
if ! command -v go >/dev/null 2>&1; then
  printf '%s\n' '{"status":"unsupported","failure_kind":"go_tool_missing"}'
  exit 0
fi
GO_VERSION_OUTPUT="$(go version 2>/dev/null || true)"
GO_VERSION_TOKEN="${GO_VERSION_OUTPUT#* go}"
GO_VERSION_TOKEN="${GO_VERSION_TOKEN%% *}"
GO_VERSION_MAJOR="${GO_VERSION_TOKEN%%.*}"
GO_VERSION_REST="${GO_VERSION_TOKEN#*.}"
GO_VERSION_MINOR="${GO_VERSION_REST%%.*}"
case "${GO_VERSION_MAJOR}:${GO_VERSION_MINOR}" in
  *[!0-9:]*|:*)
    printf '%s\n' '{"status":"unsupported","failure_kind":"go_version_unreadable","minimum_go":"1.22"}'
    exit 0
    ;;
esac
if [ -z "${GO_VERSION_MAJOR}" ] || [ -z "${GO_VERSION_MINOR}" ] || \
   [ "${GO_VERSION_MAJOR}" -lt 1 ] || \
   { [ "${GO_VERSION_MAJOR}" -eq 1 ] && [ "${GO_VERSION_MINOR}" -lt 22 ]; }
then
  printf '%s\n' '{"status":"unsupported","failure_kind":"go_version_too_old","minimum_go":"1.22"}'
  exit 0
fi
go run "${SKILL_ROOT}/scripts/propose_go.go" \
  --target "${PROPOSE_TARGET}" \
  --project-root "$(pwd)" \
  --candidates 2 \
  --inspection "reports/propose-boundary/${PROPOSE_NAME}/inspection.json" \
  --proposal "reports/propose-boundary/${PROPOSE_NAME}/proposal.md"
```
<!-- installed-command:go-proposal:end -->

## Java v1

Use this branch for one named Java package directory in a standalone host that
can compile with JDK 17 without Maven, Gradle, annotation processors, or
third-party dependencies. The bundled single-file Java runner invokes the JDK
compiler tree API with parsing and attribution enabled. Only after all eligible
production sources attribute successfully does it report direct imports or
fully-qualified type references as `compiler-resolved` caller evidence.

Java v1 proposes a seam only when at least two leading type-name domains each
contain at least two top-level types. Public top-level types are proposed as
the compatibility surface; the human still chooses the boundary. A one-domain
package defers instead of inventing a split. Generated, vendor, build, test,
malformed, default-package, mixed-package, and symlink targets never produce a
clean proposal.

This is deliberately a source/package pilot. It does not infer Spring, Jakarta,
Android, reflection, dependency injection, runtime class loading, module-path,
annotation-processor, Kotlin, Maven, or Gradle semantics. Hosts requiring those
facts defer until a framework- or build-aware contract is justified by a real
project. The runner stays family-local and uses no repository Python runtime,
language server, or third-party JAR.

### Installed Java proposal command

Run this from the host root after the router exposes the on-demand skill. Both
`java` and `javac` must resolve from `PATH`; source-file mode executes the copied
runner directly.

<!-- installed-command:java-proposal:start -->
```bash
PROPOSE_TARGET="${PROPOSE_TARGET:-src/main/java/example/legacy}"
PROPOSE_NAME="${PROPOSE_NAME:-java-legacy}"
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
if ! command -v java >/dev/null 2>&1 || ! command -v javac >/dev/null 2>&1; then
  printf '%s\n' '{"status":"unsupported","failure_kind":"jdk_tool_missing","minimum_jdk":17}'
  exit 0
fi
java "${SKILL_ROOT}/scripts/propose_java.java" \
  --target "${PROPOSE_TARGET}" \
  --project-root "$(pwd)" \
  --minimum-jdk 17 \
  --candidates 2 \
  --inspection "reports/propose-boundary/${PROPOSE_NAME}/inspection.json" \
  --proposal "reports/propose-boundary/${PROPOSE_NAME}/proposal.md"
```
<!-- installed-command:java-proposal:end -->

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
every candidate seam against the full criterion set and returns the top N plus
every candidate tied at the cutoff. `candidate_selection` records the requested,
eligible, and returned counts, cutoff score, whether ties expanded the result,
and every lower-scored omitted candidate. Returned tie identities and scores
remain in `candidate_seams`, so a limit never silently hides a cutoff-equivalent
seam. The human picks one (or none) before hand-off.

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
  top N candidate boundary cuts plus every seam tied at the cutoff.
- `candidate_selection` — `{requested, eligible, returned, cutoff_score,
  ties_included, omitted_count, omitted}`. Each omitted row names its
  `cluster_id` and score.
- `defer_signals` — guardrail trips (`target_below_threshold`,
  `single_cluster_no_seam`, `scratch_code`).

Stage 2 — **scout callers (optional).** For each `proposed_public_api`
symbol in every returned candidate seam, the orchestrator dispatches a cheap
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
**Candidate seams:** requested <N>; returned <R> of <C> eligible;
cutoff <S>; ties included: yes | no; omitted <O>

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

(Repeat this section for every row in `candidate_seams`, including ties that
expanded the result beyond requested N.)

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
