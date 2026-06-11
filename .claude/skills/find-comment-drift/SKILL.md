---
name: find-comment-drift
description: |
  Advisory SUSPECT scan for comments, docstrings, JSDoc, and template
  comments that have drifted from the code they are meant to clarify.
  Flags detached section banners, narration comments, missing or thin
  public class docstrings, stale terminology, JavaScript functions that
  deserve real JSDoc, thin ceremonial JSDoc, noisy HTML comments, and
  fragile doc references.
argument-hint: "[paths... - defaults to the /sites route surface]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Auditing explanatory-code hygiene after AI-heavy development: noisy
  comments that narrate the next line, missing ownership docstrings,
  stale terminology in comments/docstrings, banner comments that should
  be adjacent JSDoc or deleted, and Django-template comments that repeat
  visible headings.
not_for: |
  Generating external product documentation, blocking commits, enforcing
  exact prose style, or proving runtime behavior. Use targeted tests and
  existing lints for behavior and correctness.
language: any
framework: django
scans: [python, javascript, templates]
---

# /find-comment-drift

You are running an advisory comment/docstring hygiene audit. The goal is
to find explanatory text that makes an AI-grown codebase harder to skim:
stale terms, detached banners, narration comments, thin class docstrings,
missing natural JSDoc, and noisy template comments.

This skill never edits code and never blocks commits. It writes findings
under `reports/find-comment-drift/scan-<UTC>/` so a cleanup pass can use
the report as a checklist. The commit-time `comment-drift` lint imports the
same detector but fails only the bad-comment subset on the live `/sites`
surface; JSDoc candidates and thin docstrings remain advisory here.

## Default Target

If the caller does not provide paths, scan the `/sites` route surface:

```
app/pages/sites
app/site_management
app/api/site_config
app/api/sitemaps.py
app/api/field_config.py
app/api/brand_downloads
app/api/collections.py
app/api/ptid.py
app/api/visual_extraction.py
app/api/training.py
app/api/tier_detection.py
app/api/brand_mapping.py
app/api/site_checklist.py
app/api/crawling/legacy_dispatch.py
app/api/crawling/orphan_jobs.py
app/pages/crawling.py
app/services/sites
static/js/site-config-core.js
static/js/site-config-sidebar.js
static/js/site-config-preview.js
static/js/site-config-ui.js
static/js/site-config-discovery.js
static/js/site-config-custom-import.js
static/js/site-config-external_source-brand.js
static/js/site-config-agent-review.js
static/js/site-config-brand-detection.js
static/js/site-config-external_source-summary.js
static/js/site-config-forms.js
static/js/site-config-proxy.js
static/js/site-config-jobs.js
static/js/site-config-flatdata-chat.js
static/js/site-config-flatdata-preview.js
static/js/site-config-fields.js
static/js/site-config-training.js
static/js/site-config-ptid.js
static/js/site-config-pages.js
static/js/site-config-images.js
static/js/site-config-brand-mapping.js
static/js/download-filters.js
static/js/export-preview.js
static/js/export-filters.js
static/js/export-viewer-utils.js
static/js/export-progress.js
static/js/brand-picker.js
static/js/app-dialog.js
static/js/app-modal.js
static/js/app-csrf.js
templates/core/site_config_base.html
templates/core/_site_checklist.html
app/pages/sites/templates/core
```

## Pipeline

Run with the project venv:

```
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/find-comment-drift/$SCAN_ID"
.venv/bin/python .claude/skills/find-comment-drift/scripts/detect.py --output "$REPORT_DIR/detections.jsonl" <paths...>
.venv/bin/python .claude/skills/find-comment-drift/scripts/report.py "$REPORT_DIR/detections.jsonl" --output "$REPORT_DIR/report.md" --target "<paths...>"
ln -sfn "$SCAN_ID" reports/find-comment-drift/latest
```

If shell process substitution or symlinks are awkward in the current
environment, create the directory with any equivalent safe command. The
required artifacts are:

- `detections.jsonl` - one finding per line.
- `report.md` - grouped human-readable report.
- `findings.json` - machine-readable report summary.

## Detector Bands

- `detached_section_banner`: banner comments separated from the symbol or
  block they describe.
- `obvious_narration_comment`: comments that merely narrate the next line.
- `missing_public_class_docstring`: public Python class without an
  ownership or contract docstring.
- `thin_public_class_docstring`: public Python class with a vague or
  too-short docstring.
- `stale_comment_term`: comments/docstrings using stale terminology such
  as `SiteConfig`.
- `jsdoc_candidate`: JavaScript functions, handlers, initializers, async
  workflows, or global helpers that should have real JSDoc.
- `thin_jsdoc_comment`: JSDoc exists, but it is too ceremonial to describe
  the useful parameter, return-value, side-effect, or workflow contract.
- `noisy_html_comment`: Django/HTML comments that duplicate visible
  headings or section labels.
- `malformed_doc_reference`: comments/docstrings with brittle file/line
  references such as `foo.py:42`, `line 42`, or `L42`.

## Smoke Test

Before trusting changes to the detector, run:

```
.venv/bin/python .claude/skills/find-comment-drift/scripts/smoke.py
```

The smoke test scans good/bad Python, JavaScript, and Django-template
fixtures and asserts that every detector band has at least one bad
fixture while the good fixtures stay clean.

## Judgment

Treat findings as a senior-engineer review queue, not a mechanical patch
list. Preserve comments that explain intent, compatibility, safety,
non-obvious history, race conditions, cross-layer contracts, or template
gotchas. Prefer deleting narration over rewriting it. Prefer JSDoc when a
JavaScript function is public-ish, shared, async, global, or has a real
input/output/side-effect contract.
