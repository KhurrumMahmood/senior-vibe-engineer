---
name: propose-folder-reorganization
description: Turn a confirmed Python, Go, Java 17, Kotlin/JVM, C#, TypeScript, checked-JavaScript, PHP, Ruby, bounded Rust, or bounded Dart folder-topology cluster into a per-cluster reorganization proposal. Typed-source v1 resolves import impact, records compatibility and convention constraints, and emits a read-only move/test plan. No file moves or edits; hand off only after human review.
argument-hint: "<folder-topology:ID or parent::prefix>"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: explain
best_for: |
  A Java 17 flat-prefix cluster needing a compiler-resolved subpackage move plan.
  A TypeScript or checked-JavaScript flat-prefix folder cluster needing resolved import impact,
  a target tree, barrel/subpath compatibility, and native verification plan.
  A confirmed folder-topology drift finding ready for a per-cluster
  reorganization proposal — produces the current → proposed tree,
  file-move table, import-impact summary, characterization-test
  matrix, and the rule-of-thumb call (`tests_by_prefix` opportunistic
  vs `flat_prefix_cluster` per-PR). Read-only. Decided in: ADR 0006
  (folder-organization).
not_for: |
  Detection (use /find-folder-topology-drift first). File-level
  decomposition where the smell is intra-file, not intra-folder
  (use /find-omnibus). Refactor execution (use /refactor-subsystem in
  decomposition mode). Authoring or amending the folder-organization
  ADR itself (use /decide). Collapsing scratch / custom-job code (project memory:
  project_core_vs_scratch_code.md) — the proposal still runs but
  recommends `defer_scratch_code` instead of a refactor.
language: any
framework: any
scans: [python, go, java, kotlin, csharp, typescript, javascript, php, ruby, rust, dart, c, cpp]
---

# /propose-folder-reorganization

## C# 14 / .NET 10 accepted branch

Use `scripts/propose_csharp.py` only for one exact accepted three-or-more-file
direct-sibling C# prefix cluster, an explicit project convention, a current
complete integrated C# subsystem map and Roslyn fact pack, and a
content-addressed `csharp-structure-acceptance-v1` candidate/proposal verdict.
Keep copied `_csharp`, `_csharp-semantic`, and `map-subsystem` libraries beside
the selected skill; run the script with `--help` for exact paths and the pinned
`--dotnet` argument. It consumes the final topology/map artifacts and never
redetects the cluster.

The branch emits only `proposal.md`, `evidence.json`, and `scope.json`, with
exact file moves, unchanged namespace/type/assembly identity, resolved caller
and reference impact, and exact manifest/project compile-item after-states. It
proves the current tree and an independently applied disposable after-tree with
native build/test/smoke. Filename grouping does not prove ownership,
reflection/resource paths, framework registration, generated/vendor or
external consumers, conditional variants, behavioral equivalence, ABI/release
compatibility, or mutation safety.

## Kotlin/JVM 2.4.10 accepted branch

Trigger this branch only for one accepted three-or-more-file Kotlin topology
cluster with a current complete Kotlin map, explicit project convention, and
content-addressed human acceptance. Read `../_kotlin-semantic/GUIDE.md`, keep
`_kotlin-semantic` beside the selected skill, and run
`scripts/propose_kotlin.py` with `--topology`, `--map-evidence`, `--acceptance`,
`--output-dir`, absolute Kotlin/JVM 2.4.10 `--kotlinc`, and absolute JDK 17
`--java` paths; run `--help` for the exact CLI.

The branch emits only `proposal.md`, `evidence.json`, and `scope.json`, then
proves the exact same-package manifest move on the current tree and a
disposable after-tree. Filename grouping and K1 direct facts remain
insufficient for package ownership, override/runtime dispatch,
reflection/callable references, delegation, generated/KAPT/KSP or plugin
inputs, Gradle/source-set variants, Java/external callers, behavior, JVM ABI,
mutation, or release authority.

## C++20 branch

Use `scripts/propose_cpp.py` with accepted topology evidence, a current complete
C++20 map, an explicit project convention, and hash-bound human acceptance;
run it with `--help` for the exact CLI. It emits a read-only plan for one
compiler-owned private prefix cluster with exact qualified signatures,
overloads, callers, headers, Make edits, and after-tree census. Filename
grouping proves no ODR/ABI, specialization, dispatch, external variant, or
mutation safety.

