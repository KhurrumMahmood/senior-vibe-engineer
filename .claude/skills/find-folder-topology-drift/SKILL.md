---
name: find-folder-topology-drift
description: Detect drift on the folder-topology surface — flat folders with N+ same-prefix sibling files (promote), tests-by-prefix populations that should live under a tests/ subfolder, URL-prefix views not grouped under a matching folder, same-domain helper sprawl at root level, and folder packages whose source-module count fell below the ≥3 threshold (demote). SUSPECT skill governing the placement convention defined in ADR 0006 (folder-organization). The convention is bidirectional — folders earn packaging at ≥3 siblings and lose it below ≥3.
argument-hint: "[--root PATH --min-cluster-size 3 --exclude PATTERN]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Auditing a Python package's directory layout against ADR 0006's
  bidirectional ≥3-sibling threshold. Catches in the **promote**
  direction: same-prefix sibling sprawl (e.g. `views/site_config_*.py`),
  `tests_*.py` populations that should be folders, URL-prefix views not
  grouped under a matching `views/<prefix>/` folder, and same-domain
  helper modules at root level. Catches in the **demote** direction
  (Rule 5): folder packages whose source-module count has fallen below
  ≥3 because files merged, deleted, or moved out — packaging is
  earned, not preserved. Pairs with `/propose-folder-reorganization`
  for the per-cluster proposal and `/refactor-subsystem` for the
  per-PR migration.
not_for: |
  File-level "this module does too many things" (use /find-omnibus —
  that smell is intra-file, this one is intra-folder). Cross-layer
  workflow drift (use /find-route-sprawl, /find-workflow-duplication,
  /find-frontend-contract-drift). Authoring or amending the folder-
  organization ADR itself (use /decide). Acting on findings — that
  goes to /propose-folder-reorganization for the per-cluster proposal,
  then /refactor-subsystem (decomposition mode) for the migration.
language: python
framework: any
---

# /find-folder-topology-drift

You are the orchestrator for a SUSPECT skill that audits a Python
package's directory layout against ADR 0006's folder-grouping
convention.

## How success is judged

- The run is graded only by artifacts: the pasted detector/reporter
  command output plus the written `detections.jsonl`, `report.md`, and
  `findings.json` files. Do not claim a scan ran without those artifacts.
- The scan verdict is declared as one of `clean`, `drift-found`, or
  `scan-blocked`. `drift-found` means at least one emitted finding is
  worth human triage; it does not authorize file moves.
- The reported target matches the detector invocation. If `--root` is
  omitted, describe the target as the default scope universe, not a
  baked application folder. If `--root PATH` is supplied, echo that path
  in the reporter's `--target` value.
- The skill remains read-only: findings route to the next skill; this
  skill never edits, moves, stages, or commits production files.

## Scope

- **Default scan universe:** no `--root`. The detector loads the
  per-skill scope/ignore descriptors when a host repo provides them;
  otherwise it scans the repository tree after the built-in exclusions.
  Override with `--root PATH` to narrow the scan to one subtree.
<!-- spec:project-structure-redesign-phase-2::IM-16 -->
- **Default min cluster size:** 3 — the same threshold ADR 0006 sets
  for "this is a pattern, not a coincidence."
- **Default exclusions:** `__pycache__/`, `migrations/`, `data/`,
  `.venv/`, `node_modules/`, `staticfiles/`. Override with
  `--exclude PATTERN` (additive).
- **Output:** `reports/find-folder-topology-drift/<scan-id>/`.
- **Read-only.** No file moves, no edits.
- **Detector vs lint — when to add a band.** Per-file violations
  (decorator shape, decorator string, single-file AST pattern) belong
  in a pre-commit lint under `scripts/lint/` — they fire at commit
  time on the staged diff. Cross-file or path-shape violations
  (filename-vs-parent-folder mirroring, sibling-cluster threshold,
  duplicated subtree) belong in a detector band here — they fire
  at audit time over the whole tree. Some invariants want both: the
  lint catches commit-time regressions, the band catches what slips
  past (e.g. via direct-to-main pushes, branch merges that bypass
  hooks, or files older than the rule). When in doubt, ask whether
  the rule needs *neighbor context* to fire — if yes, it's a band.

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/find-folder-topology-drift/$SCAN_ID"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-folder-topology-drift/scripts/detect.py \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-folder-topology-drift/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --target "default scope"
ln -sfn "$SCAN_ID" reports/find-folder-topology-drift/latest
```

When narrowing the scan, forward the same target label to the report:

```bash
.venv/bin/python .claude/skills/find-folder-topology-drift/scripts/detect.py \
  --root .claude/skills \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-folder-topology-drift/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --target ".claude/skills"
