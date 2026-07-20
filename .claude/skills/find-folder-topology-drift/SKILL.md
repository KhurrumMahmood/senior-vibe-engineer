---
name: find-folder-topology-drift
description: Read-only SUSPECT audit for Python folder-topology drift and narrow, explicit-root JavaScript-family, TypeScript, or Go flat-prefix clusters. Python retains its ADR 0006 promotion and demotion bands; JavaScript and TypeScript report direct source siblings sharing a first `_` or `-` token, while Go uses its valid first `_` token. Use when a source folder is hard to skim because sibling filenames visibly name the same domain.
argument-hint: "[--root PATH] [--javascript-root PATH] [--typescript-root PATH] [--go-root PATH] [--min-cluster-size 3 --exclude PATTERN]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Auditing a Python package against ADR 0006's bidirectional ≥3-sibling
  threshold, or inspecting an explicitly named TypeScript or Go source root for a
  simple same-domain filename cluster such as
  `billing_parser.ts`, `billing-validator.ts`, and `billing-types.ts`.
not_for: |
  Moving files, proving import safety, or deciding that a cluster must become
  a package. TypeScript and Go v1 do not inspect sparse-package demotion, test-folder
  reorganization, Next.js/pages conventions, barrels, module resolution, or
  framework ownership. Use /propose-folder-reorganization only after a human
  confirms a Python finding; a TypeScript reorganization proposal needs its own
  resolved-import contract.
language: any
framework: any
scans: [python, javascript, typescript, go]
---

# /find-folder-topology-drift

Run a read-only directory-layout audit. Treat every finding as a human-triage
candidate, never as authorization to move files.

## How success is judged

- Produce `detections.jsonl`, `report.md`, and `findings.json`; cite their
  paths and the detector/reporter output. Do not claim a scan ran without those
  artifacts.
- Report `clean`, `drift-found`, or `scan-blocked`. `drift-found` is advisory.
- Echo the supplied target in the final report. When JavaScript or TypeScript
  is scanned, `findings.json.scan_meta.language` and every matching detection
  say `javascript` or `typescript`; the only pattern is `flat_prefix_cluster`.
- Keep source read-only. The scripts may create only the requested report
  artifacts.
- A Go run writes `scan.json` and reports analysis status `complete`, `partial`,
  `unsupported`, or `failed`. `findings.json.analysis.go` must preserve the
  same status and full pre-eligibility inventory.

## Supported invariants

### Python reference bands

The existing Python path remains unchanged and uses the host's optional
`.engineering/docs/find-folder-topology-drift-scope.md` and repo-wide
`.engineering/docs/ignore.md` descriptors. Its bands are:

- `flat_prefix_cluster` — direct `.py` siblings with a shared `<prefix>_`.
- `tests_by_prefix` — three or more `tests_*.py` files with no `tests/` folder.
- `sparse_folder_package` — a non-framework Python package below the ADR 0006
  organizational-child threshold.
- `pages_route_mirror` — Python filename prefixes duplicated beneath the
  recognized `pages/<route>/` route-mirror layout.

The Python command may narrow with `--root`; `--exclude` subtracts more paths.

### TypeScript v1: explicit source roots only

Pass one or more `--typescript-root` values. Without this flag, the detector
does not scan TypeScript. Each root must be an existing directory inside
`--project-root`; an invalid root is `scan-blocked` (exit 2), never a fallback
whole-repo scan.

An invocation with `--typescript-root` and no `--root` is TypeScript-only; it
does not scan Python elsewhere in the host and needs no exclusion for Python
trees. Pass both root forms only when an additive combined scan is intended.

Within every declared root, the detector groups direct `.ts` and `.tsx`
siblings by the first token before `_` or `-`. It emits exactly one
`flat_prefix_cluster` record per token with at least three files and a token of
at least two characters. The finding is lexical evidence of a naming cluster,
not a package recommendation.

Keep these TypeScript shapes clean:

- fewer than three siblings or three mixed first tokens;
- `index.ts` / `index.tsx`, `.d.ts`, `*.spec.ts[x]`, and `*.test.ts[x]`;
- anything under `tests/`, `test/`, `__tests__/`, `specs/`, `generated/`, `vendor/`,
  `node_modules/`, `dist/`, `build/`, `coverage/`, or `reports/`;
