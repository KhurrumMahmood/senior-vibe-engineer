---
name: find-frontend-contract-drift
description: "Detect implicit template-to-JS boot contracts: scattered `window.*` globals, undeclared JS reads, repeated reads that should be accessed through a canonical payload, and globally-loaded JS auto-init that fetches or mutates DOM without a page marker."
argument-hint: "[--template-root templates --js-root static/js]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Implicit template-to-JS boot contracts — scattered `window.*`
  globals, undeclared JS reads of template-set globals, repeated reads
  that should funnel through a canonical boot payload, or global JS
  auto-init that starts fetch/DOM work without checking a page marker.
not_for: |
  Dead JS bundles (use bundler analysis). Duplicated workflow step
  definitions across template/JS/Python (use
  /find-workflow-duplication). Documented routes drifting from URL
  registrations (use /find-doc-route-drift).
language: python
framework: django
scans: [javascript, templates]
---

# /find-frontend-contract-drift

You are the orchestrator for a product-topology SUSPECT skill. Detect
where server templates and browser JavaScript communicate through
implicit global variables instead of a documented boot payload.

## Scope

- Default template root: `templates/`.
- Default JS root: `static/js/`.
- Output: `reports/frontend-contract-drift/<scan-id>/`.
- No code edits.

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/frontend-contract-drift/$SCAN_ID"
mkdir -p "$REPORT_DIR"
python3 .claude/skills/find-frontend-contract-drift/scripts/detect.py \
  --output "$REPORT_DIR/detections.jsonl"
python3 .claude/skills/find-frontend-contract-drift/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID" \
  --target templates+static/js
```

## Findings

- `boot_global_sprawl`: many template-injected boot globals.
- `implicit_template_global`: direct template assignment to
  `window.<NAME>`.
- `undeclared_window_read`: JS reads a boot-like global that is not
  declared in the scanned roots.
- `widely_read_boot_global`: repeated JS reads should go through an
  accessor or payload object.
- `unscoped_global_auto_init`: a globally-loaded DOMContentLoaded/load
  handler, top-level `init*()` call, or shared-template
  `window.Module.init()` call starts `fetch()`/polling or DOM mutation
  without checking a page marker such as `document.body.dataset`,
  `body.classList.contains(...)`, or a `[data-*]` selector.

Reports should distinguish target findings from broader repo findings.
For example, a `/sites` cleanup can be "target clean" even if a
separate ExternalSource template still has boot-contract findings.

## Feature-Start Considerations

When adding a template-loaded JS feature, prefer a small server-owned
boot payload plus accessor helpers over new `window.*` globals. If the
feature needs URLs, status provider keys, or workflow visibility, check
whether a product workflow registry already owns that data. Add a
static regression test when retiring globals or raw endpoint strings.
If a JS file is loaded globally or by a shared base template, every
auto-init path that fetches or mutates DOM should first prove it is on
the owning page via a page marker. Element-existence checks are useful
for optional widgets; page markers are what prevent setup-only polling
from running on non-setup pages.

## Next Skills

- Use `/extract-workflow-registry` when the boot payload belongs to a
  product workflow.
- Use `/prevent-regression` after a canonical payload lands, to block
  new scattered globals.