## C17 branch

Use `scripts/propose_c.py` with an accepted prefix cluster, explicit project
convention, current complete C map, and hash-bound human acceptance; run the
script with `--help` for the exact CLI. It emits a read-only ready, keep-flat,
or no-convention outcome. Filename grouping proves no ownership, alternate-
variant or external-consumer completeness, ABI, or mutation safety.

## PHP and Ruby

For PHP, read `_php-proposal/GUIDE.md`; for Ruby, read
`_ruby-semantic/PROPOSAL-GUIDE.md`. These branches consume accepted clusters
and conventions, emit read-only move plans, and never move source.

## Dart v1

Dart v1 consumes one accepted D1 cluster, accepted D4 import impact, and an
explicit human convention judgment. It accounts for every member and edge,
preserves the public barrel, and verifies the exact after-tree only in a
disposable copy. Cohesive, convention-free, package-URI-uncertain, or stale
evidence defers or refuses without moving source.

```bash
SKILL_ROOT=".agents/skills/on-demand/propose-folder-reorganization"
python3 "${SKILL_ROOT}/scripts/propose_dart.py" \
  --project-root "$PWD" --evidence-dir reports/dart-folder-evidence \
  --acceptance reports/dart-folder-evidence/acceptance.json \
  --inspection "$PWD/reports/propose-folder-reorganization/dart/inspection.json" \
  --proposal "$PWD/reports/propose-folder-reorganization/dart/proposal.md"
```

## Rust v1

Read `knowledge/rust-v1.md`. Supply one human-reviewed split/cohesive judgment
and optional project convention. The adapter emits an exact read-only Cargo
module move plan and native obligations at
`ready_for_human_review/review_folder_plan`; it never moves files. The copied
canonical producer is
`.claude/skills/_common/scripts/rust_proposal_evidence.py`; a copied projection
places the same bytes beside the adapter under the alias
`rust_project_evidence.py`.

```bash
SKILL_ROOT=".agents/skills/on-demand/propose-folder-reorganization"
python3 "${SKILL_ROOT}/scripts/propose_rust.py" \
  --project-root "$PWD" --parent crates/example/src --prefix billing \
  --cluster-judgment split \
  --inspection "$PWD/reports/propose-folder-reorganization/rust/inspection.json" \
  --proposal "$PWD/reports/propose-folder-reorganization/rust/proposal.md"
```

You are the **orchestrator** for turning a folder-topology cluster
into a reorganization proposal. `/find-folder-topology-drift` already
flagged the cluster; your job is to read the cluster files, gather
the import graph, and emit a proposal the human reviews before
handing off to `/refactor-subsystem` (decomposition mode).

You do NOT move files, rename modules, or touch imports in this
skill. The only artifact you produce is
`reports/propose-folder-reorganization/<target-slug>/proposal.md`
plus its supporting `inspection.json`.

## How success is judged

- `proposal.md` carries the current → proposed tree, a file-move table
  grounded in `inspection.json`, the full import-impact list (every
  breaking import line with its after-rename target), and a
  characterization-test matrix as the stop condition.
- ADR 0006 thresholds are honored: ≥3 real siblings or the proposal
  says `defer_below_threshold`; one cluster per run; `defer_signals`
  from the inspection are surfaced, never suppressed.
- Zero file moves, zero edits — handoff is `/refactor-subsystem` in
  decomposition mode after human review.
Write toward these gates from Stage 0.

## Core beliefs

0. **Framework norms are a floor; intuitiveness is the goal above it.**
   Read `_common/structural-design-principles.md` before sizing a
   proposal. Every proposal evaluates the cluster against both layers:
   what framework norms constrain (Django app boundary, Python package
   semantics, test-runner discovery — the floor), and what
   intuitiveness gain motivates the reorganization (skim test, find
   test, cluster test — above the floor). Frame the proposal's
   "Why this reorganization" section in those terms.

1. **The cluster IS the unit of work.** ADR 0006 says one cluster per
   PR. The proposal is sized to one cluster, not "all of `core/services`."
   If a parent has multiple clusters (e.g. `core/services/` has
   `collection_*`, `extraction_*`, `field_*`, etc.), each gets its own
   `/propose-folder-reorganization` run.
2. **Import impact dominates the migration cost.** Whether the cluster
   has 5 files or 50 doesn't matter; what matters is how many call
   sites import the cluster's symbols. The proposal enumerates every
   import line that breaks — by absolute path, with the after-rename
   target — so `/refactor-subsystem` can run a deterministic find/replace
   in commit 1 (the move) without surprises.
