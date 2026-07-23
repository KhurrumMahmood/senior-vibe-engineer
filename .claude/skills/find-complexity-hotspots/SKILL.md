---
name: find-complexity-hotspots
description: Detect advisory Python, JavaScript, TypeScript, Go, Java, bounded Rust, and bounded Dart function-complexity hotspots without changing production files. Preserves the Python stdlib AST scan and adds syntax-only family-local high-branch findings for bounded named functions, methods, and constructors.
argument-hint: "<paths> [--language python|javascript|typescript|go|java|rust|dart]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Read-only complexity leads. Python retains nested-loop, membership-scan,
  sort/repeated-scan, Django-query, and high-branch bands. TypeScript/TSX
  reports only per-function syntactic branch complexity with exact source spans
  and analyzer provenance. Go and Java add equally bounded native-parser facts.
not_for: |
  Implementing optimizations, SQL query-plan/index decisions, profiling, or
  benchmark design. TypeScript React/Node/ORM semantics, receiver or
  type claims, import resolution, and expression-bodied arrows are out of
  scope. Broad module-level responsibility sprawl belongs to /find-omnibus.
language: any
framework: any
scans: [python, javascript, typescript, go, java, rust, dart]
---

<!-- Native-parser compatibility subset: scans: [javascript, typescript, go, java] -->
<!-- TypeScript compatibility subset: scans: [python, javascript, typescript] -->

# /find-complexity-hotspots

## Dart v1

Dart v1 consumes the shared `_dart` D3 syntax snapshot and reports named
direct bodies at the frozen score threshold of 18. Nested closures and local
functions do not inflate their owners. The score is advisory syntax evidence,
not runtime or cognitive complexity.

```bash
SKILL_ROOT=".agents/skills/on-demand/find-complexity-hotspots"
python3 "${SKILL_ROOT}/scripts/run_dart.py" \
  --project-root "$PWD" --target lib --facts /tmp/dart-d3-facts.json \
  --output-dir "$PWD/reports/complexity-hotspots/dart"
```

## Rust v1

Rust v1 reports advisory direct-body branch scores for named functions. It
excludes nested functions and braced closures and never infers runtime cost.
The copied closure must include sibling `_rust-syntax`; cfg, macro/build,
generated, and symlink uncertainty prevents a clean result.

```bash
SKILL_ROOT=".agents/skills/on-demand/find-complexity-hotspots"
python3 "${SKILL_ROOT}/scripts/run_rust.py" \
  --project-root "$PWD" --target src \
  --output-dir "$PWD/reports/complexity-hotspots/rust"
```

Run a read-only SUSPECT audit. A finding is a lead worth reading, never a
proof that an optimization is safe or valuable.

## How success is judged

- The final report directory contains `detections.jsonl`, `report.md`, and
  `findings.json`, with `latest` pointing to that run. Go and Java reports also
  state `complete` or `partial` plus their explicit ambiguity or unsupported
  evidence. Do not claim a scan ran without these artifacts.
- Python findings preserve the six established bands. JavaScript, TypeScript,
  Go, and Java findings carry their exact `language`, native analyzer, function
  start/end lines, LOC, and branch score in both JSON artifacts; `report.md`
  prints the analyzer provenance.
- Use one verdict: `no-hotspots`, `measure-first`, `actionable-hotspot`, or
  `scan-blocked`. TypeScript findings are normally `measure-first` until native
  tests and realistic input sizes justify a change.
- This skill never edits source files or claims framework identity, API
  ownership, runtime cost, Java type resolution, or Kotlin/JVM-wide support.

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
- **Go v1:** `.go` named functions and receiver methods using the host Go
  toolchain's standard-library `go/parser` and `go/ast`. It counts `if`,
  `for`, `range`, `switch`, type-switch, `select`, `&&`, and `||` in the direct
  function body only. Nested function literals, imports, calls, interfaces,
  and type/package identity are outside the claim.
- **Go exclusions and ambiguity:** `_test.go`, vendor, generated/gen, fixture,
  build, and report paths are excluded even when directly targeted. Go's
  `Code generated ... DO NOT EDIT.` marker is excluded using `ast.IsGenerated`.
  Explicit `//go:build` or `// +build` files are withheld with
  `build-constraint-ambiguous`, and the final report is `partial`, never clean.
