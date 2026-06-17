---
name: find-doc-route-drift
description: Compare documented product routes and redirect claims against Django URL patterns and simple redirect calls. SUSPECT skill for stale docs and route contract drift.
argument-hint: "[--docs-root .claude/docs] [--root-urls <path/to/urls.py>]"
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

## How success is judged

- The run is graded only by artifacts: pasted detector/reporter output
  plus `detections.jsonl`, `report.md`, and `findings.json`. Do not
  claim docs-route drift was checked without those files.
- The scan verdict is one of `docs-clean`, `route-drift`,
  `redirect-unverified`, or `scan-blocked`. `redirect-unverified`
  means docs claim a redirect the scanner could not prove from simple
  redirect calls.
- The summary names the docs root, URL source, total findings, bucket
  counts, and top rows from `report.md` or `findings.json`.
- The skill remains read-only. It can recommend doc edits, route
  investigation, or a recurring guard; it never edits docs or route
  modules in this run.

## Scope

- Default docs root: `.claude/docs`.
- Default URL source: the root URLconf, auto-discovered via the per-skill
  scope universe (override with `--root-urls <path/to/urls.py>`); follows
  `include()`s.
<!-- spec:project-structure-redesign-phase-2::IM-16 -->
- Output: `reports/doc-route-drift/<scan-id>/`.
- No code edits.

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/doc-route-drift/$SCAN_ID"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-doc-route-drift/scripts/detect.py \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-doc-route-drift/scripts/report.py \
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

If you dispatch an Agent to triage the report, tell it its output is
judged by row citations from `report.md` or `findings.json`, and that it
must return one of `docs-clean`, `route-drift`, `redirect-unverified`,
or `scan-blocked`. Uncited Agent claims are not evidence.

## Replay check

After editing this skill or its detector contract, run:

```bash
.venv/bin/python .claude/skills/find-doc-route-drift/scripts/detect.py --help
SCAN_ID="scan-replay"
REPORT_DIR="/tmp/find-doc-route-drift-${SCAN_ID}"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-doc-route-drift/scripts/detect.py \
  --docs-root .claude/docs \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-doc-route-drift/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID" \
  --target .claude/docs \
  --skip-effectiveness-log
```

This replay proves the documented flags, auto-discovery fallback, and
reporter contract execute. It does not prove a host product's live route
surface is clean.

## When things go sideways

| Symptom | Action |
|---|---|
| No root URLconf can be discovered | Mark `scan-blocked` for code-vs-doc proof, paste the detector output, and re-run with `--root-urls PATH` if the host has a known URL source. |
| Docs root is absent or empty | Mark `docs-clean` only if the detector artifact proves zero docs were scanned intentionally; otherwise use `scan-blocked` and ask for the docs root. |
| Redirect claim cannot be proven from simple redirect calls | Use verdict `redirect-unverified`, cite the row, and route to human route inspection rather than editing docs blindly. |
| Detector succeeds but reporter fails | Keep `detections.jsonl` as artifact truth, mark `scan-blocked`, and paste the reporter failure. |
| Effectiveness logging fails | Keep the scan artifacts and state the logging failure; do not rerun the detector solely to log. |
