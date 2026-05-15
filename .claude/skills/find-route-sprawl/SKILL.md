---
name: find-route-sprawl
description: Detect route prefixes for a product workflow that are scattered through flat URL modules, missing include ownership boundaries, or duplicated as ambiguous API aliases. SUSPECT skill for product topology.
argument-hint: "[--root-urls core/urls.py]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Flat route ownership where one workflow's URL prefixes are scattered
  through `core/urls.py` without `path('', include())` boundaries;
  duplicate alias routes registered for the same view.
not_for: |
  Doc/route drift (use /find-doc-route-drift). Workflow-step
  duplication across templates+JS+Python (use
  /find-workflow-duplication). Dead URL patterns (use /find-dormant).
language: python
framework: django
---

# /find-route-sprawl

You are the orchestrator for a product-topology SUSPECT skill. Detect
when workflow routes are technically valid but hard to own because they
live in a flat URL namespace.

## Scope

- Default target: `core/urls.py`.
- Output: `reports/route-sprawl/<scan-id>/report.md` and
  `findings.json`.
- No code edits, no route changes.

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/route-sprawl/$SCAN_ID"
mkdir -p "$REPORT_DIR"
python3 .claude/skills/find-route-sprawl/scripts/detect.py \
  --output "$REPORT_DIR/detections.jsonl"
python3 .claude/skills/find-route-sprawl/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID" \
  --target core/urls.py
```

## Findings

- `flat_site_page_routes`: many `/sites/<site_id>/...` page routes in
  the root URL file.
- `flat_site_scoped_api_routes`: site-scoped API routes mixed into the
  global API namespace.
- `missing_workflow_include`: workflow routes exist without an include
  boundary.
- `duplicate_route_alias_surface`: one named route/view has multiple
  path strings.

## Next Skills

- Use `/extract-workflow-registry` before reshaping routes.
- Use `/prevent-regression` only after route grouping exists, to block
  new routes from bypassing the owner module.
