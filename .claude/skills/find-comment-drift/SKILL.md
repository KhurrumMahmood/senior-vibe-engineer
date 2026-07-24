---
name: find-comment-drift
description: |
  Advisory SUSPECT scan for comments, docstrings, JSDoc, and template
  comments that have drifted from the code they are meant to clarify.
  Flags detached section banners, narration comments, missing or thin
  public class docstrings, stale terminology, JavaScript and TypeScript
  functions that deserve real JSDoc, thin ceremonial JSDoc, noisy HTML
  comments, fragile doc references, bounded Go, Java, Kotlin/JVM, PHP, Ruby,
  Swift, Rust, C, and C++ lexical-comment surfaces, and bounded Dart adjacent-doc/fixed-return
  syntax.
argument-hint: "[paths... | --scan-request FILE - no scope uses the legacy default surface]"
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
scans: [python, javascript, typescript, go, java, kotlin, php, ruby, swift, rust, dart, c, cpp, templates]
---

# /find-comment-drift

## Kotlin/JVM 2.4.10 branch

Trigger this branch only for manifest-selected authored `.kt` comments. Keep
sibling `_kotlin`, read [`../_kotlin/GUIDE.md`](../_kotlin/GUIDE.md), and enter
through `scripts/analyze_comments_kotlin.py`. It emits four lexical hygiene
bands with exact comment spans and final advisory/clean artifacts. It does not
associate comments with declarations or prove semantic/runtime drift; strings,
tests, generated/vendor/build/tooling/symlink inputs, `.kts`, Java,
annotations, plugins, Gradle variants, reflection, frameworks, and behavior
remain outside the claim.

## Dart v1

Dart v1 reports one deliberately narrow advisory shape: an adjacent `///`
percentage/rate claim whose named top-level function directly returns a
conflicting fixed numeric literal. Copy sibling `_dart/scripts` and its locked
public-analyzer tool; missing offline dependencies remain partial and never
trigger a download or host Pub operation.

```bash
SKILL_ROOT=".agents/skills/on-demand/find-comment-drift"
python3 "${SKILL_ROOT}/scripts/analyze_comments_dart.py" \
  --project-root "$PWD" --target . \
  --output-dir "$PWD/reports/find-comment-drift/dart" \
  --native-test "${DART_DIRECT_TEST:?Set a dependency-free direct test path}" \
  --smoke "${DART_SMOKE:?Set a direct smoke entrypoint}" \
  --smoke-stdout "${DART_EXPECTED_STDOUT:?Set exact stdout including any newline}"
```

Computed values, inherited docs, nested closures, data flow, generated code,
and runtime correctness remain outside this rule.

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

Ruby uses the copied `scripts/analyze_comments_ruby.py` entry point. Ruby 3.3+
Prism supplies exact comment locations and `ruby -c` gates syntax for every
eligible `.rb` or Ruby-shebang source. The bounded behavior-drift rule reports
only an adjacent percentage-calculation comment contradicted by a fixed numeric
method body; it does not infer runtime behavior through reopening,
metaprogramming, reflection, dynamic loading, Rails, or Zeitwerk.

Swift uses the external-library provider. Load the selected skill with sibling
`_swift-project-lexical`, then read
[`../_swift-project-lexical/GUIDE.md`](../_swift-project-lexical/GUIDE.md) for
the exact command, restrictive native gates, bounded adjacent-comment rule,
and semantic non-claims.

Rust uses the copied `scripts/analyze_comments_rust.py` entry point. Rust/Cargo
1.85+ and rustfmt gate a locked offline workspace plus every eligible `.rs`
input. Its bounded behavior rule reports only an adjacent percentage/rate doc
comment contradicted by a fixed numeric function body. Macros, build scripts,
`include!`, cfg/target variants, traits, generics, unsafe/FFI, and runtime
dispatch remain explicit non-claims.

