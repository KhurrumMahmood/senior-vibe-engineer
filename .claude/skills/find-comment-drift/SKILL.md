---
name: find-comment-drift
description: |
  Advisory SUSPECT scan for comments, docstrings, JSDoc, and template
  comments that have drifted from the code they are meant to clarify.
  Flags detached section banners, narration comments, missing or thin
  public class docstrings, stale terminology, JavaScript and TypeScript
  functions that deserve real JSDoc, thin ceremonial JSDoc, noisy HTML
  comments, fragile doc references, and bounded Go, Java, and PHP lexical-comment surfaces.
argument-hint: "[paths... - no paths uses the detector's legacy default surface]"
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
framework: any
scans: [python, javascript, typescript, go, java, php, templates]
---

# /find-comment-drift

You are running an advisory comment/docstring hygiene audit. The goal is
to find explanatory text that makes an AI-grown codebase harder to skim:
stale terms, detached banners, narration comments, thin class docstrings,
missing natural JSDoc, and noisy template comments.

This skill never edits code and never blocks commits. It writes findings
under `reports/find-comment-drift/scan-<UTC>/` so a cleanup pass can use
the report as a checklist. The bundled `scripts/guard.py` and the repository
`comment-drift` lint consume the same detector but fail only the bad-comment
subset; JSDoc candidates and thin docstrings remain advisory here.

The detector is language-neutral only within its declared lexical bands. It
scans Python, JavaScript/JSX/MJS/CJS, TypeScript/TSX, Go, and HTML/template comments. It
does not use TypeScript type or module resolution, prove that a function is a
public API, or require JSDoc for ordinary TSX components solely because they
contain JSX.

Go is an explicit `--language go` mode. It inventories selected `.go` and
`_test.go` files before eligibility, then uses the family-local
`python-go-comment-lexer` to distinguish real `//`/`/* */` comments from
comment-looking quoted, rune, and raw-string contents. It reports only the
existing lexical stale-term, brittle-reference, banner, and narration bands;
it does not parse declarations or claim exported-symbol documentation
completeness.

Java is also an explicit language mode. Read
[`references/java.md`](references/java.md) only for a Java run; it defines the
source-role inventory, lexer boundary, native fixture check, and non-claims.
This extends the preserved `scans: [python, javascript, typescript, go, templates]`
contract with one separately selected Java band.

PHP is an explicit native lexical/syntax mode. The copied helper uses
`token_get_all(..., TOKEN_PARSE)` from PHP >= 8.1.0, inventories excluded roles,
and distinguishes a clean complete scan from incomplete or unavailable
evidence without loading Composer packages.

## How success is judged

- The run is graded only by artifacts: pasted detector/reporter output
  plus `detections.jsonl`, `report.md`, and `findings.json`. Do not
  claim comments were audited without those files.
- The scan verdict is one of `clean`, `advisory-findings`, or
  `scan-blocked`. `advisory-findings` means the report has rows for
  human triage; it does not authorize edits.
- Every summary cites the report artifacts: total findings, bucket
  counts, and the top examples must come from `report.md` or
  `findings.json`, not from memory or preference.
- The skill remains read-only. Preserve, delete, or rewrite comments
  only in a separate cleanup pass after a human selects findings.
- A Go run additionally records analysis status `complete`, `partial`,
  `unsupported`, or `failed` in `scan.json` and `findings.json.analysis.go`.
  Never relabel unreadable eligible source, a missing/old Go tool, or a tool
  failure as a clean scan.
- A Java run records the same status vocabulary in `scan.json` and
  `findings.json.analysis.java`, without depending on a JDK at scan time.
- A PHP run records status plus `advisory-findings`,
  `clean-within-complete`, `incomplete`, `unsupported`, or `failed` outcome in
  `scan.json` and the explicitly selected JSON report. Missing/old PHP and
  native provider failures are never relabeled clean.

## Default Target

If the caller does not provide paths, the current detector uses its
legacy site-workflow default surface:

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
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-comment-drift/scripts/detect.py \
  --output "$REPORT_DIR/detections.jsonl"
.venv/bin/python .claude/skills/find-comment-drift/scripts/report.py \
  "$REPORT_DIR/detections.jsonl" \
  --output "$REPORT_DIR/report.md" \
  --target "legacy default surface"
ln -sfn "$SCAN_ID" reports/find-comment-drift/latest
```

Relative scan paths anchor on `--project-root`, which defaults to the
git toplevel of the cwd (else the cwd) — matching the sibling detectors.
For portable repo scans, pass explicit paths and use the same label in
the reporter:

```
REPORT_DIR="/tmp/find-comment-drift-portable"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-comment-drift/scripts/detect.py \
  --output "$REPORT_DIR/detections.jsonl" \
  .claude/skills/find-comment-drift
.venv/bin/python .claude/skills/find-comment-drift/scripts/report.py \
  "$REPORT_DIR/detections.jsonl" \
  --output "$REPORT_DIR/report.md" \
  --target ".claude/skills/find-comment-drift"
```

When the selected skill has been copied outside the toolkit checkout, invoke
the copied scripts with the host's Python 3.11+ interpreter. No repository
`scripts/`, `_common`, toolkit venv, Node package, or network access is
required:

```
python3 /path/to/find-comment-drift/scripts/detect.py \
  --project-root "$PWD" \
  --output /tmp/comment-drift.jsonl \
  src