```

## Findings

The detector emits one record per finding into a JSONL file. Bands:

- **`flat_prefix_cluster`** — A directory contains N≥`min-cluster-size`
  Python modules sharing the same `<prefix>_` token, where the prefix
  names a domain. Recommendation: collapse the cluster into a
  directory package per ADR 0006 Rule 2; the EXPLAIN skill writes
  the migration table.

- **`tests_by_prefix`** — A directory contains N≥`min-cluster-size`
  files matching `tests_*.py` and has no `tests/` subfolder.
  Recommendation: introduce `tests/` and migrate tests alongside the
  code they exercise per ADR 0006 Rule 1. Tests-prefix-at-root is the
  user-visible symptom that motivated this skill — expect it to fire
  loudly on first run.

- **`sparse_folder_package`** — A folder package (has `__init__.py`)
  whose top-level source-module count is below `min-cluster-size`.
  Implements ADR 0006 Rule 5: the convention is bidirectional, and a
  folder loses its packaging when the cluster that earned it
  dissolves. Source modules exclude `__init__.py`, `conftest.py`,
  any `tests_*.py` / `test_*.py` files, and entries inside the
  `tests/` subfolder; framework-mandated folders
  (`migrations/`, `management/`, `commands/`, `templatetags/`,
  `fixtures/`, `tests/`) are exempted. Recommendation: demote the
  folder — survivors migrate up to the parent as sibling files —
  unless an in-flight spec is about to grow it back above threshold,
  in which case the proposal records `defer_in_flight`.

- **`route_folder_misalignment`** *(Stage 2 — deferred)* — A URL
  prefix resolves to >=3 view modules that are not grouped under a
  matching folder under the route-owned views tree. The detector
  currently emits a placeholder note when the routes file is parseable
  but the band is not yet computed; turn this on when the
  Stage 1 bands have drained their queue.

- **`same_domain_helper_sprawl`** *(Stage 2 — deferred)* — Root-level
  modules naming the same domain (e.g. seven `*scraper*.py` files at a
  package root). Stage 1 catches the obvious form via
  `flat_prefix_cluster` whenever they share a prefix; the harder case
  (mixed prefixes, shared domain) is deferred until Stage 1 is drained.

Each Stage 1 record carries `pattern`, `file`, `lineno`, `summary`,
and `recommendation` keys so the shared `render_simple_report` helper
in `.claude/skills/_common/product_topology.py` can render it.

## Why these findings cost anything

Read `_common/structural-design-principles.md` for the underlying
rule this skill operates on. Short form: framework and language
norms are a *floor* (constraints you can't break without things
breaking literally); above that floor, the design objective is
*intuitiveness for a human skimming a directory listing*. Each band
this skill emits is a layout that fails one of the intuitiveness
tests there:

- `flat_prefix_cluster` — fails the **skim test** and **cluster
  test**: the names show a cluster, but the layout treats every
  member as an unrelated singleton.
- `tests_by_prefix` — fails the **find test**: a reader looking for
  the tests for module X has to grep `tests_X*.py` instead of
  navigating to `tests/test_X.py`.
- `sparse_folder_package` — fails the **skim test** in the inverse
  direction: a folder name promises a cluster, but the contents are
  one or two files that would read more directly as flat siblings.

The bands stay neutral on framework norms — exemptions
(`framework_folder_names`, the scratch-code escape valve) are how
the floor is honored.

## Calibration

- **`--min-cluster-size`** defaults to 3 to match ADR 0006's
  threshold. Lowering to 2 floods the report with noise — pairs are
  not yet a pattern. Raising to 4+ misses real clusters that the
  proposal step should still see; if the report is too long, exclude
  scratch-code paths instead.
- **`--exclude PATTERN`** is glob-style and additive on top of the
  default exclusions. Use it to skip scratch-code directories per
  project memory (e.g. `--exclude 'scratch/*'`).
- **Singletons are not findings.** A 400-LOC cohesive module with no
  prefix siblings is honored by ADR 0006's "singletons stay flat"
  guardrail — it never appears in this report.

## Reading the report

`report.md` groups findings by band; each finding names one
directory + the cluster summary + a recommendation pointing at the
EXPLAIN skill. The findings are independent — there is no priority
order between bands; pick the largest cluster first by default
(highest navigation cost relief per migration PR).

## Next skills

- **`/propose-folder-reorganization <cluster-id>`** — turns a
  finding into the per-cluster proposal (current → proposed tree,
  file-move table, import-impact summary, characterization-test
  matrix, stop condition).
- **`/refactor-subsystem`** in decomposition mode — executes the
  proposal under ADR 0002's spec-first, two-commit discipline. One
  cluster per PR.
- **`/decide`** if a finding reveals a tradeoff the ADR doesn't yet
  cover (e.g. "we keep accepting `flat_prefix_cluster` for framework
  command modules because that is the framework convention — document
  the exemption formally").
- **`/prevent-regression`** *(Stage 2 — deferred)* if the SUSPECT
  queue drains and folder-topology drift recurs often enough to
  justify a pre-commit lint.

## Notes for the orchestrator

- This is a Stage 1 skeleton. Bands `route_folder_misalignment` and
  `same_domain_helper_sprawl` are not yet detected — the obvious
  same-prefix case of the latter falls under `flat_prefix_cluster`,
  and route alignment requires URL parsing that is out of scope for
  the first iteration.
- The detector recurses into subdirectories. A folder with a real
  package layout is *not* flagged for its internal structure — only
  directly-flat folders with prefix clusters are.
- Re-runs are idempotent. The detector reads the filesystem only;
  there is no cached state.
- ADR 0006's "custom-job and scratch code" exemption (project memory:
  `project_core_vs_scratch_code.md`) is enforced by the user via
  `--exclude` rather than auto-detected. The proposal step
  (`/propose-folder-reorganization`) re-reads the exemption and may
  recommend `defer_scratch_code` for findings that survived the scan.

## Replay check

After editing this skill or its detector contract, run the cheap replay:

```bash
.venv/bin/python .claude/skills/find-folder-topology-drift/scripts/detect.py --help
SCAN_ID="scan-replay"
REPORT_DIR="/tmp/find-folder-topology-drift-${SCAN_ID}"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-folder-topology-drift/scripts/detect.py \
  --root .claude/skills/find-folder-topology-drift \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-folder-topology-drift/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --target ".claude/skills/find-folder-topology-drift"
```

Paste the command output when using it as repair evidence. The replay
does not prove the scan is clean; it proves the documented argparse and
reporter contract execute.

## When things go sideways

| Symptom | Action |
|---|---|
| `--root PATH` is outside `--project-root` | Treat the run as invalid for that target, state the mismatch, and re-run with a repo-relative root; do not report the fallback whole-repo scan as if it honored the root. |
| `detections.jsonl` is missing or empty because the command did not run | Mark the scan `scan-blocked`; paste the failing command output instead of summarizing findings. |
| Reporter fails after detector success | Keep `detections.jsonl` as the artifact truth, mark the run `scan-blocked`, and paste the reporter failure; do not hand-write `report.md`. |
| Stage-2 deferred bands look relevant | Say they are not detected yet; route the specific design question to `/decide` or a follow-up detector change rather than fabricating findings. |
| A finding looks like framework convention rather than drift | Keep it in the report, label it an exemption candidate, and route to `/decide` only if the convention should become durable policy. |

## Repository layout

```
.claude/skills/find-folder-topology-drift/
├── SKILL.md          # this file — orchestrator
└── scripts/
    ├── detect.py     # Stage 1 bands (stdlib only)
    └── report.py     # markdown + JSON renderer (uses _common helpers)
```
