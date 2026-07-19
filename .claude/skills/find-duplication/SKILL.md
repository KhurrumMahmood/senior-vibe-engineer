---
name: find-duplication
description: Report TypeScript/TSX lexical or near-lexical clone clusters with pinned offline jscpd evidence, reliable source spans, and conservative enclosing-symbol names. The triage is read-only and never claims that consolidation is safe.
argument-hint: "--target <TypeScript-source-directory>"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  TypeScript or TSX copy/paste candidates whose repeated text is substantial
  enough for a lexical detector. Produces a durable triage report for human
  investigation, including source ranges and the enclosing symbols that the
  family-local mapper can establish reliably.
not_for: |
  Semantic duplication, equivalence, safe extraction, or automated
  consolidation. This v1 does not resolve imports, understand framework
  conventions, prove overload compatibility, or make a refactoring proposal.
language: typescript
framework: any
scans: [typescript]
---

# /find-duplication

Run a read-only TypeScript lexical-duplication audit. The outcome is evidence,
not a change plan: every result names jscpd spans and the enclosing symbols the
mapper could prove, but no result establishes that two implementations have the
same behavior or can safely be merged.

## TypeScript v1 contract

This revision reports only TypeScript/TSX lexical or near-lexical clone clusters
where both clone-site endpoints fit the same reliable source range and an
enclosing function or block-bodied arrow symbol. It deliberately drops a jscpd
pair when either site cannot be mapped confidently. It also excludes generated, test, declaration,
vendor, build, and `node_modules` paths before jscpd runs, then applies the same
boundary defensively while collapsing a report. Overload signatures are never
triage findings.

The scanner has no TypeScript type-checker, module-resolution, React, Node, or
framework claim. It does not compare behavior, public API compatibility,
exception policy, side effects, caller context, or ownership. “Lexical clone”
means duplicated detector text, not “safe to consolidate.”

Python remains a frozen stdlib reference replay for the pre-existing collapse
shape. The installed router should advertise this revision as TypeScript-only;
the reference replay does not earn a broader routing claim.

## Required result

The run is complete only when all of these artifacts exist under the chosen
report directory:

- `jscpd/jscpd-report.json` — the pinned tool output after paths are restored
  from the disposable staging tree to the host source tree.
- `collapsed.json` and `ranked.json` — deterministic lexical clusters with
  filtering/accounting metadata. Distinct source occurrences remain distinct;
  pairs join a cluster only through overlapping occurrences.
- `triage.md` and `findings.json` — the final user-facing and structured
  artifacts. The Markdown repeats the no-automatic-consolidation boundary.

The audit must not modify source files. The jscpd staging copy and report files
are audit artifacts, not host-source changes.

## Offline pinned dependency

The family-local wrapper invokes exactly `jscpd@4.0.5` with `npx --offline` and
`NPM_CONFIG_OFFLINE=true`. It never falls back to the network. A missing cache
returns status 3 with a clear preflight error. Before an offline scan, populate
the chosen npm cache deliberately using stock npm in an environment where a
network install is allowed, then keep the scan itself offline:

```bash
NPM_CONFIG_CACHE="/path/to/jscpd-cache" \
  npx --yes jscpd@4.0.5 --version
```

The cache location is explicit runtime input, not a repository dependency. The
selected skill carries no repository `scripts/`, `_common`, toolkit virtualenv,
or generic executor dependency. See `knowledge/typescript-v1.md` for the tool
decision and rejected alternatives.

## Pipeline

From the TypeScript host project, set the installed skill path explicitly. Use
the host's Python 3.11+ interpreter; use this repository's `.venv/bin/python`
only while validating the source checkout.

```bash
PYTHON="${PYTHON:-python3}"
SKILL_ROOT="${SKILL_ROOT:-.claude/skills/find-duplication}"
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/duplication/${SCAN_ID}"
TARGET="src"
NPM_CACHE="${NPM_CACHE:-/tmp/engineering-skills-jscpd-cache}"
RUN_JSCPD="$SKILL_ROOT"/scripts/run_jscpd.py
COLLAPSE_TYPESCRIPT="$SKILL_ROOT"/scripts/collapse_typescript.py
RANK="$SKILL_ROOT"/scripts/rank.py
REPORT="$SKILL_ROOT"/scripts/report.py

mkdir -p "$REPORT_DIR/jscpd"
"$PYTHON" "$RUN_JSCPD" \
  --target "$TARGET" \
  --output "$REPORT_DIR/jscpd" \
  --npm-cache "$NPM_CACHE"
"$PYTHON" "$COLLAPSE_TYPESCRIPT" \
  --jscpd-report "$REPORT_DIR/jscpd/jscpd-report.json" \
  --target "$TARGET" \
  --project-root "$PWD" \
  --output "$REPORT_DIR/collapsed.json"
"$PYTHON" "$RANK" \
  --input "$REPORT_DIR/collapsed.json" \
  --output "$REPORT_DIR/ranked.json"
"$PYTHON" "$REPORT" \
  --input "$REPORT_DIR/ranked.json" \
  --output-md "$REPORT_DIR/triage.md" \
  --output-json "$REPORT_DIR/findings.json" \
  --scan-id "$SCAN_ID"
ln -sfn "$SCAN_ID" reports/duplication/latest
```

Run all four stages. Do not render a new triage from stale intermediate files
after a failed offline detector preflight.

## How to read the result

- A nonempty cluster means the pinned lexical detector found repeated text and
  the mapper located both spans inside named symbols. Read both bodies and
  callers before deciding whether they even represent the same concept.
- An empty report means no eligible lexical clone reached this detector’s
  threshold. It does not prove the code is free of semantic duplication.
- A pair omitted as `unmapped_symbol` is intentionally not promoted to a
  cluster; TypeScript v1 prefers a false negative to a fabricated symbol name.
- A pair omitted as `span_crosses_symbol_boundary` crossed or escaped its
  start symbol, so its range cannot support a reliable owner claim.
- Generated/test/declaration/overload exclusions are false-positive boundaries,
  not evidence that such code is never duplicated.

## Failure handling

| Symptom | Action |
|---|---|
| Wrapper exits 3 | Populate the exact `jscpd@4.0.5` npm cache explicitly, then retry. Do not turn on a silent network fallback. |
| Wrapper exits 2 | Correct the target: it must be a directory with eligible `.ts` or `.tsx` files. |
| Wrapper reports an unexpected jscpd schema | Treat the detector run as failed. The wrapper removes the unusable report and never marks it complete or clean. |
| Collapse reports mapped finding count 0 | Read `filter_reasons` in `collapsed.json`; do not substitute module-level or guessed symbols. |
| A report names a generated/test/declaration path | Stop and treat it as a detector-boundary defect; do not triage it. |
| A cluster looks safe at a glance | Treat that as an investigation lead only. TypeScript v1 has made no semantic or refactor-safety determination. |

## Non-goals

- Modifying source, generating codemods, or dispatching a refactor.
- Type checking, import resolution, call-graph analysis, or semantic cloning.
- Inventing a shared TypeScript parser/executor platform for another skill.
- Downloading dependencies during an audit.
