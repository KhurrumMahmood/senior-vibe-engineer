---
name: find-duplication
description: Detect and triage Python structural/lexical duplication with the legacy scout workflow, or report conservative JavaScript-family, TypeScript/TSX, exact Go function-body, and exact Java method-body clone evidence. Each language uses a separate family-local pipeline and copied-skill runtime.
argument-hint: "--target <source-directory>"
allowed-tools: Bash, Read, Grep, Glob, Write, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Python/Django copy-paste and canonical-pattern candidates that need the
  established P0/P1/P2 scout triage, JavaScript-family/TypeScript lexical clone
  candidates that need reliable source spans, exact normalized Go function-body
  clones, or duplicated Java method bodies represented as exact normalized
  method-body clone candidates for conservative human review.
not_for: |
  Behavior-level matches whose implementations differ structurally belong to
  /find-semantic-duplication. Cross-layer workflow drift and refactor execution
  are outside this detector. Family-local v1 evidence establishes structural
  clone leads and stops short of safety or reuse conclusions.
language: any
framework: any
scans: [python, javascript, typescript, go, java]
---

# /find-duplication

Run the language branch that matches the target. Python, JavaScript, TypeScript, Go, and Java share a
skill name and report vocabulary, but not a detector model or outcome claim.

## Route before running

Inspect eligible source suffixes under `--target`:

- `.py` only: run the **Python legacy triage branch**.
- `.ts`/`.tsx` only: run the **TypeScript lexical-evidence branch**.
- `.js`/`.jsx`/`.mjs`/`.cjs` only: run the **JavaScript lexical-evidence branch**.
- `.go` only: run the **Go exact-function evidence branch**.
- `.java` only: run the **Java exact-method evidence branch**.
- multiple supported families: run each branch into its own language report
  directory and summarize them separately. Do not merge their findings or
  apply one family's outcome contract to another family's evidence.
- neither: stop and report that this skill has no eligible source.

Use a host Python 3.11+ interpreter. The selected skill is self-contained: no
repository-level `scripts/`, `_common`, toolkit virtualenv, or shared language
adapter is part of either installed path.

## Python legacy triage branch

The Python branch preserves the original user journey: pinned lexical
detection plus Python AST pattern detection, method-identity collapse, ranking,
per-finding scout investigation, a dormant-code side-channel, and final
`triage.md`/`findings.json` suitable for `/fix-workflow` handoff.

### Python success contract

- Every final finding was present in `ranked.json` and has a valid scout JSON
  in `scout/<finding_id>.json` before it becomes actionable.
- `classified.json` preserves all scout verdicts and dormant candidates.
- `triage.md` and `findings.json` include the same `fix_shape`, notes, latent
  bug risk, and side-channel evidence.
- Production source is unchanged.

### Python setup

```bash
PYTHON="${PYTHON:-python3}"
SKILL_ROOT="${SKILL_ROOT:-.claude/skills/find-duplication}"
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/duplication/${SCAN_ID}"
TARGET="src"
NPM_CACHE="${NPM_CACHE:-/tmp/engineering-skills-jscpd-cache}"
RUN_PY_JSCPD="$SKILL_ROOT"/scripts/run_jscpd_python.py
DETECT_PY="$SKILL_ROOT"/scripts/detect_python.py
COLLAPSE_PY="$SKILL_ROOT"/scripts/collapse.py
RANK="$SKILL_ROOT"/scripts/rank.py
REPORT="$SKILL_ROOT"/scripts/report.py
mkdir -p "$REPORT_DIR/jscpd" "$REPORT_DIR/scout"
```

### Python Stage 1 — detect

Run the two family-local commands. They are independent and may run in
parallel. `--offline-ok` preserves the legacy AST-only degraded mode when the
exact jscpd cache is absent; the resulting report says `skipped_lexical` and
must never be described as a clean lexical scan.

```bash
"$PYTHON" "$RUN_PY_JSCPD" \
  --target "$TARGET" \
  --output "$REPORT_DIR/jscpd" \
  --npm-cache "$NPM_CACHE" \
  --offline-ok

"$PYTHON" "$DETECT_PY" "$TARGET" \
  --project-root "$PWD" \
  --output "$REPORT_DIR/ast-findings.json"
```

