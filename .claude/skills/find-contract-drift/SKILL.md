---
name: find-contract-drift
description: |
  Advisory SUSPECT scan for cross-layer contract drift on configured
  product-workflow targets or explicit paths: endpoint keys, DOM IDs,
  `data-*` selectors, template-called JS exports, and JSON/boot payload
  fields. Imports the existing `/find-frontend-contract-drift`
  boot-global detector and adds route-surface contract bands.
argument-hint: "[paths... - defaults to workflow_targets(project_root); empty without .engineering/docs/product-workflows.md]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Contract drift in configured product-workflow targets where templates,
  static JavaScript, workflow registries, and API payloads disagree:
  endpoint keys, DOM IDs, `data-*` selectors, template JS contracts,
  template-called JS exports, JSON payload fields, missing
  `SiteConfigCore.siteEndpoint` keys, stale
  `window.Namespace.method()` calls, and scattered boot globals.
not_for: |
  Repeated workflow labels or route literals owned by multiple layers
  (use `/find-workflow-duplication`), type-checking a compiled frontend,
  proving runtime HTTP behavior, or blocking commits in v1. Use targeted
  tests and `/prevent-regression` only after a detector band proves
  low-noise on real route work.
language: any
framework: django
scans: [python, javascript, templates]
---

# /find-contract-drift

Run an advisory contract audit for configured product-workflow targets.
This skill reuses `/find-frontend-contract-drift` for boot-global
contracts, then adds DOM, endpoint, and template-to-JS checks that are
specific to the scanned workflow files.

Default scope is not hard-coded to `/sites`. With no positional paths,
`scripts/run.py` passes `None` into `detect()`, and
`product_health.expand_paths()` scans `workflow_targets(project_root)`
from `.engineering/docs/product-workflows.md` (`## Targets`). If that
descriptor or section is absent, the default workflow target set is
empty. To scan a concrete surface, pass explicit positional paths after
`scripts/run.py`.
On no-path runs, the detector may also add boot-contract coverage from
`workflow_template_roots(project_root)` and `templates/core/includes`;
pass explicit paths when you need exact scan scope.

## How success is judged

- The runner exits 0 and prints the scan directory it wrote.
- `reports/find-contract-drift/scan-<UTC>/detections.jsonl`,
  `report.md`, `findings.json`, and `latest` exist under the selected
  `--project-root`.
- The target scope is explicit in the command or comes from
  `workflow_targets(project_root)`; do not describe a no-descriptor run
  as a `/sites` scan.
- Findings are grouped by contract detector bands and are treated as
  advisory triage input; high-confidence DOM/export/endpoint findings
  may feed `/fix-workflow` or `extract-workflow-registry`.

## Pipeline

```
.venv/bin/python .claude/skills/find-contract-drift/scripts/run.py <paths...>
```

`<paths...>` are positional path or glob arguments. Omit them only when
the host repo has declared `## Targets` in
`.engineering/docs/product-workflows.md`.

The runner writes:

- `reports/find-contract-drift/scan-<UTC>/detections.jsonl`
- `reports/find-contract-drift/scan-<UTC>/report.md`
- `reports/find-contract-drift/scan-<UTC>/findings.json`
- `reports/find-contract-drift/latest`

## Detector Bands

- `implicit_template_global` and related boot-contract findings imported
  from `/find-frontend-contract-drift`.
- `missing_endpoint_key`: JS calls `SiteConfigCore.siteEndpoint*("key")`
  for a key absent from `SiteWorkflowRegistry.SITE_ENDPOINTS` or
  `SITE_ENDPOINT_TEMPLATES`.
- `missing_js_export`: a template calls `window.Namespace.method()` but
  the scanned JS namespace export does not expose that method.
- `missing_dom_id`: JS reads an ID that is absent from scanned templates.
- `missing_data_selector`: JS queries a `data-*` selector absent from
  scanned templates.

Treat results as triage input, not a chore pile. High-confidence new
findings are candidates for cleanup; noisy or intentional findings should
be captured as fixture refinements or accepted tradeoffs.

## When things go sideways

| Symptom | Action |
|---|---|
| Descriptor absent | Treat the default workflow target set as empty; pass explicit positional paths or add `## Targets` to `.engineering/docs/product-workflows.md`. |
| Zero findings | Check whether `detections.jsonl` is empty because the workflow target set expanded to no `.py`, `.js`, or `.html` files; rerun with explicit paths before calling the contract surface clean. |
| Script failure | Re-run the exact `.venv/bin/python .claude/skills/find-contract-drift/scripts/run.py ...` command, capture stderr, and fix the path/import/argparse failure before interpreting results. |