C is a separate copied-helper mode rather than a branch of the legacy
detector. `scripts/analyze_comments_c.py` uses Clang 21+ raw tokens and exact
source bytes over `.c`/`.i` files. Headers are eligible only when a current,
complete C17 `compile_commands.json` proves they belong to the selected
translation-unit dependency closure. The result is lexical: macro expansion,
inactive branches, comment-to-symbol meaning, C++, Objective-C, and framework
conventions are explicit non-claims.

C++ is selected through the copied `scripts/analyze_comments_cpp.py` entry
point. It applies the same bounded Clang 21+ raw-token evidence contract to
C++20 `.cpp`, `.cc`, `.cxx`, `.c++`, `.C`, and `.ii` translation units. Common
C++ header and template suffixes (`.h`, `.hpp`, `.hh`, `.hxx`, `.h++`, `.inc`,
`.ipp`, `.inl`, and `.tpp`) are eligible only when a current, complete C++20
`compile_commands.json` proves dependency ownership. A conservative byte scan
rejects malformed or truncated raw-token output; only Clang comment tokens
produce findings. Macro expansion, inactive branches, comment-to-symbol
meaning, Objective-C++, CUDA, module interfaces, and framework conventions
remain explicit non-claims.

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
- A Ruby run records `complete`, `partial`, `unsupported`, or `failed` in
  `scan.json` and `findings.json`. Missing/old Ruby, Prism/provider failures,
  syntax-invalid eligible inputs, and unreadable sources are never relabeled
  clean. Exact source, artifact, and finding hashes make stale output visible.
- A Rust run records `complete`, `partial`, or `failed` plus
  `advisory-findings`, `clean-within-complete`, or `incomplete` in all four
  artifacts. Missing/old tools and syntax-incomplete inputs remain `partial`,
  never a permanent unsupported language claim or an empty clean result.
- A C run records `complete`, `partial`, `unsupported`, or `failed` plus a
  final `findings.json`. Missing/old Clang, ambiguous headers, stale/incomplete
  compile commands, syntax failures, and provider failures remain visible.
- A C++ run records the same terminal status and final artifact. It must report
  C++20 compile-database ownership, exact raw-token source spans, source hashes,
  and whether evidence is lexical only. Validate a durable artifact with
  `analyze_comments_cpp.py --verify-artifact`; stale source, manifest, spelling,
  or finding hashes are rejected rather than presented as current evidence.

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

When `/which-cleanup` supplies a `scan_request`, write that exact JSON object to
a bounded file and pass it with `--scan-request`. `diff-lines` scans each
selected file once for syntactic correctness, then filters the resulting
line/range findings; `changed-files` keeps findings from the complete selected
files. The sibling `<detections-stem>-scope.json` records requested/effective
mode, selector, analyzed files, raw findings, filtered findings, and incomplete
or error counts.
Content-basis drift refuses `diff-lines`; explicitly use `changed-files`
instead of applying historical or staged line numbers to different bytes.

```bash
python3 /path/to/find-comment-drift/scripts/detect.py \
  --project-root "$PWD" \
  --scan-request /tmp/which-cleanup-scan-request.json \
  --output /tmp/comment-drift.jsonl
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
- `scan.json` - selected-language tool evidence, complete inventory,
  eligibility reasons, and `complete`/`partial`/`unsupported`/`failed` status
  for copied-helper modes that publish it.

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

For a C17 host, run the copied helper directly. The host owns Clang and its
compile database; this skill installs neither.

```bash
COMMENT_SKILL=".agents/skills/on-demand/find-comment-drift"
COMMENT_REPORT="reports/find-comment-drift/c-pilot"
mkdir -p "${COMMENT_REPORT}"
python3 "${COMMENT_SKILL}/scripts/analyze_comments_c.py" \
  --project-root "$PWD" --clang "$(command -v clang)" \
  --output "${COMMENT_REPORT}/detections.jsonl" .