The lexical wrapper pins `jscpd@4.0.5`, runs `npx --offline`, stages only
eligible production `.py` files, and excludes tests, migrations, vendor,
generated, report, output, and prior `.jscpd-input` trees. The AST detector is
stdlib-only and retains the legacy categories: unsafe request integer parsing,
shadow safe-conversion helpers, repeated LLM-call helpers, inline request-body
JSON parsing, and same-name/same-arity cross-module candidates.

### Python Stage 2 — collapse

```bash
"$PYTHON" "$COLLAPSE_PY" \
  --jscpd-report "$REPORT_DIR/jscpd/jscpd-report.json" \
  --ast-findings "$REPORT_DIR/ast-findings.json" \
  --target "$TARGET" \
  --project-root "$PWD" \
  --output "$REPORT_DIR/collapsed.json"
```

Expected stderr begins with `[collapse]`. Default filters remove tests,
migrations, vendor/framework boilerplate, reports, and staging input. Python
enclosing-symbol mapping uses stdlib `ast` inside the copied skill.

### Python Stage 3 — rank

```bash
"$PYTHON" "$RANK" \
  --input "$REPORT_DIR/collapsed.json" \
  --output "$REPORT_DIR/ranked.json"
```

This preserves the original multiplicity × divergence × blast-radius ranking
and P0/P1/P2 tiers.

### Python Stage 4 — investigate

This is the only Python stage where LLM judgment runs. Investigate the top 10
ranked findings by default (or all when fewer exist). For each finding:

1. Expand `agents/investigate.md` with `finding_id`, the finding JSON,
   `project_root`, `skill_root`, and `output_path`.
2. Dispatch a fresh general-purpose sub-agent. Dispatch independent scouts in
   parallel when the host supports it.
3. Require the scout to read `knowledge/false-positives.md`, any host overlay,
   and `knowledge/learnings.md` when ambiguity matches a precedent.
4. Accept only schema-valid JSON using one documented `fix_shape`. Re-dispatch
   malformed output; never silently promote an unreviewed finding.

Merge the accepted scout files:

```bash
"$PYTHON" -c '
import glob, json, pathlib, sys
report = pathlib.Path(sys.argv[1])
out = {"findings": [], "dormant_candidates": []}
for name in sorted(glob.glob(str(report / "scout" / "*.json"))):
    data = json.loads(pathlib.Path(name).read_text())
    out["findings"].append(data)
    out["dormant_candidates"].extend(data.get("dormant_candidates") or [])
(report / "classified.json").write_text(json.dumps(out, indent=2) + "\n")
' "$REPORT_DIR"
```

### Python Stage 5 — final report

```bash
"$PYTHON" "$REPORT" \
  --input "$REPORT_DIR/ranked.json" \
  --classified "$REPORT_DIR/classified.json" \
  --output-md "$REPORT_DIR/triage.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID"
ln -sfn "$SCAN_ID" reports/duplication/latest
```

The final report preserves the original scout `fix_shape`, notes, latent bug
risk, `/fix-workflow cluster:<finding_id>` handoff, and dormant-code
side-channel. Summarize counts by shape, the top three clusters, latent risks,
the final artifact path, and the recommended next command in at most 10 lines.

## TypeScript lexical-evidence branch

TypeScript v1 reports only lexical or near-lexical clone clusters where each
complete site range fits one proven function declaration or block-bodied arrow
symbol. It excludes generated, tests, declarations, vendor, dependencies,
build, report, output, and staging paths. Distinct occurrences remain distinct;
raw pairs cluster only through overlapping occurrences.

This branch has no TypeScript type checker, module resolution, React/Node
framework model, caller proof, or refactor-safety claim. It does not run Python
scouts or hand findings directly to `/fix-workflow`.

### TypeScript setup and pipeline

Provision the exact cache deliberately outside the audit when needed:

```bash
NPM_CONFIG_CACHE="/path/to/jscpd-cache" npx --yes jscpd@4.0.5 --version
```

Then run all four installed stages:

