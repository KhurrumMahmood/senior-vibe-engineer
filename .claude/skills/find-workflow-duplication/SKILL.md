---
name: find-workflow-duplication
description: Detect duplicated product-step authority such as labels, tab ids, route literals, endpoint suffixes, sidebar/dashboard step definitions, boot payload keys, and status text across backend, templates, JS, and docs.
argument-hint: "[workflow-name: sites]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Repeated step labels, tab IDs, route literals, endpoint suffixes,
  sidebar/dashboard step definitions, boot payload keys, and status
  text duplicated across backend, templates, JS, and docs for one
  product workflow. SUSPECT skill for product topology.
not_for: |
  Generic code duplication across functions (use /find-duplication or
  /find-semantic-duplication). Route prefix sprawl (use
  /find-route-sprawl). Doc/route drift (use /find-doc-route-drift).
language: python
framework: django
---

# /find-workflow-duplication

You are the orchestrator for a product-topology SUSPECT skill. Detect
when the same workflow step knowledge is repeated across layers instead
of owned by a registry.

## Scope

- Default workflow: `sites`.
- Scans `core/`, `templates/`, `static/js/`, `docs/`, and
  `.claude/docs/`.
- Output: `reports/workflow-duplication/<scan-id>/`.
- No code edits.

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/workflow-duplication/$SCAN_ID"
mkdir -p "$REPORT_DIR"
python3 .claude/skills/find-workflow-duplication/scripts/detect.py \
  --min-active-owners 2 \
  --output "$REPORT_DIR/detections.jsonl"
python3 .claude/skills/find-workflow-duplication/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID" \
  --target sites
```

## Findings

- `duplicated_workflow_label`: step label repeated across owner layers.
- `duplicated_workflow_tab_id`: tab key repeated across owner layers.
- `duplicated_route_literal`: route literal repeated across owner
  layers.
- `duplicated_endpoint_authority`: site-scoped API endpoint suffixes
  built by consumers instead of provided by a workflow boot payload.
- `duplicated_boot_contract`: templates or JS defining workflow boot
  keys that should come from the canonical registry.

Every finding includes surface classification:

- `active_executable`: current templates, loaded JS, views, or services
  that can change runtime behavior.
- `legacy_unloaded`: JS or templates in the workflow file family that
  are not loaded by current site-config templates.
- `route_definition`: URLconf definitions. These can stay literal when
  route names and consumers are registry-owned.
- `docs` / `tests`: reference material and regression coverage.

## Triage Rules

- Lexical repeats are evidence, not findings. A label, tab id, route
  prefix, or endpoint suffix appearing in docs/tests does not matter by
  itself.
- Start from active executable repeats. Treat legacy/unloaded files,
  docs/tests, and route definitions as context unless they are paired
  with two or more active executable owners that can drift.
- Use a two-pass migration lens for endpoint or boot-payload cleanup:
  first migrate consumers loaded by current templates, then sweep the
  remaining workflow-family static files. Dormant prototype JS should be
  deleted when it has no unique knowledge; otherwise quarantine it with
  an explicit reason instead of keeping silent compatibility debt.
- Promote to a finding only when multiple executable layers can change
  behavior independently: navigation, page tabs, status providers,
  route/URL generation, endpoint construction, feature visibility, or
  boot payload shape.
- Every finding must name the proposed canonical owner. For `/sites`,
  prefer `SiteWorkflowRegistry` or the existing workflow boot payload
  when the duplication is about steps, visibility, JS boot data, or
  site-config endpoint consumers.
- Do not fold ai-sidecar workflow rules into general `/sites`
  workflow findings unless the user explicitly scopes that work in.

## Next Skills

- Use `/extract-workflow-registry` to propose the explicit owner.
- Use `/fix-workflow` only after tests pin the current labels, tabs,
  redirects, and page rendering.
