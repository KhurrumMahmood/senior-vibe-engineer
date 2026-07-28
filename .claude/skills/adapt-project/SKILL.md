---
name: adapt-project
description: Discover objective host-project facts and scaffold a project adapter for engineering-skills. Reads Python, JavaScript-family, TypeScript, Go, Java, bounded Kotlin/JVM, PHP/Composer, bounded plain-Ruby/Bundler, SwiftPM, Cargo/Rust, and plain-Dart stack/source markers plus commands, tests, CI, docs, domain terms, sensitive surfaces, existing guardrails, and skill overlays; writes adapter artifacts under reports/adapt-project/scan-<TS>/ by default. Host writes to .engineering/project/adapter.yml require --apply, and --no-host-write is the dogfood mode for evaluating another project without touching it.
argument-hint: "[--project-root <path>] [--artifact-root <path>] [--apply|--no-host-write]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  Adapting the portable engineering-skills ecosystem to a new host
  project. Use when onboarding a repo, dogfooding against a reference
  project, or regenerating local adapter facts after stack/CI/test
  changes. Produces project adapter facts, not human intent.
not_for: |
  Capturing project purpose, risk posture, desired direction, or
  intentional tradeoffs (use /project-interview). Cleaning up a messy
  codebase (use /triage-debt then the maintenance loop). Installing the
  runtime itself (use /engineer-init). Treating common legacy patterns
  as canonical without review.
escalate_to: |
  /project-interview when discovery finds ambiguous priorities,
  vibe-coded surfaces, or patterns that are common but not clearly
  healthy. /prevent-regression after a discovered convention is
  human-approved and detectable.
language: any
framework: any
scans: [python, javascript, typescript, go, java, kotlin, csharp, php, ruby, swift, rust, dart, c, cpp]
lanes: [project-adaptation]
stage: discover
entrypoint: true
produces: [adapter, adaptation_report, standardization_cautions]
evidence_required: [adapter, report]
risk_triggers: [legacy, high-churn, missing-tests, sensitive-surface]
max_overhead: "Stop after discovery and write unresolved questions; do not infer project philosophy."
---

# /adapt-project

## Kotlin/JVM 2.4.10 branch

Trigger this branch only for an exact manifest-selected lowercase `.kt`
project. Keep sibling `_kotlin` beside this skill, read
[`../_kotlin/GUIDE.md`](../_kotlin/GUIDE.md), and enter through
`scripts/discover_kotlin.py`. The guide owns the executable command and current
native-evidence prerequisites. The result is an objective dependency-free JVM
adapter only; `.kts`, Gradle/dependencies, Java, generated inputs, Android,
Multiplatform, plugins, frameworks, variants, and layout endorsement remain
outside the claim.

## C# 14 / .NET 10 branch

Use `scripts/discover_csharp.py` with the sibling `_csharp` provider; run the
script with `--help` for the exact CLI. The branch accepts only the exact
authored `.cs` source/test closure declared by `csharp-project.json`, compiles
and replays it with SDK 10.0.302, and reports direct Roslyn syntax facts. It
does not evaluate MSBuild, source generators, multi-targeting, resolved
symbols, runtime behavior, or layout health.

## C++20 branch

Use `scripts/discover_cpp.py` with `_cpp/cpp_facts.py` and
`_cpp/cpp_consumers.py`; run the script with `--help` for the exact CLI. It
requires a current complete C++20 compile database and admits only compiler-
owned headers. Output preserves namespace, signature, and overload boundaries;
it makes no ODR, ABI, specialization, dynamic-dispatch, or external-variant
claim.

## C17 branch

Use `scripts/discover_c.py` with the sibling `_c/c_lexical_facts.py` provider;
run `python3 scripts/discover_c.py --help` for the exact CLI. This external-
library branch requires Clang 21+, Make, and a current complete C17 compilation
database. It reports objective project facts only, not framework or layout
health, macro variants, C++, or Objective-C semantics.

## Dart v1