python3 /path/to/find-comment-drift/scripts/guard.py \
  --project-root "$PWD" \
  src
```

For a Go 1.22+ host, use the copied on-demand closure and explicit Go mode:

```bash
COMMENT_SKILL="$PWD/.agents/skills/find-comment-drift"
COMMENT_REPORT="$PWD/reports/find-comment-drift/scan-go"
mkdir -p "$COMMENT_REPORT"
python3 "${COMMENT_SKILL}/scripts/detect.py" \
  --project-root "$PWD" --language go \
  --output "$COMMENT_REPORT/detections.jsonl" .
python3 "${COMMENT_SKILL}/scripts/report.py" \
  "$COMMENT_REPORT/detections.jsonl" \
  --output "$COMMENT_REPORT/report.md" --target .
go test ./...
```

The detector discovers `go` from `PATH` and requires Go >= 1.22.0. It writes
`scan.json` beside `detections.jsonl`. The inventory includes every selected Go
file before marking `_test.go`, test trees, generated files/trees/markers,
vendor files, and symlinks ineligible. An invalid UTF-8 or lexically malformed
eligible file makes the analysis `partial`. Ordinary Go parse errors do not:
this contract is lexical and deliberately does not invoke `go/parser`.

If shell process substitution or symlinks are awkward in the current
environment, create the directory with any equivalent safe command. The
required artifacts are:

- `detections.jsonl` - one finding per line.
- `report.md` - grouped human-readable report.
- `findings.json` - machine-readable report summary.
- `scan.json` - Go tool evidence, complete inventory, eligibility reasons, and
  `complete`/`partial`/`unsupported`/`failed` analysis status (Go mode only).

PHP uses the same artifact lifecycle but writes the machine-readable final
artifact to the path passed with `report.py --output-json`; the documented PHP
command uses `reports/find-comment-drift/php-pilot/report.json`.

```bash
COMMENT_SKILL=".agents/skills/on-demand/find-comment-drift"
python3 "${COMMENT_SKILL}/scripts/detect.py" \
  --project-root "$PWD" --language php \
  --output reports/find-comment-drift/php-pilot/detections.jsonl .
python3 "${COMMENT_SKILL}/scripts/report.py" \
  reports/find-comment-drift/php-pilot/detections.jsonl \
  --output reports/find-comment-drift/php-pilot/report.md \
  --output-json reports/find-comment-drift/php-pilot/report.json --target .
php -l path/to/representative.php
```

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
- `jsdoc_candidate`: JavaScript or TypeScript functions, handlers,
  initializers, async workflows, or global helpers that should have real
  JSDoc. This is a lexical review lead, not proof of exported API status.
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

The smoke test scans good/bad Python, JavaScript, TypeScript, TSX, and
HTML/template fixtures and asserts that every detector band has at least one
bad fixture while the good fixtures stay clean.

Use this smoke output as the replay case for detector or contract
repairs. Paste the command output; do not summarize it as "smoke passed"
without the transcript.

## Judgment

Treat findings as a senior-engineer review queue, not a mechanical patch
list. Preserve comments that explain intent, compatibility, safety,
non-obvious history, race conditions, cross-layer contracts, or template
gotchas. Prefer deleting narration over rewriting it. Prefer JSDoc when a
JavaScript function is public-ish, shared, async, global, or has a real
input/output/side-effect contract.

## When things go sideways

| Symptom | Action |
|---|---|
| No explicit paths were passed and the host repo lacks the legacy default files | Mark the verdict `scan-blocked` for the intended target, then re-run with explicit repo-relative paths. Do not treat a zero-file default scan as a clean audit. |
| Detector writes `detections.jsonl` but reporter fails | Keep the JSONL as artifact truth, mark `scan-blocked`, and paste the reporter failure; do not hand-write `report.md`. |
| A finding preserves important intent or safety context | Classify it as `noise` or `keep-comment` in the human summary and cite the adjacent code; do not rewrite it inside this skill. |
| Smoke test fails after detector edits | Stop and fix the detector or fixture expectation before trusting any new report. |
| A malformed file cannot be parsed | Report the parser failure and the file path, then continue only if the detector produced an explicit artifact for the skipped file. |
| Go is missing or older than 1.22.0 | Keep the `unsupported` `scan.json`, install/select Go >= 1.22.0 on `PATH`, and re-run; do not present empty JSONL as clean. |
| A Go file is unreadable or lexically unterminated | Keep the useful findings with `partial` status and cite the failed inventory row; do not silently omit it. |
| A Java file is unreadable or lexically unterminated | Keep useful findings with `partial` status and cite the failed inventory row; Java syntax errors outside the lexer remain valid lexical input. |
| PHP is missing or older than 8.1.0 | Keep the `unsupported` scan/report evidence, select PHP >= 8.1.0, and re-run; the detector never installs PHP or Composer dependencies. |
| PHP syntax or source decoding fails | Keep useful findings with `partial`/`incomplete` evidence and cite the failed inventory row; do not call an empty JSONL clean. |
| The PHP provider process or payload fails | Keep the concrete `failed` evidence, correct the selected runtime/closure, and re-run at the same destination so stale reports cannot survive. |