3. **Tests migrate alongside their subjects, not in bulk.** ADR 0006
   Rule 1 forbids a single bulk-rename PR for `tests_*.py` → `tests/`.
   When the cluster has matching `tests_<prefix>_<x>.py` files at root,
   the proposal pairs each test with its target subject and migrates
   them in the same PR — but the *unrelated* `tests_*.py` files at root
   stay where they are until *their* subject moves.
4. **Singletons stay flat.** If the inspection turns up a "cluster" that
   is really one substantial module + one helper that happens to share
   a prefix, the proposal recommends `defer_below_threshold` rather
   than packaging two files into a folder. The threshold is ≥3 *real*
   siblings — see ADR 0006's "When NOT to split" guardrails.
5. **Behavior preservation is the migration's stop condition.** The
   proposal names a characterization-test matrix that
   `/refactor-subsystem` must pin BEFORE the move. Same discipline as
   ADR 0002's two-commit refactor: capture current behavior, migrate,
   confirm unchanged. Any latent bug found during the move is its own
   commit, never bundled with the rename.

## Scope

- **Project root:** the working directory.
- **Python:** `.venv/bin/python` for the helper script (it routes
  Python parsing through the shared per-language adapter registry
  (ADR 0032; Python-only here) and walks the project to build the
  import graph; stdlib-only — no Django imports needed).
- **Output:** `reports/propose-folder-reorganization/<target-slug>/`.
  Never touches any other file.
- **Read-only.** No file moves, no edits, no Edit tool. The
  orchestrator's `allowed-tools` list intentionally excludes Edit.

## Go v1
Read `knowledge/go-v1.md`; its copied-closure command requires an explicit project convention, while language-safety blockers override that permission.

## Java 17 v1
Read `knowledge/java-v1.md`; its copied-closure command requires explicit
cluster and subpackage-convention judgments, then emits a compiler-resolved,
current-source-root-only plan. It never loads Maven, Gradle, or JARs.

## TypeScript / TSX and checked-JavaScript v1 — one resolved cluster proposal

The Python workflow below remains unchanged. This additive typed-source branch
is for one human-confirmed flat file cluster only; it does not infer a Node,
React, Next, ORM, or test-framework convention.

### Supported invariant

Given a direct parent directory, a prefix, a named project-local `tsconfig`,
and the host's own installed `typescript` package, produce a read-only
proposal for three or more eligible `prefix-*.ts[x]` / `prefix_*.ts[x]` or
`prefix-*.js[x]` / `prefix_*.js[x]` (including `.mjs` and `.cjs`)
siblings. The final proposal and its JSON inspection contain:

- every selected source file and its destination beneath
  `<parent>/<prefix>/`;
- every resolved static `import`, `export … from`, and `import = require`
  line that points at a selected file — including cluster-internal imports,
  direct relative consumers, `paths` alias consumers, and existing barrel
  re-exports — with the exact after-move specifier;
- an explicit compatibility decision: preserve existing `index.ts[x]`
  barrels, add a new domain barrel, and migrate every resolved direct subpath
  importer rather than retain legacy file shims;
- a characterization-test matrix and the host-native `npm run typecheck`
  proof required before and after the behavior-preserving move.

The user must pass `--cluster-judgment split` after confirming that this
specific cluster harms navigation. Pass `--cluster-judgment cohesive` when
the files are deliberately cohesive; it writes an explicit
`defer_cohesive_cluster` proposal rather than pretending lexical naming is a
refactor verdict.

This v1 does not execute the move, discover test ownership, resolve dynamic
or runtime module loading, infer framework conventions, preserve unlisted
external package subpaths, or claim a TypeScript or JavaScript framework migration.

Checked JavaScript passes `--language javascript` with a named `jsconfig.json`
or `tsconfig.json` that sets `allowJs` and `checkJs`. It accepts `.js`, `.jsx`,
`.mjs`, and `.cjs`, including a JS cluster in a mixed JS/TS root. A selected
file omitted from that config is an explicit `partial`/`defer_partial_config`
artifact, not a move authority.

### TypeScript guardrails and statuses

