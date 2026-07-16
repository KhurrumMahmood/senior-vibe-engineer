---
name: find-frontend-contract-drift
description: "Detect implicit template-to-JS boot contracts: scattered `window.*` globals, undeclared JS reads, repeated reads that should be accessed through a canonical payload, and globally-loaded JS auto-init that fetches or mutates DOM without a page marker."
argument-hint: "[--template-root PATH --js-root PATH]"
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

## How success is judged

- The run is graded only by artifacts: pasted detector/reporter command
  output plus `detections.jsonl`, `report.md`, and `findings.json`.
  Do not claim a target is clean without those files.
- The scan verdict is one of `target-clean`, `target-drift`,
  `broad-drift-only`, or `scan-blocked`. Use `broad-drift-only` when
  the requested target has no findings but the broader scan universe
  still emits unrelated frontend-contract findings.
- The documented roots match argparse: `--template-root` and `--js-root`
  are optional narrowing flags. With neither flag, the detector scans
  the host scope universe, not a baked `templates/` or `static/js/`
  subtree.
- The skill remains read-only. It can recommend a canonical boot payload
  or a follow-up guard, but it never edits templates, JavaScript, or
  route code.

## Scope

- Default template/JS roots: unset. The detector loads the per-skill
  scope/ignore descriptors when a host repo provides them; otherwise it
  scans the repository tree for `.html` and `.js` files after the shared
  exclusions. Script selection includes JavaScript and TypeScript-family
  extensions (`.js`, `.mjs`, `.cjs`, `.jsx`, `.ts`, and `.tsx`).
- Use `--template-root PATH` or `--js-root PATH` only to narrow one side
  of the scan for this invocation.
- Output: `reports/frontend-contract-drift/<scan-id>/`.
- No code edits.

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/frontend-contract-drift/$SCAN_ID"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/detect.py \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID" \
  --target "default scope"
```

For a narrowed run, forward the same scope to the detector and reporter:

```bash
.venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/detect.py \
  --template-root .claude/skills/find-frontend-contract-drift \
  --js-root .claude/skills/find-frontend-contract-drift \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID" \
  --target ".claude/skills/find-frontend-contract-drift"
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
Declare the target verdict from the requested scope, then separately
name any broader findings that remain in the report.

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

## Replay check

After editing this skill or its detector contract, run:

```bash
.venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/detect.py --help
SCAN_ID="scan-replay"
REPORT_DIR="/tmp/find-frontend-contract-drift-${SCAN_ID}"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/detect.py \
  --template-root .claude/skills/find-frontend-contract-drift \
  --js-root .claude/skills/find-frontend-contract-drift \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/report.py \
  --detections "$REPORT_DIR/detections.jsonl" \
  --output-md "$REPORT_DIR/report.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID" \
  --target ".claude/skills/find-frontend-contract-drift" \
  --skip-effectiveness-log
```

Paste the command output when using it as repair evidence. The narrowed
replay proves the documented flags, reporter flags, and exit behavior;
it is not a product-surface audit.

## When things go sideways

| Symptom | Action |
|---|---|
| The user expected `templates/` or `static/js/` to be the default | State that those roots are optional narrowing flags, then re-run with `--template-root templates` and/or `--js-root static/js` if that is the intended target. |
| Detector output exists but the reporter fails | Mark the verdict `scan-blocked`, paste the reporter failure, and keep `detections.jsonl` as the only trusted artifact. |
| Report shows unrelated broad findings | Use `broad-drift-only` when the requested target is clean; do not fold unrelated rows into the target verdict. |
| A JS auto-init finding is on a shared file with an intentional guard elsewhere | Keep the row advisory and cite the guard evidence; route to human triage rather than deleting or rewriting code in this skill. |
| Effectiveness logging fails | Keep the scan artifacts and state the logging failure; do not rerun the detector just to produce a log row. |
