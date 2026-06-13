---
name: find-route-sprawl
description: Detect route prefixes for a product workflow that are scattered through flat URL modules, missing include ownership boundaries, or duplicated as ambiguous API aliases. SUSPECT skill for product topology.
argument-hint: "[--root-urls <path/to/urls.py>]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Flat route ownership where one workflow's URL prefixes are scattered
  through the root URL module without `path('', include())` boundaries;
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

- Default target: the root URLconf, auto-discovered via the per-skill
  scope universe (override with `--root-urls <path/to/urls.py>`).
- Output: `reports/route-sprawl/<scan-id>/report.md` and
  `detections.jsonl` / `findings.json`.
- No code edits, no route changes.

## How success is judged

- The run creates a fresh scan dir under `reports/route-sprawl/<scan-id>/`
  with `detections.jsonl`, `report.md`, and `findings.json`.
- Each command's exit code is honored; stop on non-zero and report the
  failing command instead of rendering stale detections.
- Handoff identifiers are valid: every `findings.json` record uses one of
  the `pattern` names in Findings and carries `file` / `lineno` evidence.
- No silent drops: the JSONL record count matches
  `findings.summary.findings_total` and the `findings` array length.
- A zero-finding run is successful only when those artifacts exist and
  `report.md` says `Findings: 0`.

## Pipeline

```bash
set -euo pipefail
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/route-sprawl/$SCAN_ID"
ROOT_URLS_ARGS=()
# Optional override:
# ROOT_URLS_ARGS=(--root-urls path/to/urls.py)
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-route-sprawl/scripts/detect.py \
  "${ROOT_URLS_ARGS[@]}" \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-route-sprawl/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID" \
  --target "root URLconf"
```

## Findings

- `flat_site_page_routes`: many `/sites/<site_id>/...` page routes in
  the root URL file.
- `flat_site_scoped_api_routes`: site-scoped API routes mixed into the
  global API namespace.
- `missing_workflow_include`: workflow routes exist without an include
  boundary.
- `scattered_route_family`: related workflow routes for the same route
  segment are separated by a large line span.
- `duplicate_route_alias_surface`: one named route/view has multiple
  path strings.

## When things go sideways

| Case | Signal | Response |
|---|---|---|
| Target absent | `detect.py` writes `0 findings (no urls.py found)` or the `--root-urls` path is not readable. | Keep the zero-finding artifacts if the script exits 0; otherwise stop and report the missing target. |
| Zero findings | `detections.jsonl` is empty and `report.md` says `Findings: 0`. | Treat as a clean scan, not as a skipped scan; do not invent route-sprawl findings. |
| Script non-zero exit | Any command exits non-zero. | Stop the pipeline, paste the command and stderr, and do not run `report.py` against stale detections. |

## Next Skills

- Use `/extract-workflow-registry` before reshaping routes.
- Use `/prevent-regression` only after route grouping exists, to block
  new routes from bypassing the owner module.
