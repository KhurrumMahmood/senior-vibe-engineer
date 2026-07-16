---
name: propose-folder-reorganization
description: Turn a confirmed folder-topology drift finding into a per-cluster reorganization proposal. Consumes a finding from /find-folder-topology-drift (or an explicit target like `core/views::site_config`) and emits reports/propose-folder-reorganization/<target>/proposal.md with the current → proposed tree, file-move table, import-impact summary, characterization-test matrix, and stop condition. Read-only — no file moves, no edits. Hands off to /refactor-subsystem (decomposition mode).
argument-hint: "<folder-topology:ID or parent::prefix>"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: explain
best_for: |
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
  ADR itself (use /decide). Cluster collapse where the cluster is
  scratch / custom-job code (project memory:
  project_core_vs_scratch_code.md) — the proposal still runs but
  recommends `defer_scratch_code` instead of a refactor.
language: python
framework: any
---

# /propose-folder-reorganization

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
   what framework norms constrain (application boundary, language package
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
  import graph; stdlib-only — no host framework imports needed).
- **Output:** `reports/propose-folder-reorganization/<target-slug>/`.
  Never touches any other file.
- **Read-only.** No file moves, no edits, no Edit tool. The
  orchestrator's `allowed-tools` list intentionally excludes Edit.

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
  and the selected framework runner discovers commands by file name.
  Re-grouping into subfolders may break its public command convention.
  Proposal recommends `defer_framework_convention` and points at ADR
  0006's open question on this; the selected binding names the exact
  runner contract.

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
    └── inspect.py    # gathers cluster + import-impact data (stdlib only)
```

## Next skills

- **`/refactor-subsystem`** in decomposition mode — executes the
  proposal under ADR 0002's two-commit discipline. One cluster per
  PR.
- **`/decide`** if the proposal surfaces a tradeoff ADR 0006
  doesn't yet cover (e.g. the `framework_convention` deferral
  becomes a real question that needs a ruling on
  `core/management/commands/`).
- **`/find-folder-topology-drift`** to re-scan after the migration
  lands — the cluster should drop off the next report.