- **Go prerequisite:** a `go` executable on `PATH`, version **Go >= 1.22.0**.
  Missing or older Go, malformed eligible source, or malformed parser output
  stops the run with exit code 2; do not present a previous `latest` report as
  this run's result.
- **Java v1:** `.java` declared methods and constructors using the host JDK
  compiler tree API. It counts `if`, classic/enhanced `for`, `while`, `do`,
  switch statements/expressions, `catch`, ternaries, `&&`, and `||` in the
  direct method body. Nested lambdas and local/anonymous class bodies do not
  contribute to their enclosing method. Methods of local/anonymous classes,
  type resolution, call graphs, framework semantics, build configuration, and
  runtime cost are outside the claim.
- **Java exclusions and mixed source:** test (including Gradle
  `integrationTest` and `testFixtures`), vendor, generated, fixture,
  build/output, report, and symlink paths are excluded even when directly
  targeted. Generated headers and top-level type `@Generated` markers are withheld.
  A target containing only excluded Java source is `partial`, not a clean
  no-hotspot result; Markdown and JSON name the excluded paths.
  Eligible `.kt`/`.kts` files are inventoried as `kotlin_source_present`, make
  the Java result `partial`, and are never presented as Java or JVM support.
- **Java prerequisite:** both `java` and `javac` on `PATH` from **JDK >= 17.0.0**.
  The family-local source launcher batches all eligible `.java` files through
  the public compiler tree API. It does not invoke Maven/Gradle, resolve a
  project classpath, download a JAR, or import a shared analysis platform.
  Missing/old JDK, malformed eligible source, or malformed helper output stops
  the run with exit code 2.

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

Use `--language typescript`, `--language go`, or `--language java` to make a
narrow native-parser contract explicit, or `--language python` to retain the
Python-only scan. The default is additive: it scans supported Python,
JavaScript, TypeScript, Go, and Java files found under `TARGET`.
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
  score. TypeScript, Go, and Java report the same threshold only from their narrow
  syntax lists above, never from calls, receivers, types, interfaces, or
  framework conventions.

## Summarize and act

Report in 10 lines or fewer: total findings and bucket counts; up to three
locations/symbols; the verdict; the `reports/find-complexity-hotspots/latest/`
report path; and one evidence-based next step. Do not optimize cold code or
small collections. For TypeScript, Go, or Java, state the score is syntactic
and name any unknown input size. For Go `partial`, name every build-constraint
ambiguity; for Java `partial`, name the unsupported Kotlin paths.

## Replay check

After changing this skill, run the Python oracle and native outcome suites:

```bash
python3 "${SKILL_ROOT}/scripts/smoke.py"
python3 -m pytest -q tests/test_find_complexity_hotspots_typescript.py
python3 -m pytest -q tests/test_find_complexity_hotspots_go.py
python3 -m pytest -q tests/test_find_complexity_hotspots_java.py
node --check "${SKILL_ROOT}/scripts/detect_typescript_complexity.mjs"
gofmt -d "${SKILL_ROOT}/scripts/detect_go_complexity.go"
java "${SKILL_ROOT}/scripts/detect_java_complexity.java" \
  --project-root "$(pwd)" \
  --file tests/fixtures/find-complexity-hotspots-java/src/main/java/example/CleanService.java
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
| Go parser exits 2 | Stop. Restore `go` on `PATH`, upgrade to Go >= 1.22.0, or repair the eligible syntax; do not present a prior report as the current scan. |
| Go report is partial | Read each `build-constraint-ambiguous` path with its intended build context. This detector does not evaluate tags or claim current-platform reachability. |
| Java parser exits 2 | Stop. Restore a complete JDK >= 17 on `PATH` or repair the eligible syntax; do not present a prior report as the current scan. |
| Java report is partial | Name each `kotlin_source_present` path. Route Kotlin separately; this Java detector does not provide JVM-wide coverage. |
| A high score is on cold/tiny data | Use `measure-first`; no optimization follows from syntax alone. |
| A likely ORM/React/Node/Java-framework issue is absent | This is expected: native-parser v1 intentionally has no framework semantics. Inspect it manually or use a future framework-specific workflow. |
| A direct detector run has JSONL but no report | Run `scripts/run.py` before presenting a verdict. |
