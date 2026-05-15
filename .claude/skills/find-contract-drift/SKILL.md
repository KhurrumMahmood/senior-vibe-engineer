---
name: find-contract-drift
description: |
  Advisory SUSPECT scan for `/sites` cross-layer contract drift beyond
  boot globals: endpoint keys, DOM IDs, `data-*` selectors,
  template-called JS exports, and JSON/boot payload fields. Imports the
  existing `/find-frontend-contract-drift` boot-global detector and adds
  route-surface contract bands.
argument-hint: "[paths... - defaults to the /sites route surface]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Contract drift in `/sites` where templates, static JavaScript, site
  workflow registries, and API payloads disagree: endpoint keys, DOM
  IDs, `data-*` selectors, template JS contracts, template-called JS
  exports, JSON payload fields, missing `SiteConfigCore.siteEndpoint`
  keys, stale `window.Namespace.method()` calls, and scattered boot
  globals.
not_for: |
  Repeated workflow labels or route literals owned by multiple layers
  (use `/find-workflow-duplication`), type-checking a compiled frontend,
  proving runtime HTTP behavior, or blocking commits in v1. Use targeted
  tests and `/prevent-regression` only after a detector band proves
  low-noise on real route work.
language: any
framework: django
---

# /find-contract-drift

Run an advisory contract audit for the `/sites` route surface. This skill
reuses `/find-frontend-contract-drift` for boot-global contracts, then
adds DOM, endpoint, and template-to-JS checks that are specific to the
site workflow.

## Pipeline

```
.venv/bin/python .claude/skills/find-contract-drift/scripts/run.py <paths...>
```

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