All exclusions are project-root-relative, including direct invocation of an
excluded directory. Test/spec/fixture, generated, vendor, dependency, build,
coverage, report, declaration, minified, bundle, and existing `index.ts[x]`
source are excluded from the candidate cluster. Existing index files remain
eligible **importers** so their re-export rewrites appear in the impact table.

- Fewer than three selected files writes `defer_below_threshold`.
- A `scratch`, `sandbox`, `experiments`, or equivalent path writes
  `defer_scratch_code`.
- An explicitly cohesive cluster writes `defer_cohesive_cluster`.
- An excluded direct parent writes `defer_excluded_target`.
- An unresolved or symlink-blocked static import **inside a selected cluster
  file** writes a `blocked` `defer_unresolved_imports` proposal. Resolve it
  and re-run; do not treat a partial table as move authority.
- A missing parent, a logical path outside the host, any target/tsconfig or
  artifact path traversing a symlink, invalid syntax/configuration, or a
  missing project-local TypeScript Compiler API exits 2 with no false-clean
  proposal.

Artifact paths must be under
`reports/propose-folder-reorganization/`; existing or ancestor symlinks are
rejected before anything is written. Directory symlinks are never followed.

### Installed TypeScript commands

Run these from the target TypeScript host root. The stock Codex installer
copies only this selected skill to `.agents/skills/`; the runtime command uses
the host's Node and project-local `typescript`, never this repository's
scripts, `_common`, virtual environment, or another installed skill.

<!-- installed-command:stock-install:start -->
```bash
: "${PROPOSE_FOLDER_REORGANIZATION_SOURCE:?Set this to the pinned skill source/ref}"
npx --yes skills@1.5.19 add "${PROPOSE_FOLDER_REORGANIZATION_SOURCE}" \
  --skill propose-folder-reorganization --agent codex --copy -y
```
<!-- installed-command:stock-install:end -->

<!-- installed-command:typescript-proposal:start -->
```bash
PFR_PARENT="${PFR_PARENT:-src}"
PFR_PREFIX="${PFR_PREFIX:-billing}"
PFR_CLUSTER_JUDGMENT="${PFR_CLUSTER_JUDGMENT:-split}"
PFR_LANGUAGE="${PFR_LANGUAGE:-typescript}" # typescript | javascript
PFR_TSCONFIG="${PFR_TSCONFIG:-tsconfig.json}"
PFR_NAME="${PFR_NAME:-${PFR_PARENT//\//-}__${PFR_PREFIX}}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/propose-folder-reorganization" \
  ".claude/skills/propose-folder-reorganization"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "propose-folder-reorganization is not installed in .agents/skills or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/propose_typescript.mjs" \
  --parent "${PFR_PARENT}" \
  --prefix "${PFR_PREFIX}" \
  --cluster-judgment "${PFR_CLUSTER_JUDGMENT}" \
  --project-root "$(pwd)" \
  --language "${PFR_LANGUAGE}" \
  --tsconfig "${PFR_TSCONFIG}" \
  --proposal "reports/propose-folder-reorganization/${PFR_NAME}/proposal.md" \
  --inspection "reports/propose-folder-reorganization/${PFR_NAME}/inspection.json"
```
<!-- installed-command:typescript-proposal:end -->

Read both final artifacts before planning the refactor. `inspection.json` is
the machine-checkable truth; `proposal.md` is the human handoff. For a ready
proposal, run `npm run typecheck` before the move, apply the exact move and
impact rows in a disposable branch, then run it again with the
characterization tests. A normal TypeScript type error is native verification
evidence, not something this read-only proposer repairs.

## Argument parsing

Two forms.

### Form A — finding-ID

```
/propose-folder-reorganization <scan-id>:<finding-index>
```

e.g. `/propose-folder-reorganization scan-20260508-000715:18` reads
`reports/find-folder-topology-drift/<scan-id>/findings.json`,
selects the finding at index 18, and derives the cluster's parent
directory + prefix from it.

### Form B — explicit target

```
/propose-folder-reorganization <parent-path>::<prefix>
```

e.g. `/propose-folder-reorganization core/views::site_config`. The
`parent-path` is the folder that contains the cluster; `prefix` is
the leading underscore-prefix token (without the trailing `_`).
Special prefix `tests` triggers the `tests_by_prefix` band — same
parent-path argument, prefix `tests`.

If the user passes a target that isn't a real directory or has
fewer than 3 sibling files matching the prefix, the orchestrator
stops, logs `target_not_found` or `cluster_below_threshold` to the
proposal, and returns.

