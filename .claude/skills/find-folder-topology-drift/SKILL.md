---
name: find-folder-topology-drift
description: Read-only SUSPECT audit for Python folder-topology drift and a narrow, explicit-root TypeScript/TSX flat-prefix cluster. Python retains its ADR 0006 promotion and demotion bands; TypeScript v1 reports only three-or-more direct `.ts`/`.tsx` siblings sharing a first `_` or `-` token. Use when a source folder is hard to skim because sibling filenames visibly name the same domain.
argument-hint: "[--root PATH] [--typescript-root PATH] [--min-cluster-size 3 --exclude PATTERN]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Auditing a Python package against ADR 0006's bidirectional ≥3-sibling
  threshold, or inspecting an explicitly named TypeScript source root for a
  simple same-domain filename cluster such as
  `billing_parser.ts`, `billing-validator.ts`, and `billing-types.ts`.
not_for: |
  Moving files, proving import safety, or deciding that a cluster must become
  a package. TypeScript v1 does not inspect sparse-package demotion, test-folder
  reorganization, Next.js/pages conventions, barrels, module resolution, or
  framework ownership. Use /propose-folder-reorganization only after a human
  confirms a Python finding; a TypeScript reorganization proposal needs its own
  resolved-import contract.
language: any
framework: any
scans: [python, typescript]
---

# /find-folder-topology-drift

Run a read-only directory-layout audit. Treat every finding as a human-triage
candidate, never as authorization to move files.

## How success is judged

- Produce `detections.jsonl`, `report.md`, and `findings.json`; cite their
  paths and the detector/reporter output. Do not claim a scan ran without those
  artifacts.
- Report `clean`, `drift-found`, or `scan-blocked`. `drift-found` is advisory.
- Echo the supplied target in the final report. When TypeScript is scanned,
  `findings.json.scan_meta.language` and every TypeScript detection say
  `typescript`; its only pattern is `flat_prefix_cluster`.
- Keep source read-only. The scripts may create only the requested report
  artifacts.

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

Within every declared root, the detector groups direct `.ts` and `.tsx`
siblings by the first token before `_` or `-`. It emits exactly one
`flat_prefix_cluster` record per token with at least three files and a token of
at least two characters. The finding is lexical evidence of a naming cluster,
not a package recommendation.

Keep these TypeScript shapes clean:

- fewer than three siblings or three mixed first tokens;
- `index.ts` / `index.tsx`, `.d.ts`, `*.spec.ts[x]`, and `*.test.ts[x]`;
- anything under `tests/`, `__tests__/`, `generated/`, `vendor/`,
  `node_modules/`, `dist/`, `build/`, `coverage/`, or `reports/`;
- any path subtracted by a repeatable, additive `--exclude PATTERN`.

Do not infer a framework convention, a barrel boundary, TypeScript module
resolution, import safety, test placement, package density, or a safe file
move. Those claims are deliberately outside this v1.

## Pipeline

Run from the host project. Set `SKILL_DIR` to the installed skill directory;
use the host's Python 3.11+ interpreter outside this repository. During source
checkout validation only, use this worktree's `.venv/bin/python`.

```bash
HOST="$PWD"
SKILL_DIR="$HOST/.claude/skills/find-folder-topology-drift"
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="$HOST/reports/find-folder-topology-drift/$SCAN_ID"
mkdir -p "$REPORT_DIR"
cd "$SKILL_DIR"
python3 scripts/detect.py \
  --project-root "$HOST" \
  --typescript-root src \
  --output "$REPORT_DIR/detections.jsonl"
python3 scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --target "src" \
  --language typescript
```

For Python, omit `--typescript-root` and optionally replace it with `--root`:

```bash
cd "$SKILL_DIR"
python3 scripts/detect.py \
  --project-root "$HOST" \
  --root app/services \
  --exclude 'app/services/scratch' \
  --output "$REPORT_DIR/detections.jsonl"
python3 scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --target "app/services" \
  --language python
```

For a combined run, pass both root forms and use `--language mixed`. Do not
label a TypeScript-only artifact `python` or a combined artifact `typescript`.

## Read the artifacts before acting

`detections.jsonl` is the detector truth. `report.md` is the human-readable
summary. `findings.json` repeats the records and carries `scan_meta`, including
the language label and the patterns actually present. For TypeScript v1, reject
any output that has a pattern other than `flat_prefix_cluster`.

For a Python `flat_prefix_cluster`, `tests_by_prefix`, or
`sparse_folder_package`, `/propose-folder-reorganization` produces the
read-only move table and impact review. Keep the TypeScript finding as a
triage item until a separate TypeScript proposal contract can resolve imports.

## Replay check

Run this after changing the installed scripts. It proves the documented
TypeScript command and final artifacts, not that an arbitrary host is clean.

```bash
HOST="$(mktemp -d /tmp/folder-topology-replay.XXXXXX)"
mkdir -p "$HOST/src/billing" "$HOST/reports"
touch "$HOST/src/billing/billing_parser.ts" \
  "$HOST/src/billing/billing-validator.ts" \
  "$HOST/src/billing/billing-types.ts"
cd "$SKILL_DIR"
python3 scripts/detect.py \
  --project-root "$HOST" --typescript-root src \
  --output "$HOST/reports/detections.jsonl"
python3 scripts/report.py \
  --detections "$HOST/reports/detections.jsonl" \
  --output-md "$HOST/reports/report.md" \
  --output-json "$HOST/reports/findings.json" \
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