For a dependency-free plain-Dart 3.12 package, use the copied skill plus the
sibling `_dart/dart_project_snapshot.py`. The adapter inventories authored
library roles and records the exact native commands it proves. It does not run
Pub, infer Flutter, resolve a package graph, or endorse the observed layout.

```bash
SKILL_ROOT=".agents/skills/on-demand/adapt-project"
python3 "${SKILL_ROOT}/scripts/discover_dart.py" \
  --project-root "$PWD" \
  --output-dir "$PWD/reports/adapt-project/dart" \
  --direct-test "${DART_DIRECT_TEST:?Set a dependency-free direct test path}" \
  --smoke-entrypoint "${DART_SMOKE:?Set a direct smoke entrypoint}" \
  --expected-smoke "${DART_EXPECTED_SMOKE:?Set its exact stdout without the newline}"
```

Discover objective facts about a host project and turn them into a
project adapter. The adapter is the operational half of localizing
engineering-skills: stack, commands, tests, CI, source roots, docs,
domain terms, sensitive surfaces, existing guardrails, and candidate
overlays.

Do not confuse observed frequency with health. A messy repo may have
many repeated patterns that are exactly what the adapter should warn
against standardizing. Discovery reports what exists; `/project-interview`
and human review decide what deserves to become doctrine.

## How success is judged

- The installed skill's `scripts/discover.py` writes a scan directory containing
  `adapter.yml`, `adapter.json`, `report.md`, and `evidence.json`.
- The scan's `evidence.json` maps the required evidence tokens
  `adapter` and `report` to `adapter.yml` and `report.md`, satisfying
  this skill's `evidence_required: [adapter, report]` declaration.
- The installed skill's `scripts/check_evidence.py --scan-dir <scan>` exits 0
  before the run is called done.
- Host writes are absent unless `--apply` was explicitly requested; a
  dogfood run with `--no-host-write` uses an `--artifact-root` outside
  the host project.
- The summary surfaces high-confidence facts, standardization cautions,
  sensitive surfaces, and open questions without inferring project
  philosophy.
- A Go module's final adapter and report count only authored `.go` source,
  classify `go.mod`, emit `go test ./...`, and declare `status: complete`.
- A Java build's final adapter and report count only authored `.java` source,
  classify Maven or Gradle markers, emit the matching test command, and declare
  `analysis.java.status: complete`.

Status is atomic. `complete` means every requested filesystem fact and artifact
was written. This read-only Go inventory has no honest `partial` mode and does
not need native tooling, so `partial` and `unsupported` are reserved rather
than emitted. A path or write error is `failed`: the command exits nonzero and
the run must not be presented as a completed adapter.

## JavaScript-family v1 contract

Source-root facts retain the reference Python count and add
`typescript_files` with a `.ts`/`.tsx` breakdown, `javascript_files` with a
`.js`/`.jsx`/`.mjs`/`.cjs` breakdown, and `source_languages`. The large-root
standardization caution fires when any of the Python, TypeScript, or
JavaScript counts exceeds 200. JavaScript-family counts exclude `node_modules`,
`dist`, `build`, `generated`, `vendor`, and test descendants, as well as
declaration, `*.test`/`*.spec`, generated, and minified files.
Both `src/` and the common `source/` spelling are candidate source roots.

This is objective source-root discovery, not a Node-stack adapter. A
`package.json` may contribute package-manager markers and declared commands,
but it does not establish React, Vite, Next, Express, or any other framework.
This branch does not infer framework behavior from JavaScript or TypeScript,
resolve modules, type-check the host, or decide that observed code is a
healthy standard.

## Go v1 contract

Source-root facts add `go_files` and `go` to `source_languages` only when at
least one authored `.go` file is present. Counts exclude dependency, vendor,
build, generated, fixture, test-directory, `*_test.go`, generated-name, and
canonical `// Code generated ... DO NOT EDIT.` files. The same `>200` large-root
standardization caution used for Python and JavaScript-family source applies to
Go. Root-level Go files use the `.` source-root row; conventional `cmd`,
`internal`, and `pkg` trees are source-root candidates alongside existing
roots. Authored direct-child packages may use domain names such as
`middleware/`; they are inventoried without treating example, test, fixture,
dependency, vendor, build, or generated trees as production packages.