```bash
PYTHON="${PYTHON:-python3}"
SKILL_ROOT="${SKILL_ROOT:-.claude/skills/find-duplication}"
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/duplication/${SCAN_ID}"
TARGET="src"
NPM_CACHE="${NPM_CACHE:-/tmp/engineering-skills-jscpd-cache}"
RUN_TS_JSCPD="$SKILL_ROOT"/scripts/run_jscpd.py
COLLAPSE_TS="$SKILL_ROOT"/scripts/collapse_typescript.py
RANK="$SKILL_ROOT"/scripts/rank.py
REPORT="$SKILL_ROOT"/scripts/report.py
mkdir -p "$REPORT_DIR/jscpd"

"$PYTHON" "$RUN_TS_JSCPD" \
  --target "$TARGET" --output "$REPORT_DIR/jscpd" --npm-cache "$NPM_CACHE"
"$PYTHON" "$COLLAPSE_TS" \
  --jscpd-report "$REPORT_DIR/jscpd/jscpd-report.json" \
  --target "$TARGET" --project-root "$PWD" \
  --output "$REPORT_DIR/collapsed.json"
"$PYTHON" "$RANK" \
  --input "$REPORT_DIR/collapsed.json" --output "$REPORT_DIR/ranked.json"
"$PYTHON" "$REPORT" \
  --input "$REPORT_DIR/ranked.json" \
  --output-md "$REPORT_DIR/triage.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID"
ln -sfn "$SCAN_ID" reports/duplication/latest
```

Required artifacts are `jscpd/jscpd-report.json`, `collapsed.json`,
`ranked.json`, `triage.md`, and `findings.json`. The final Markdown repeats
“Do not consolidate automatically.” A nonempty cluster is an investigation
lead only. `unmapped_symbol`, `span_crosses_symbol_boundary`, overload, and
excluded-path omissions are deliberate false-negative boundaries.

## JavaScript lexical-evidence branch

JavaScript v1 accepts `.js`, `.jsx`, `.mjs`, and `.cjs` only through an
explicit project-local `jscpd` binary. It never runs npm or npx and never
installs a tool. The runner emits `run.json` with `tool-missing`,
`syntax-error`, `tool-failed`, or `partial` when an established final clone
report cannot be produced; none of those outcomes is clean.

The collapse pass retains a reported pair only when both spans fit a named
function or block-bodied arrow. It excludes generated, minified, test, vendor,
dependency, report, staging, and symlink paths and maps source lines from the
original host files. The final `triage.md` says “Do not consolidate automatically”; it is lexical evidence, not a behavior, caller, or semantic equivalence conclusion.

```bash
PYTHON="${PYTHON:-python3}"
RUN_JS_JSCPD="$SKILL_ROOT"/scripts/run_jscpd_javascript.py
COLLAPSE_JS="$SKILL_ROOT"/scripts/collapse_javascript.py
JSCPD_BIN="$PWD/node_modules/.bin/jscpd"

"$PYTHON" "$RUN_JS_JSCPD" --target "$TARGET" --project-root "$PWD" --output "$REPORT_DIR/jscpd" \
  --jscpd-bin "$JSCPD_BIN" || exit $?
"$PYTHON" "$COLLAPSE_JS" --jscpd-report "$REPORT_DIR/jscpd/jscpd-report.json" \
  --target "$TARGET" --project-root "$PWD" --output "$REPORT_DIR/collapsed.json" || exit $?
"$PYTHON" "$RANK" --input "$REPORT_DIR/collapsed.json" --output "$REPORT_DIR/ranked.json" || exit $?
"$PYTHON" "$REPORT" --input "$REPORT_DIR/ranked.json" \
  --output-md "$REPORT_DIR/triage.md" --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID"
```

## Go exact-function evidence branch

Go v1 uses Go 1.22+ from `PATH` and one batched `go run` of the bundled
`go/parser` standard-library helper. It fingerprints `go/format`-normalized
bodies of named functions and receiver methods with at least five source lines, then
retains only fingerprints occurring at two or more symbols. This is exact
structural evidence, not semantic equivalence, caller proof, or a safe-reuse
recommendation.

The source inventory is project-root-relative and excludes `_test.go`,
generated, test/testdata/fixture, vendor, dependency, report, and build-output
trees even when one is targeted directly or through a symlink. Generated files
are excluded before build classification. Explicit build tags and implicit
GOOS/GOARCH filename constraints make an otherwise useful result `partial`;
malformed source, missing/old Go, or invalid helper evidence is `failed` or
`unsupported`, never clean.