- any path subtracted by a repeatable, additive `--exclude PATTERN`.

Do not infer a framework convention, a barrel boundary, TypeScript module
resolution, import safety, test placement, package density, or a safe file
move. Those claims are deliberately outside this v1.

### JavaScript v1: explicit source roots only

Pass one or more `--javascript-root` values to scan `.js`, `.jsx`, `.mjs`, and
`.cjs`. Its invocation and output contract matches the TypeScript lexical band
but it is a separate JavaScript collector. It excludes `index.js[x]`/
`index.mjs`/`index.cjs`, `*.spec.*`, `*.test.*`, generated, minified, vendor,
dependency, build, report, test, and symlink paths. A JavaScript cluster is
only a lexical naming observation; it proves no module resolution, package
layout, import safety, framework convention, or safe move.

### Go v1: explicit source roots only

Pass one or more `--go-root` values. A Go-only invocation does not run the
Python bands. The detector discovers Go from `PATH`, requires Go >= 1.22.0,
and inventories every selected `.go` and `_test.go` file before eligibility.
It explicitly excludes `_test.go`, test trees, generated files/trees/markers,
vendor paths, symlinks, and additive `--exclude` paths.

Eligible direct siblings are grouped by the first underscore token. At least
three files with a token of at least two characters emit one Go
`flat_prefix_cluster`. The `python-filesystem-names` analyzer is filename-only:
it does not parse syntax, load packages, interpret build tags, resolve imports,
or recommend a move. A malformed Go body can therefore still support this
filename fact; unreadable UTF-8 is a failed inventory row and makes the result
`partial`.

## Pipeline

Run from the host project. The stock Codex install places this skill under
`.agents/skills/`; use the host's Python 3.11+ interpreter outside this
repository. During source-checkout validation only, use this worktree's
`.venv/bin/python`.

```bash
FT_PROJECT_ROOT="$PWD"
FT_SKILL_DIR="$FT_PROJECT_ROOT/.agents/skills/find-folder-topology-drift"
FT_SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
FT_REPORT_DIR="$FT_PROJECT_ROOT/reports/find-folder-topology-drift/$FT_SCAN_ID"
mkdir -p "$FT_REPORT_DIR"
cd "$FT_SKILL_DIR"
python3 scripts/detect.py \
  --project-root "$FT_PROJECT_ROOT" \
  --typescript-root src \
  --output "$FT_REPORT_DIR/detections.jsonl"
python3 scripts/report.py \
  --detections "$FT_REPORT_DIR/detections.jsonl" \
  --output-md "$FT_REPORT_DIR/report.md" \
  --output-json "$FT_REPORT_DIR/findings.json" \
  --target "src" \
  --language typescript
```

For JavaScript, replace `--typescript-root src` with `--javascript-root src`
and pass `--language javascript` to the reporter. Use `--language mixed` only
when deliberately combining explicit Python and/or both language roots.

For Python, omit `--typescript-root` and optionally replace it with `--root`:

```bash
cd "$FT_SKILL_DIR"
python3 scripts/detect.py \
  --project-root "$FT_PROJECT_ROOT" \
  --root app/services \
  --exclude 'app/services/scratch' \
  --output "$FT_REPORT_DIR/detections.jsonl"
python3 scripts/report.py \
  --detections "$FT_REPORT_DIR/detections.jsonl" \
  --output-md "$FT_REPORT_DIR/report.md" \
  --output-json "$FT_REPORT_DIR/findings.json" \
  --target "app/services" \
  --language python
```

For a combined run, pass both `--root <python-subtree>` and
`--typescript-root <typescript-subtree>`, then use `--language mixed`. Do not
label a TypeScript-only artifact `python` or a combined artifact `typescript`.

For a copied Go closure, use:

```bash
FT_PROJECT_ROOT="$PWD"
FT_SKILL_DIR="$FT_PROJECT_ROOT/.agents/skills/find-folder-topology-drift"
FT_REPORT_DIR="$FT_PROJECT_ROOT/reports/find-folder-topology-drift/scan-go"
mkdir -p "$FT_REPORT_DIR"
python3 "${FT_SKILL_DIR}/scripts/detect.py" \
  --project-root "$FT_PROJECT_ROOT" --go-root . \
  --output "$FT_REPORT_DIR/detections.jsonl"
python3 "${FT_SKILL_DIR}/scripts/report.py" \
  --detections "$FT_REPORT_DIR/detections.jsonl" \
  --output-md "$FT_REPORT_DIR/report.md" \
  --output-json "$FT_REPORT_DIR/findings.json" \
  --target . --language go
go test ./...
```

## Read the artifacts before acting

`detections.jsonl` is the detector truth. `report.md` is the human-readable
summary. `findings.json` repeats the records and carries `scan_meta`, including
the language label and the patterns actually present. For TypeScript v1, reject
any output that has a pattern other than `flat_prefix_cluster`.

Go mode also writes `scan.json`; grade Go completeness from it and
`findings.json.analysis.go`, not from a zero-finding JSONL alone.

For a Python `flat_prefix_cluster`, `tests_by_prefix`, or
`sparse_folder_package`, `/propose-folder-reorganization` produces the
read-only move table and impact review. Keep the TypeScript finding as a
triage item until a separate TypeScript proposal contract can resolve imports.

## Replay check

Run this after changing the installed scripts. It proves the documented
TypeScript command and final artifacts, not that an arbitrary host is clean.

```bash
FT_INSTALL_ROOT="$PWD"
FT_SKILL_DIR="$FT_INSTALL_ROOT/.agents/skills/find-folder-topology-drift"
FT_REPLAY_ROOT="$(mktemp -d /tmp/folder-topology-replay.XXXXXX)"
mkdir -p "$FT_REPLAY_ROOT/src/billing" "$FT_REPLAY_ROOT/reports"
touch "$FT_REPLAY_ROOT/src/billing/billing_parser.ts" \
  "$FT_REPLAY_ROOT/src/billing/billing-validator.ts" \
  "$FT_REPLAY_ROOT/src/billing/billing-types.ts"
cd "$FT_SKILL_DIR"
python3 scripts/detect.py \
  --project-root "$FT_REPLAY_ROOT" --typescript-root src \
  --output "$FT_REPLAY_ROOT/reports/detections.jsonl"
python3 scripts/report.py \
  --detections "$FT_REPLAY_ROOT/reports/detections.jsonl" \
  --output-md "$FT_REPLAY_ROOT/reports/report.md" \
  --output-json "$FT_REPLAY_ROOT/reports/findings.json" \
  --target src --language typescript
```

The expected final result is one finding labeled
`language: typescript`, `pattern: flat_prefix_cluster`.

## When things go sideways

| Symptom | Action |
|---|---|
| A root is missing or outside `--project-root` | Stop on exit 2, correct the path, and re-run. Never relabel a fallback scan as the requested root. |
| `detections.jsonl` is missing | Mark `scan-blocked` and paste the failed detector output; do not hand-write a report. |
| The reporter fails after detection | Preserve `detections.jsonl`, mark `scan-blocked`, and paste the reporter failure. |
| A TypeScript cluster needs an import-safe move plan | State that v1 does not resolve imports; request a TypeScript proposal contract instead of applying a Python package convention. |
| A Python finding is scratch or a framework convention | Keep it advisory and record the reason in the downstream proposal or add an additive `--exclude`. |
| Go is missing or older than 1.22.0 | Keep the `unsupported` `scan.json`, restore Go >= 1.22.0 on `PATH`, and re-run. |
| A selected Go file is unreadable | Keep useful clusters with `partial` status and cite the failed inventory row; never claim the root was completely inventoried. |
| A Go cluster needs a safe package move | State that v1 has no package/import/build-tag facts; use a separately proven Go proposal workflow. |

## Installed layout

```
find-folder-topology-drift/
├── SKILL.md
└── scripts/
    ├── detect.py
    ├── report.py
    └── support.py     # family-local scope and report helpers
```

The selected skill imports only these files and the Python standard library, so
a stock copy can run with `python3 -I -S` outside the source checkout.