## Pipeline

Stage 0 — **resolve target.** Parse the argument. If finding-ID,
read `findings.json` from the named scan and pull `file` + the
prefix the finding's recommendation cites. If explicit target, take
parent-path + prefix as given. Compute the target slug:
`<parent-path with / → -><__><prefix>`, e.g.
`core-views__site_config`.

Stage 1 — **inspect.** Run the helper:

```bash
.venv/bin/python .claude/skills/propose-folder-reorganization/scripts/inspect.py \
  --parent <parent-path> \
  --prefix <prefix> \
  --project-root . \
  --output reports/propose-folder-reorganization/<target-slug>/inspection.json
```

The helper writes `inspection.json` with:

- `cluster_files` — list of `{path, line_count, public_symbols}` for
  every file in the cluster (one record per file).
- `import_impact` — list of `{importer, statement, lineno}` for
  every import line in the project that resolves to a cluster
  member, with the after-rename target precomputed.
- `matched_tests` — list of `tests_<prefix>_*.py` files at the same
  parent (or at the project root for `core/`) that exercise cluster
  members.
- `singletons_at_parent` — count of sibling files at the parent
  that do NOT match the cluster prefix and are NOT in noise tokens.
  This is informational — the proposal cites it when judging
  whether the cluster collapse is the right move or whether the
  parent itself needs a higher-level reorg.
- `defer_signals` — list of any guardrail trips (cluster size <3,
  parent matches a known scratch-code path, prefix matches a
  framework convention like `core/management/commands/`).

Stage 2 — **synthesize.** The orchestrator reads `inspection.json`
and writes `proposal.md` per the template below. This is judgment
work, not mechanical — Claude does it, not a script.

Stage 3 — **stop or hand off.** If `defer_signals` are non-empty,
the proposal records `recommendation: defer_<reason>` in the front
matter. Otherwise the proposal recommends `recommendation: refactor`
and names `/refactor-subsystem --target <target-slug>` as the next
step.

## Proposal template

The proposal markdown has these sections, in order:

```markdown
# Folder reorganization proposal — <parent-path>::<prefix>

> **Detected by:** `/find-folder-topology-drift` <finding-ref>
> **Decided in:** [ADR 0006](../../../ai-docs/decisions/0006-folder-organization.md)
> **Executed by:** `/refactor-subsystem` (decomposition mode, ADR 0002)

**Recommendation:** refactor | defer_<reason>
**Cluster size:** <N> files | <total LOC> lines
**Import impact:** <K> import lines across <M> files
**Matched tests:** <T> `tests_<prefix>_*.py` files

## Current tree

\`\`\`
<parent-path>/
├── <file 1>             # <line count>
├── <file 2>             # <line count>
├── ...
└── <noise siblings, if relevant for context>
\`\`\`

## Proposed tree

\`\`\`
<parent-path>/<prefix>/
├── __init__.py          # re-exports for compatibility
├── <file 1 renamed>     # <prefix>_X.py → X.py
├── <file 2 renamed>
├── ...
└── tests/
    ├── __init__.py
    └── test_*.py        # migrated from tests_<prefix>_*.py
\`\`\`

## File-move table

| Current path | New path | Public symbols |
|---|---|---|
| <path> | <new path> | `func_a`, `Class B`, `CONSTANT_C` |

(One row per cluster file. Public symbols come from `inspection.json`.
The `__init__.py` re-export list is the union of every row's
"Public symbols" column.)

## Import-impact summary

| Importer | Current statement | New statement |
|---|---|---|
| <importer-path>:<lineno> | `from <parent>.<old> import X` | `from <parent>.<prefix> import X` |

(One row per import line. If the cluster is consumed only via
`__init__.py` re-exports, this collapses to a single
`from <parent> import <prefix>` form and the table is short. If
callers reach into module internals, every line is listed.)

## Characterization-test matrix

| Existing test | Subject under test | Action |
|---|---|---|
| `tests_<prefix>_X.py` | `<parent>/<old>.py` | Migrate to `<parent>/<prefix>/tests/test_X.py` in the same PR |
| (no test) | `<parent>/<old>.py::func_a` | Pin behavior with a new test BEFORE the move |

(Every cluster file gets a row. Files with no existing test get a
pin-test recommendation; files with a matching `tests_<prefix>_*.py`
file get a migration-pair row. `/refactor-subsystem` enforces this
matrix in Phase 2.1.)

## Migration sequencing

1. **Pre-move** — write any pin-tests named in the matrix. They run
   green against the current layout.
2. **Commit 1: behaviour-preserving move.** Create
   `<parent>/<prefix>/`, `git mv` each cluster file, update its
   public-symbol re-exports in `__init__.py`, run the
   import-impact rename across the project. Tests run green.
3. **Commit 2: clean-up.** Remove the legacy shim file (if one
   exists at `<parent>/<old-name>.py`), drop dead `__init__.py`
   re-exports if no caller needs them. Tests run green.
4. **Tests pair** — `tests_<prefix>_X.py` moves to
   `<parent>/<prefix>/tests/test_X.py` in commit 1, alongside its
   subject. Unrelated `tests_*.py` files at root do NOT move.

## Stop condition

The cluster has collapsed into `<parent>/<prefix>/` and:

- Every cluster file is now under the new folder (or merged into a
  sibling within it).
- Every importer in `import_impact` resolves through
  `<parent>/<prefix>` (directly or via re-export).
- Every test in `matched_tests` lives under
  `<parent>/<prefix>/tests/`.
- The full test suite is green; behaviour is unchanged.

If `defer_signals` is non-empty, the stop condition instead is:

- The deferral reason is recorded in this proposal.
- The cluster is NOT in the active backlog at
  `reports/find-folder-topology-drift/latest`. (It will reappear on
  the next scan unless the deferral is also recorded as an
  exemption — see ADR 0006's "custom-job and scratch code"
  guardrail.)

## Notes (orchestrator judgment)

A short prose section. Use it for:

- The "why this prefix is a coherent domain" sentence (or the
  counter-argument: "prefix is coincidental").
- Any sub-cluster the orchestrator notices (e.g. `site_*` mixes
  `site_config_*`, `site_ai_sidecar_*`, and `site_checklist`;
  the proposal may recommend running this skill three times rather
  than collapsing all nine into `site/`).
- Singletons in the cluster that should stay flat — name them and
  why.
- Anything the file-move table can't carry on its own.
```

