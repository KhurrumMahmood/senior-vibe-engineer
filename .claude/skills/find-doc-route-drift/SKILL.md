---
name: find-doc-route-drift
description: Compare documented product routes and redirect claims against Django URL patterns and simple redirect calls. SUSPECT skill for stale docs and route contract drift.
argument-hint: "[--docs-root .claude/docs --root-urls app/urls.py]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Documented routes and redirect claims drifting from Django URL
  patterns — docs claiming `/x/y/` redirects exist when the route
  module no longer registers them. SUSPECT for product-topology drift.
not_for: |
  Code-side dead routes (use /find-dormant). Live route deduplication
  or include-boundary problems (use /find-route-sprawl). Frontend
  template-to-JS boot contracts (use /find-frontend-contract-drift).
language: python
framework: django
---

# /find-doc-route-drift

You are the orchestrator for a product-topology SUSPECT skill. Detect
when docs describe routes or redirects that no longer match code.

## Scope

- Default docs root: `.claude/docs`.
- Default URL source: `app/urls.py`.
<!-- spec:project-structure-redesign-phase-2::IM-16 -->
- Output: `reports/doc-route-drift/<scan-id>/`.
- No code edits.

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/doc-route-drift/$SCAN_ID"
mkdir -p "$REPORT_DIR"
python3 .claude/skills/find-doc-route-drift/scripts/detect.py \
  --output "$REPORT_DIR/detections.jsonl"
python3 .claude/skills/find-doc-route-drift/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID" \
  --target .claude/docs
```

## Findings

- `unknown_documented_route`: docs mention a route that no URL pattern
  provides.
- `stale_redirect_claim`: docs claim a redirect target that differs
  from the view's simple redirect call.
- `unverified_redirect_claim`: docs claim a redirect but the scanner
  cannot prove the target.

## Next Skills

- Use `/fix-workflow` for small doc corrections.
- Use `/prevent-regression` if docs-route drift recurs often enough to
  justify a scheduled or diff-scoped check.