A root `go.mod` is an objective Go language/package-manager marker and adds the
native test command `go test ./...`; `go.work` is a language marker only. This
is filesystem discovery, so the skill does not require Go, parse source, load
packages, interpret build constraints, infer a framework, or claim that the
observed module layout is healthy. Native fixture verification runs separately
from the discovery command.

## Java v1 contract

For Java hosts, read [`references/java.md`](references/java.md) before running
discovery. That reference defines the authored-source boundary, accepted build
markers and commands, native fixture check, and explicit non-claims.

## Rust v1 contract

For a Cargo/Rust host, use the copied two-file Rust closure: this skill plus
the sibling `_rust/rust_lexical_facts.py`. It counts authored `.rs` modules,
classifies Cargo and source roles, and emits locked/offline check, test, and
format commands without treating the observed layout as a standard. Missing or
old tools remain `partial`; native failures are `failed`; no Rust result is
called unsupported.

```bash
SKILL_ROOT=".agents/skills/on-demand/adapt-project"
python3 "${SKILL_ROOT}/scripts/discover_rust.py" \
  --project-root "$PWD" \
  --output-dir "$PWD/reports/adapt-project/rust" .
```

The copied layout must also contain
`.agents/skills/on-demand/_rust/rust_lexical_facts.py`. The command writes
`adapter.yml`, `adapter.json`, `report.md`, and `evidence.json` and never writes
durable host configuration.

## External project/lexical variants

For PHP, Ruby, or Swift, load the selected skill with its sibling language
provider and read that provider's on-demand guide before execution:

- [`../_php-project-lexical/GUIDE.md`](../_php-project-lexical/GUIDE.md)
- [`../_ruby-project-lexical/GUIDE.md`](../_ruby-project-lexical/GUIDE.md)
- [`../_swift-project-lexical/GUIDE.md`](../_swift-project-lexical/GUIDE.md)

A consumer-only ambient install is incomplete. Each guide owns the exact
command, tool boundary, output contract, and bounded non-claims.

## Forms

```bash
/adapt-project
/adapt-project --project-root /path/to/repo
/adapt-project --project-root /path/to/repo --artifact-root /private/tmp/adapt/foo --no-host-write
/adapt-project --apply
```

Default behavior writes only a timestamped report under
`reports/adapt-project/scan-<TS>/`. `--apply` additionally writes the
durable adapter to `.engineering/project/adapter.yml` in the host project
(the committed-zone state home, ADR 0021 — not under any one agent's
folder). `--no-host-write` is mutually exclusive with `--apply` and is the
dogfood mode for evaluating another repo. When `--no-host-write` is
used, `--artifact-root` must be outside the host project.

## Pipeline

1. Resolve `PROJECT_ROOT` and `ARTIFACT_ROOT`.
2. Run discovery:

   <!-- installed-command:discover:start -->
   ```bash
   PROJECT_ROOT="$(cd "${PROJECT_ROOT:-.}" && pwd -P)" || exit $?
   ARTIFACT_ROOT="${ARTIFACT_ROOT:-$PROJECT_ROOT}"
   mkdir -p "$ARTIFACT_ROOT" || exit $?
   ARTIFACT_ROOT="$(cd "$ARTIFACT_ROOT" && pwd -P)" || exit $?
   ADAPT_PROJECT_SKILL="${ADAPT_PROJECT_SKILL:-.agents/skills/adapt-project}"
   cd "$ADAPT_PROJECT_SKILL"
   SCAN_DIR="$(python3 -I -S scripts/discover.py \
     --project-root "${PROJECT_ROOT}" \
     --artifact-root "${ARTIFACT_ROOT}")"
   printf '%s\n' "$SCAN_DIR"
   ```
   <!-- installed-command:discover:end -->

   Add `--no-host-write` only with an artifact root outside the project for a
   dogfood run, or add `--apply` only after the user explicitly wants durable
   project state written. Keep `ADAPT_PROJECT_SKILL` on its own preceding
   assignment line: a command-local environment assignment does not affect
   expansion of `$ADAPT_PROJECT_SKILL` in the same command line.

