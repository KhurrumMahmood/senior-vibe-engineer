---
name: find-duplication
description: Detect and triage Python structural/lexical duplication with the legacy scout workflow, or report conservative TypeScript/TSX lexical clone evidence. Each language uses a separate family-local pipeline and copied-skill runtime.
argument-hint: "--target <source-directory>"
allowed-tools: Bash, Read, Grep, Glob, Write, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Python/Django copy-paste and canonical-pattern candidates that need the
  established P0/P1/P2 scout triage, or TypeScript/TSX lexical clone
  candidates that need reliable source spans without a consolidation claim.
not_for: |
  Semantic duplication where code differs substantially (use
  /find-semantic-duplication), cross-layer workflow drift, or executing a
  refactor. TypeScript v1 does not prove semantic equivalence or safe reuse.
language: any
framework: any
scans: [python, typescript]
---

# /find-duplication

Run the language branch that matches the target. Python and TypeScript share a
skill name and report vocabulary, but not a detector model or outcome claim.

## Route before running

Inspect eligible source suffixes under `--target`:

- `.py` only: run the **Python legacy triage branch**.
- `.ts`/`.tsx` only: run the **TypeScript lexical-evidence branch**.
- both: run both branches into separate `python/` and `typescript/` report
  directories and summarize them separately. Do not merge their findings or
  apply the Python scout verdict contract to TypeScript evidence.
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

## Mixed targets

For a mixed repository, use one outer scan ID and separate branches:

```text
reports/duplication/<scan-id>/python/...
reports/duplication/<scan-id>/typescript/...
```

Run Python with its AST + scout stages and TypeScript with its conservative
four-stage evidence path. Produce two final reports and summarize them under
their own claims. Do not concatenate their ranked JSON.

## Failure handling

| Symptom | Action |
|---|---|
| Either wrapper exits 2 | Correct the target; it must contain eligible source for that language. |
| Either wrapper exits 3 | Populate the exact offline cache, or for Python only rerun with `--offline-ok` and label the result AST-only/degraded. |
| Invalid/empty or schema-invalid jscpd JSON | Stop. The wrapper removes the unusable report and never marks the scan complete or clean. |
| Python scout JSON is invalid | Re-dispatch; do not pass an unreviewed finding to the final report. |
| TypeScript finding looks safe | Keep the human-review boundary; lexical similarity is not refactor safety. |
| A report names tests, generated, migrations, report, or staging source | Treat it as a detector-boundary defect and stop. |

## Non-goals

- Editing source or executing a refactor.
- Treating dormant code as a primary duplication finding.
- Turning TypeScript lexical evidence into semantic equivalence.
- Creating a shared parser, detector service, or cross-family runtime.