## Defer signals

The helper sets `defer_signals` when any of these trip. The
orchestrator translates them to `recommendation: defer_<reason>`:

- `cluster_below_threshold` — fewer than 3 cluster files (ADR 0006
  Rule 2's threshold). Proposal recommends `defer_below_threshold`.
- `scratch_code` — the parent path matches a known scratch-code
  prefix (project memory: `project_core_vs_scratch_code.md`). Today
  this means anything under `core/management/commands/_experiments/`
  or files known to be one-off jobs. Proposal recommends
  `defer_scratch_code`.
- `framework_convention` — the parent is `core/management/commands/`
  and Django's runner discovers commands by file name. Re-grouping
  into subfolders is possible but breaks the
  `manage.py <command_name>` convention. Proposal recommends
  `defer_framework_convention` and points at ADR 0006's open
  question on this.

## Calibration

- **Cluster threshold** lives in `/find-folder-topology-drift`
  (`--min-cluster-size 3`). This skill takes the threshold from the
  source finding; if the helper finds fewer than that on its own
  walk (e.g. someone deleted a file between scan and proposal),
  it sets `defer_signals: ["cluster_below_threshold"]` and the
  proposal recommends deferral.
- **Import-graph scope** is the entire project root by default. To
  scope tighter (e.g. ignore tests when computing impact), pass
  `--exclude` flags through to the helper. The default exclusions
  match `/find-folder-topology-drift`.

## Re-runs are idempotent

The helper reads the filesystem only. Re-running with the same
target overwrites `inspection.json` and is safe. The proposal,
because it carries judgment, is NOT auto-overwritten — Claude
inspects the existing proposal first and only rewrites the
sections that changed.

## Repository layout

```
.claude/skills/propose-folder-reorganization/
├── SKILL.md          # this file — orchestrator
└── scripts/
    ├── inspect.py                # Python cluster + import-impact data
    ├── propose_java.py           # JDK gate + artifact-safe launcher
    ├── propose_java.java         # JDK compiler/tree/type proposal
    └── propose_typescript.mjs     # TS/TSX resolved proposal (host Compiler API)
```

## Next skills

Use `/refactor-subsystem` for an approved one-cluster move, `/decide` for an
unsettled convention, and `/find-folder-topology-drift` to verify it afterward.