3. Read the generated `adapter.yml` and `report.md`.
4. Surface:
   - high-confidence facts;
   - standardization cautions;
   - sensitive surfaces;
   - open questions that require `/project-interview`.
5. Before claiming done, run the evidence gate on the scan directory:

   <!-- installed-command:check-evidence:start -->
   ```bash
   python3 -I -S scripts/check_evidence.py \
     --scan-dir "$SCAN_DIR"
   ```
   <!-- installed-command:check-evidence:end -->

   If discovery ran in a previous shell, pass its timestamped scan path
   explicitly instead of relying on `latest`.

## Output

Each scan directory contains:

- `adapter.yml` — machine-readable adapter facts (JSON-compatible YAML so
  the copied skill has no PyYAML dependency).
- `adapter.json` — same payload for tools that prefer JSON.
- `report.md` — human-readable summary.
- `evidence.json` — evidence manifest for the installed
  `scripts/check_evidence.py` command.

Durable project state, when `--apply` is used:

- `.engineering/project/adapter.yml`

## Dogfood

For host-a-style dogfood without touching the host project:

```bash
ADAPT_PROJECT_SKILL="${ADAPT_PROJECT_SKILL:-.agents/skills/adapt-project}"
cd "$ADAPT_PROJECT_SKILL"
python3 -I -S scripts/discover.py \
  --project-root /path/to/host-a \
  --artifact-root /private/tmp/engineering-skills-dogfood/host-a \
  --no-host-write
```

Read the resulting adapter and use `/project-interview` only for the human
questions that discovery explicitly leaves open. Dogfood discovery is
host-read-only: the artifact root must stay outside the project being
evaluated.

## Standardization Guard

When the project looks like a vibe-coded or inherited mess, the correct
output is a stabilization map, not a canon. Mark common-but-suspect
patterns as `do not standardize yet`, route them to `/triage-debt`, and
only promote patterns with human approval plus tests, lints, or clear
examples of healthy use.

## When things go sideways

| Symptom | Action |
|---|---|
| `scripts/discover.py` exits nonzero | Surface the exact stderr and stop; do not claim `adapter.yml`, `adapter.json`, `report.md`, or `evidence.json` landed |
| `discover.py` reports `--apply and --no-host-write are mutually exclusive` | Pick one mode: `--apply` for durable host state, or `--no-host-write` for dogfood/read-only evaluation |
| `discover.py` reports `--no-host-write requires --artifact-root outside --project-root` | Move `--artifact-root` outside the host project and rerun; do not write dogfood artifacts inside the repo being evaluated |
| `scripts/check_evidence.py` reports no `evidence.json` manifest | Treat the adaptation as incomplete; rerun discovery or inspect the scan directory before claiming done |
| `check_evidence.py` reports missing `adapter` or `report` evidence | Fix the scan so `evidence.json` points to existing `adapter.yml` and `report.md`, then rerun the gate |
| `check_evidence.py` reports malformed JSON or missing scan dir | Surface the usage/data error and stop; do not fabricate a passing evidence transcript |

## Replay case

From the source repository, the locked Go fixture must first pass its native
boundary and then reach the final adapter/evidence boundary without source
mutation:

```bash
(cd tests/fixtures/adapt-project-go-g1 && go test ./...)
.venv/bin/python -m pytest -q tests/test_adapt_project_go_g1.py
```

The equivalent Java replay is:

```bash
javac --release 17 -proc:none -d /tmp/adapt-project-java-j2a-classes \
  $(find tests/fixtures/adapt-project-java-j2a -name '*.java' -type f)
.venv/bin/python -m pytest -q tests/test_adapt_project_java_j2a.py
```

## Inspiration

This skill was inspired in part by GAIA React's agent workflow ideas,
especially its fitness, forensics, audit, and review-gate patterns:
https://github.com/gaia-react/gaia
