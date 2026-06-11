---
name: map-product-workflow
description: Map a user-visible product workflow across routes, views, templates, JavaScript, docs, status providers, and compatibility redirects. Produces `.claude/docs/workflows/<name>.md`. MAP skill for topology-level quality.
argument-hint: "<workflow-name>"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: map
best_for: |
  A user-visible product workflow that is easy to understand in the
  UI but hard to locate in code — spans routes, views, templates,
  JavaScript, docs, status providers, and compatibility redirects.
  Produces `.claude/docs/workflows/<name>.md` as the topology map.
not_for: |
  Single-subsystem inventory (use /map-subsystem). Behavioral
  annotation of a known file (use /explain-code). Detection of
  workflow-step duplication (use /find-workflow-duplication).
language: python
framework: django
---

# /map-product-workflow

You are the orchestrator for a product-topology MAP skill. Use this
when a user-visible workflow is easy to understand in the UI but hard
to locate in code.

## Scope

- Workflow name: any label you pass. Its shape (steps, route shape, UI
  template/script globs) is host-authored in
  `.engineering/docs/product-workflows.md`; with no descriptor the map is
  empty rather than assuming a project's layout.
- Output: `.claude/docs/workflows/<name>.md`.
- Scratch JSON: `reports/product-topology/<scan-id>/<name>.json`.
- Python: `python3`; scripts are stdlib-only.
- No production code edits.

## Pipeline

```bash
SCAN_ID="workflow-map-$(date -u +%Y%m%d-%H%M%S)"
python3 .claude/skills/map-product-workflow/scripts/generate.py \
  <workflow-name> \
  --scan-id "$SCAN_ID"
```

The map inventories:

- workflow steps and canonical route names,
- page routes and site-scoped API routes,
- view-to-template render ownership,
- template-injected `window.*` boot globals and JS reads,
- JS modules participating in the workflow,
- status-provider candidates,
- redirects and route mentions in docs.

## When To Use

- Start of a new product area: before code spreads across routes,
  templates, JS, and services.
- Inheriting a large project: before local smell scans, so each file is
  read in product context.
- After major work: refresh the map, then run the targeted SUSPECT
  skills for drift.

## Next Skills

- Route ownership unclear: `/find-route-sprawl`.
- Step knowledge repeated: `/find-workflow-duplication`.
- Template/JS globals implicit: `/find-frontend-contract-drift`.
- Docs disagree with routes: `/find-doc-route-drift`.
- Registry shape is ready: `/extract-workflow-registry`.