make test
```

The helper writes `detections.jsonl`, `scan.json`, `report.md`, and
`findings.json` atomically and preserves selected source bytes.

For a C++20 host, use the copied C++ entry point. The host owns Clang, its
compile database, and the native build; this skill installs none of them.

```bash
COMMENT_SKILL=".agents/skills/on-demand/find-comment-drift"
COMMENT_REPORT="reports/find-comment-drift/cpp"
mkdir -p "${COMMENT_REPORT}"
python3 "${COMMENT_SKILL}/scripts/analyze_comments_cpp.py" \
  --project-root "$PWD" --clang "$(command -v clang)" \
  --output "${COMMENT_REPORT}/detections.jsonl" .
python3 "${COMMENT_SKILL}/scripts/analyze_comments_cpp.py" \
  --project-root "$PWD" \
  --verify-artifact "${COMMENT_REPORT}/findings.json"
make test
```

The analyzer removes all four old destination artifacts before a run and
rewrites terminal evidence atomically. The verifier recomputes every inventoried
source hash, the inventory manifest hash, and each finding's source spelling
hash before accepting the report as current.

For a Ruby 3.3+ host, run the copied Ruby helper directly. The host owns Ruby;
the skill installs no gem and requires no application dependency.

```bash
COMMENT_SKILL=".agents/skills/on-demand/find-comment-drift"
COMMENT_REPORT="reports/find-comment-drift/ruby"
mkdir -p "${COMMENT_REPORT}"
python3 "${COMMENT_SKILL}/scripts/analyze_comments_ruby.py" \
  --project-root "$PWD" --ruby "$(command -v ruby)" \
  --output "${COMMENT_REPORT}/detections.jsonl" .
ruby -c path/to/representative.rb
```

The helper atomically writes `detections.jsonl`, `scan.json`, `findings.json`,
and `report.md`; selected source bytes remain unchanged.

For a Rust 1.85+ Cargo host, run the copied Rust helper directly. The host owns
Rust, Cargo, rustfmt, the lockfile, and native checks; the skill installs
nothing and uses offline/locked commands.

```bash
COMMENT_SKILL=".agents/skills/on-demand/find-comment-drift"
COMMENT_REPORT="reports/find-comment-drift/rust"
mkdir -p "${COMMENT_REPORT}"
python3 "${COMMENT_SKILL}/scripts/analyze_comments_rust.py" \
  --project-root "$PWD" \
  --rustc "$(command -v rustc)" \
  --cargo "$(command -v cargo)" \
  --rustfmt "$(command -v rustfmt)" \
  --output "${COMMENT_REPORT}/detections.jsonl" .
cargo test --locked --offline --workspace --all-targets --all-features
```

The helper atomically replaces `detections.jsonl`, `scan.json`,
`findings.json`, and `report.md`, records exact source/finding/manifests hashes,
and preserves selected source bytes.

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
| Ruby is missing/older than 3.3, Prism fails, or an eligible file is syntax-invalid | Keep the explicit `unsupported`, `failed`, or `partial` artifacts, correct the host runtime/source, and re-run at the same destination; do not present empty findings as clean. |
| Rust/Cargo is missing or older than 1.85, rustfmt is unavailable, or an eligible file is syntax-invalid | Keep the explicit `partial` artifacts, correct the host toolchain/source, and re-run at the same destination; do not call the Rust skill unsupported or present empty findings as clean. |
| Clang is missing or older than 21.0.0 for C/C++ | Keep the `unsupported` final artifacts, select a supported host-owned Clang, and re-run; do not present empty detections as clean. |
| C/C++ compile commands are missing, malformed, incomplete, or stale | Source translation units may still have bounded lexical evidence, but keep unowned headers `ambiguous-header`; do not infer ownership from directory names. |
| C/C++ syntax fails or Clang raw-token output is malformed/incomplete | Keep the explicit `partial`/`failed` evidence and failed inventory rows. Fix the source/tool invocation and re-run the same destination; never reuse the prior report. |
| C++ sources changed after the report | Run `analyze_comments_cpp.py --verify-artifact`; a nonzero result makes the report stale and requires a fresh analysis. |