```bash
PYTHON="${PYTHON:-python3}"
SKILL_ROOT="${SKILL_ROOT:-.claude/skills/find-duplication}"
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/duplication/${SCAN_ID}"
mkdir -p "$REPORT_DIR"

"$PYTHON" "${SKILL_ROOT}/scripts/run_go.py" \
  --target src --project-root "$PWD" --output "$REPORT_DIR/collapsed.json"
"$PYTHON" "${SKILL_ROOT}/scripts/rank.py" \
  --input "$REPORT_DIR/collapsed.json" --output "$REPORT_DIR/ranked.json"
"$PYTHON" "${SKILL_ROOT}/scripts/report.py" \
  --input "$REPORT_DIR/ranked.json" \
  --output-md "$REPORT_DIR/triage.md" \
  --output-json "$REPORT_DIR/findings.json" --scan-id "$SCAN_ID"
```

The final Markdown says “Do not consolidate automatically.” Review both bodies
and their callers before proposing a refactor.

## Java exact-method evidence branch

Java v1 uses `java` and `javac` from JDK 17+ and one batched source-launcher
invocation of the family-local JDK compiler-tree helper. It fingerprints the
normalized bodies of direct methods and constructors on named top-level types
when the complete declaration spans at least five lines. Exact fingerprints at
two or more symbols become review leads; this is not semantic equivalence,
caller proof, type resolution, inheritance analysis, or a safe-reuse claim.

Tests, generated source, fixtures, vendor/dependency, report, and build-output
trees are excluded. The parser does not run annotation processors or infer
Lombok/framework-generated members. Malformed source, missing/old JDK, or
invalid helper evidence is `failed`/`unsupported`, never clean.

```bash
PYTHON="${PYTHON:-python3}"
SKILL_ROOT="${SKILL_ROOT:-.claude/skills/find-duplication}"
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/duplication/${SCAN_ID}"
mkdir -p "$REPORT_DIR"

"$PYTHON" "${SKILL_ROOT}/scripts/run_java.py" \
  --target src --project-root "$PWD" --output "$REPORT_DIR/collapsed.json"
"$PYTHON" "${SKILL_ROOT}/scripts/rank.py" \
  --input "$REPORT_DIR/collapsed.json" --output "$REPORT_DIR/ranked.json"
"$PYTHON" "${SKILL_ROOT}/scripts/report.py" \
  --input "$REPORT_DIR/ranked.json" --output-md "$REPORT_DIR/triage.md" \
  --output-json "$REPORT_DIR/findings.json" --scan-id "$SCAN_ID"
```

The final Markdown retains “Do not consolidate automatically.” Review the
matched bodies and their callers before proposing any refactor.

## Mixed targets

For a mixed repository, use one outer scan ID and separate branches:

```text
reports/duplication/<scan-id>/python/...
reports/duplication/<scan-id>/typescript/...
reports/duplication/<scan-id>/javascript/...
reports/duplication/<scan-id>/java/...
```

Run Python with its AST + scout stages and JavaScript/TypeScript with their
conservative evidence paths. Produce separate final reports and summarize them under
their own claims. Do not concatenate their ranked JSON.

## Failure handling

| Symptom | Action |
|---|---|
| Either wrapper exits 2 | Correct the target; it must contain eligible source for that language. |
| Either wrapper exits 3 | Populate the exact offline cache, or for Python only rerun with `--offline-ok` and label the result AST-only/degraded. |
| Invalid/empty or schema-invalid jscpd JSON | Stop. The wrapper removes the unusable report and never marks the scan complete or clean. |
| Python scout JSON is invalid | Re-dispatch; do not pass an unreviewed finding to the final report. |
| TypeScript finding looks safe | Keep the human-review boundary; lexical similarity is not refactor safety. |
| JavaScript runner says `tool-missing`, `syntax-error`, `tool-failed`, or `partial` | Preserve `run.json` and report that outcome; do not synthesize a clean clone result. |
| Java helper reports malformed source or the JDK is missing/old | Preserve the failure; do not render or claim a clean scan. |
| A report names tests, generated, migrations, report, or staging source | Treat it as a detector-boundary defect and stop. |

## Non-goals

- Editing source or executing a refactor.
- Treating dormant code as a primary duplication finding.
- Turning TypeScript lexical evidence into semantic equivalence.
- Turning JavaScript lexical evidence into semantic equivalence.
- Turning exact Java body fingerprints into semantic equivalence or safe reuse.
- Creating a shared parser, detector service, or cross-family runtime.
