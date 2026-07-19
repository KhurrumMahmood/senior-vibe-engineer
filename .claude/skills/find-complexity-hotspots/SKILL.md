---
name: find-complexity-hotspots
description: Detect advisory Python and TypeScript function-complexity hotspots without changing production files. Preserves the Python stdlib AST scan for nested loops, membership scans, sort/repeated scans, Django query calls in loops, and high-branch functions; adds syntax-only TypeScript/TSX high-branch findings for function declarations, methods, and block-bodied arrows. Use when a subsystem feels expensive or difficult to follow and a read-only, evidence-backed lead list is needed before measurement or refactoring.
argument-hint: "<paths> [--language python|typescript]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Read-only complexity leads. Python retains nested-loop, membership-scan,
  sort/repeated-scan, Django-query, and high-branch bands. TypeScript/TSX
  reports only per-function syntactic branch complexity with exact source spans
  and analyzer provenance.
not_for: |
  Implementing optimizations, SQL query-plan/index decisions, profiling, or
  benchmark design. TypeScript React/Node/ORM semantics, receiver or
  type claims, import resolution, and expression-bodied arrows are out of
  scope. Broad module-level responsibility sprawl belongs to /find-omnibus.
language: any
framework: any
scans: [python, typescript]
---

# /find-complexity-hotspots

Run a read-only SUSPECT audit. A finding is a lead worth reading, never a
proof that an optimization is safe or valuable.

## How success is judged

- The final report directory contains `detections.jsonl`, `report.md`, and
  `findings.json`, with `latest` pointing to that run. Do not claim a scan ran
  without these artifacts.
- Python findings preserve the six established bands. TypeScript findings carry
  `language: "typescript"`, `analyzer: "typescript-compiler-api"`, function
  start/end lines, LOC, and branch score in both JSON artifacts; `report.md`
  prints the analyzer provenance.
- Use one verdict: `no-hotspots`, `measure-first`, `actionable-hotspot`, or
  `scan-blocked`. TypeScript findings are normally `measure-first` until native
  tests and realistic input sizes justify a change.
- This skill never edits source files or claims a TypeScript receiver type,
  framework identity, API ownership, or runtime cost.

## Scope

- **Target:** one or more explicit files, directories, or globs. There is no
  whole-repository default.
- **Python branch:** the existing stdlib AST detector remains intact: nested
  loops, membership scans, sort/repeated scans, Django QuerySet-like calls in
  loops, and high-branch functions. `--include-tests` affects this branch only.
- **TypeScript v1:** `.ts` and `.tsx` function declarations, methods, and
  block-bodied arrows. It counts only syntactically established counterparts of
  the existing branch invariant: conditionals, loop forms, try/catch, `with`,
  switch, `&&`/`||`, and ternaries. It does not infer data cost from these
  syntax facts.
- **TypeScript exclusions:** React/Node/ORM semantics, receiver or
  type claims, function expressions, expression-bodied arrows, declarations and
  overload signatures without a body, declarations (`.d.ts`), and generated,
  vendor, minified, bundle, test, spec, and fixture paths. These exclusions are
  deliberate even when `--include-tests` is present.
- **TypeScript prerequisite:** Node plus a `typescript` package resolvable from
  the target host's `package.json`. The bundled family-local Compiler API parser
  uses `createSourceFile`, not a tsconfig, Program, TypeChecker, shared parser,
  or fact platform. Missing Node/package, malformed parser output, or TypeScript
  syntax errors stop the run with exit code 2 instead of silently under-detecting.

## Installed command

Set `TARGET` to the requested source directory. Run this resolver verbatim from
the host root; it supports both a stock install and this source checkout.

<!-- installed-command:resolve:start -->
```bash
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/find-complexity-hotspots" \
  ".claude/skills/find-complexity-hotspots"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-complexity-hotspots is not installed in .agents/skills or .claude/skills" >&2
  exit 2
fi
if [ -x ".venv/bin/python" ]; then
  HOST_PYTHON="$(pwd)/.venv/bin/python"
else
  HOST_PYTHON="python3"
fi
```
<!-- installed-command:resolve:end -->

<!-- installed-command:run:start -->
```bash
: "${TARGET:?Set TARGET to a file, directory, or glob to audit}"
"${HOST_PYTHON}" "${SKILL_ROOT}/scripts/run.py" \
  --project-root "$(pwd)" \
  --skip-effectiveness-log \
  "${TARGET}"
```
<!-- installed-command:run:end -->

Use `--language typescript` to make the narrow TypeScript v1 contract
explicit, or `--language python` to retain the Python-only scan. The default is
additive: it scans supported Python and TypeScript files found under `TARGET`.
`--skip-effectiveness-log` is retained for command compatibility; selected-skill
execution has no toolkit telemetry dependency.

For direct detector debugging, write only JSONL:

```bash
"${HOST_PYTHON}" "${SKILL_ROOT}/scripts/detect.py" \
  --project-root "$(pwd)" \
  --output /tmp/complexity-hotspots.jsonl \
  --language typescript \
  "${TARGET}"
```

## Finding buckets

- `django-query-in-loop`, `nested-loop`, `membership-scan-in-loop`,
  `sort-in-loop`, and `repeated-scan-in-loop` are Python-only heuristic leads.
  Preserve filters, authorization, ordering, duplicates, and data-size behavior
  before replacing a loop with a query, map, set, grouping, or batch.
- `high-branch-function` is structural. Python preserves its historical AST
  score. TypeScript reports the same threshold only from the narrow syntax list
  above, never from calls, receivers, types, or framework conventions.

## Summarize and act

Report in 10 lines or fewer: total findings and bucket counts; up to three
locations/symbols; the verdict; the `reports/find-complexity-hotspots/latest/`
report path; and one evidence-based next step. Do not optimize cold code or
small collections. For TypeScript, state the score is syntactic and name any
unknown input size.

## Replay check

After changing this skill, run the Python oracle and TypeScript outcome suite:

```bash
python3 "${SKILL_ROOT}/scripts/smoke.py"
python3 -m pytest -q tests/test_find_complexity_hotspots_typescript.py
node --check "${SKILL_ROOT}/scripts/detect_typescript_complexity.mjs"
```

The locked TypeScript fixture runs `npm ci --offline --ignore-scripts`,
`npm run typecheck` (`tsc --noEmit`), and `npm test`. It proves positive,
clean, generated/vendor/minified/test/spec/declaration exclusions, syntax and
prerequisite failures, copied closure, and stock installation commands.

## When things go sideways

| Symptom | Action |
|---|---|
| No target path was supplied | Let argparse fail, then rerun with explicit paths. |
| TypeScript parser exits 2 | Stop. Install the host's pinned `typescript`, restore Node, or repair the syntax; do not present an incomplete TypeScript scan as clean. |
| A high score is on cold/tiny data | Use `measure-first`; no optimization follows from syntax alone. |
| A likely ORM/React/Node issue is absent | This is expected: TypeScript v1 intentionally has no framework semantics. Inspect it manually or use a future framework-specific workflow. |
| A direct detector run has JSONL but no report | Run `scripts/run.py` before presenting a verdict. |
