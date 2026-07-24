---
name: find-concept-divergence
description: |
  Advisory SUSPECT scan that surfaces concept-name drift between the
  canonical glossary at `.claude/contracts/concepts.yaml` and the
  codebase / docs. Detects three drift bands: `avoid_term_hit` (code
  uses a phrasing the glossary explicitly says is wrong),
  `competing_term_coexistence` (a `flagged_ambiguities` entry has
  multiple `competing_terms` present in the same file — drift the
  glossary author has not yet resolved), and
  `superseded_co_occurrence` (both a deprecated name and its
  `superseded_by:` replacement appear in the same file — rename
  transition drift). Detection only — never edits code or docs.
argument-hint: "[paths... — defaults to common project roots; see SKILL.md]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Catching cross-subsystem concept-drift cases (a function/module name
  in one subsystem that conceptually duplicates a canonical name in
  another). Pairs with the canonical glossary at
  `.claude/contracts/concepts.yaml`: if a divergence exists for a
  concept that isn't yet glossary-tracked, the strict scan will miss
  it — add the concept first, then re-run.
not_for: |
  Refactor execution (this is detection only); enforcing renames that
  already have a dedicated lint — set `coverage_lint:` on the
  superseded concept and the scanner will skip co-occurrence noise so
  the lint owns the rename; fuzzy/similarity-based identifier matching
  (deferred — strict canonical-name + avoid-term grep only in v1).
language: any
framework: any
scans: [python, javascript, typescript, go, java, php, ruby, swift, rust, dart, c, cpp, markdown, templates]
---

# /find-concept-divergence

## C++20 branch

Use `scripts/scan_cpp.py` with the sibling `_cpp` provider; run the script with
`--help` for the exact CLI. It reports strict glossary spelling only across a
current complete C++20 compiler-owned source/header snapshot while retaining
namespace, signature, and overload context. Text hits do not prove symbol
identity, ODR/ABI, specializations, dispatch, or external variants.

## C17 branch

Use `scripts/scan_c.py` with the sibling `_c/c_lexical_facts.py` provider; run
`python3 scripts/scan_c.py --help` for the exact CLI. This external-library
branch emits strict glossary-backed authored-text evidence only. Comments and
strings may be review noise; macro expansion, symbol identity, rename
completeness, C++, and Objective-C remain unresolved.

## Dart v1

Dart v1 is strict glossary-backed text evidence over authored library source.
Copy the sibling `_dart/dart_project_snapshot.py`; the scan excludes generated,
test, example, vendor, build, report, part, barrel, and symlink roles and makes
no symbol-identity or rename-completeness claim.

```bash
SKILL_ROOT=".agents/skills/on-demand/find-concept-divergence"
python3 "${SKILL_ROOT}/scripts/scan_dart.py" \
  --project-root "$PWD" --dart-root lib \
  --glossary "$PWD/.claude/contracts/concepts.yaml" \
  --output "$PWD/reports/find-concept-divergence/dart/findings.jsonl" \
  --report "$PWD/reports/find-concept-divergence/dart/report.md" \
  --direct-test "${DART_DIRECT_TEST:?Set a dependency-free direct test path}" \
  --smoke-entrypoint "${DART_SMOKE:?Set a direct smoke entrypoint}" \
  --expected-smoke "${DART_EXPECTED_SMOKE:?Set its exact stdout without the newline}"
```

You are running an advisory concept-glossary divergence audit. The goal
is to surface places in the codebase or docs where:

1. **avoid-term hits** — code uses a phrasing that the glossary
   explicitly lists under a concept's `avoid:` block (the glossary
   author has said "do not use this phrasing for this concept").
2. **competing-term coexistence** — a file contains multiple
   `competing_terms` from a `flagged_ambiguities` entry (an open
   ambiguity has bled into runtime — two competing names for the same
   concept are co-occurring in the same module).
3. **superseded co-occurrence** — a file mentions both a deprecated
   concept name and its `superseded_by:` replacement (rename
   transition drift; redundant with `coverage_lint:`-declared lints).

This skill is detection-only. It never edits code, docs, or the
glossary; it writes a report under
`reports/find-concept-divergence/scan-<UTC>/` so a follow-up audit can
act on the findings.

## Host-language boundary

The host code language is not a routing constraint: this is a strict textual
glossary scan. It reads `.py`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx`,
template/HTML, and prose files. It does not parse JavaScript or TypeScript,
resolve imports, infer types, or judge JSX runtime behavior. Generated,
vendor, test, minified, and symlinked sources remain excluded by strict
path-level rules; identifier-like terms use lexical word boundaries, not fuzzy
or substring matching.

Go support is an explicit `--language go` strict-text mode, not an inference
from the generic suffix walk. It inventories every selected `.go` and
`_test.go` file before excluding test, generated, vendor, and symlink surfaces.
The `python-strict-text` analyzer applies the same exact term boundaries to
eligible UTF-8 source; it does not parse Go syntax, packages, build tags,
identifiers, comments, or string literals.

The automatic non-Go surface remains
`scans: [python, javascript, typescript, markdown, templates]`; only explicit
Go mode promotes Go files into the supported inventory/status contract.

Java support is likewise explicit rather than part of the automatic suffix
walk. Read [`references/java.md`](references/java.md) only for a Java run; it
defines the source-role inventory, native fixture check, and strict-text
non-claims.
This extends the preserved
`scans: [python, javascript, typescript, go, markdown, templates]` contract
with one separately selected Java band.

Rust is a separate strict-text mode over authored `.rs` source. It uses the
copied `_rust/rust_lexical_facts.py` inventory/native gate and records exact
glossary-term spans and hashes; generated, vendor, target/build, test,
auxiliary, configuration, and symlink roles remain visible but cannot fire.
This is textual evidence, not symbol identity or semantic equivalence.

```bash
SKILL_ROOT=".agents/skills/on-demand/find-concept-divergence"
REPORT_DIR="$PWD/reports/find-concept-divergence/rust"
python3 "${SKILL_ROOT}/scripts/scan_rust.py" \
  --project-root "$PWD" \
  --glossary "$PWD/.claude/contracts/concepts.yaml" \
  --output "${REPORT_DIR}/findings.jsonl" \
  --report "${REPORT_DIR}/report.md" .
```

The copied closure must include sibling `_rust/rust_lexical_facts.py`.

### External strict-text variants

For PHP, Ruby, or Swift, load the selected skill with its sibling language
provider and read that provider's on-demand guide before execution:

- [`../_php-project-lexical/GUIDE.md`](../_php-project-lexical/GUIDE.md)
- [`../_ruby-project-lexical/GUIDE.md`](../_ruby-project-lexical/GUIDE.md)
- [`../_swift-project-lexical/GUIDE.md`](../_swift-project-lexical/GUIDE.md)

These are glossary-backed authored-text scans, not symbol or conceptual
identity. The guides own the exact commands, native gates, and non-claims.

## How success is judged

- The run is graded only by artifacts: pasted command output plus
  `findings.jsonl` and `report.md`. Do not claim concept drift was
  checked without those files.
- The scan verdict is one of `clean`, `real-drift`, `glossary-gap`,
  `noise-only`, or `scan-blocked`. A mixed report may name multiple
  row-level triage labels, but the run-level verdict should state the
  most important next action.
- Every row-level triage decision cites the report row and the relevant
  glossary entry. Code claims without the glossary evidence are not
  enough for a concept-divergence verdict.
- The skill remains read-only. It can recommend a rename, glossary
  update, ADR, exclusion, or lint handoff; it never edits the glossary,
  code, docs, or lint rules in this run.
- Go `scan.json` status is exactly one of `complete`, `partial`, `unsupported`,
  or `failed`. The Markdown report repeats it. Missing/old Go, unreadable
  eligible source, and Go tool failures must never become `clean`.
- Java uses the same status vocabulary in `scan.json`, but strict-text scanning
  does not depend on a JDK. Unreadable eligible source cannot become `clean`.

## Glossary source

The canonical glossary is `.claude/contracts/concepts.yaml`. The
detector reads:

- `concepts[].name`, `concepts[].aliases`, `concepts[].avoid`,
  `concepts[].superseded_by`, `concepts[].source`,
  `concepts[].coverage_lint`
- `flagged_ambiguities[].competing_terms`

If the glossary is missing or unparseable the scan exits with a clear
error rather than degrading silently — concept-divergence detection
has no meaningful default behavior without it.

Copied installs use a schema-specific stdlib profile, not a general YAML
engine: normal block lists and scalar flow lists are supported; quoted flow
values preserve commas (single quotes or JSON-style double quotes). Nested
flow collections and other unsupported shapes stop the scan with a parse error
rather than becoming different search terms. Normalize those entries to the
documented block-list shape before running the scan.

## Schema convention: `competing_terms:` vs overload ambiguities

`competing_terms:` is for terms that genuinely compete *for the same
concept slot* — rename transitions, parallel implementations of the
same thing, or two names that mean the same thing fighting for
canonicality. Band 2 (`competing_term_coexistence`) treats a file
containing 2+ of these as drift, which is the right semantics for
true competition.

Do **not** use `competing_terms:` for **overload** cases where the
named terms are typed names for *distinct things that share a noun*
(e.g. distinct stores with overlapping prose, or distinct entities
that each carry the same generic English word in their slug). For
those, document the typed senses under `where:` and let the
canonical concept's `avoid:` block catch the actual drift signal
(bare generic-noun usage in prose / log strings) via band 1.

## Default target

If the caller does not provide paths, the scanner walks a portable
set of common project roots — language- and framework-agnostic —
and auto-skips any that don't exist in the host repo:

```
app/, src/, lib/, scripts/, tests/, docs/,
.claude/skills/, .claude/docs/,
CONTEXT.md, README.md, ONBOARDING.md,
CLAUDE.md, .claude/CLAUDE.md
```

Out-of-scope paths (always excluded): `.venv/`, `node_modules/`,
`.git/`, `dist/`, `build/`, `__pycache__/`, `.pytest_cache/`,
`.mypy_cache/`, `.ruff_cache/`, `*/migrations/` (Django-shaped),
`ai-docs/decisions/` (ADRs intentionally name both sides of a rename),
`.claude/worktrees/` (agent worktrees), `reports/` (runtime output),
`*.worktree/`. Host projects extend the prefix exclusion list via
`.claude/skills/find-concept-divergence/host_excludes.txt` (one
path-prefix per line; comments via `#`).

Exclusions are evaluated against the logical path relative to `--project-root`,
including a directly named file or directory. The walk never traverses a
directory symlink, even when that symlink or one of its descendants is the
direct target; an alias below an excluded logical directory cannot bypass that
exclusion. Files/symlinks resolving outside the project root are rejected.
Therefore a host may itself live below an ancestor named `node_modules`, while
its own dependency tree and escaped symlink targets remain out of scope.

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/find-concept-divergence/$SCAN_ID"
mkdir -p "$REPORT_DIR"

.venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py \
  --output "$REPORT_DIR/findings.jsonl" \
  --report "$REPORT_DIR/report.md"
```

Scan targets, finding labels, and the glossary default
(`<project-root>/.claude/contracts/concepts.yaml`) anchor on
`--project-root`, which defaults to the git toplevel of the cwd (else
the cwd).

For a bounded target or non-default glossary, pass the flags explicitly:

```bash
.venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py \
  --output "$REPORT_DIR/findings.jsonl" \
  --report "$REPORT_DIR/report.md" \
  --glossary .claude/contracts/concepts.yaml \
  .claude/skills/find-concept-divergence
```

The scan writes:

- `findings.jsonl` — one record per hit; fields `band`, `concept` or
  `ambiguity_id`, `file`, `line`, `match`, `term`.
- `report.md` — grouped summary by band, sorted by concept then file.
- `scan.json` — Go tool/version evidence, full Go inventory, eligibility
  reasons, and analysis status when `--language go` is selected.

### Go copied-closure pipeline

Use Go >= 1.22.0 discovered from `PATH`; the fixture/native oracle remains the
host's own `go test ./...`:

```bash
CONCEPT_SKILL="$PWD/.agents/skills/find-concept-divergence"
CONCEPT_REPORT="$PWD/reports/find-concept-divergence/scan-go"
mkdir -p "$CONCEPT_REPORT"
python3 "${CONCEPT_SKILL}/scripts/scan.py" \
  --project-root "$PWD" --language go \
  --output "$CONCEPT_REPORT/findings.jsonl" \
  --report "$CONCEPT_REPORT/report.md" .
go test ./...
```

The strict-text outcome remains valid when eligible Go source is syntactically
malformed because the claim is textual co-occurrence, not parse validity.
Invalid UTF-8 or a read failure is different: it leaves a failed inventory row
and makes the result `partial`.

## Output triage

Classify each finding into one of:

- **real drift** — code says one thing, glossary says another;
  promote to a `quality/findings.jsonl` entry (or the host project's
  equivalent) with band-appropriate recommendation (rename, glossary
  update, ADR).
- **glossary gap** — the term in code is fine but the glossary lists
  a stale `avoid:` phrasing or hasn't registered a real synonym; update
  `concepts.yaml` and re-run.
- **noise** — false-positive (term appears inside a string literal or
  comment that's intentionally quoting deprecated naming). Skip; if
  the same noise recurs across multiple scans, narrow the `avoid:`
  phrase, add the file's prefix to `host_excludes.txt`, or move the
  case to a typed-name `where:` block instead of `competing_terms:`.

If you dispatch an Agent to triage the report, give it this verdict
contract: each row must be labeled `real drift`, `glossary gap`, or
`noise`, and each label must cite both the report row and the glossary
entry. Agent output without those citations is not evidence.

## Strict-first principle

v1 is strict only: it grep-matches the canonical names, aliases, avoid
phrasings, and competing-terms slugs verbatim (word-boundary,
case-insensitive). It does **not** do similarity matching, stem
analysis, or fuzzy identifier comparison. Add similarity flagging
only if the strict pass produces nothing real over multiple cycles.

If the strict pass produces noise, narrow the `avoid:` phrases in
`concepts.yaml` (more specific, more identifier-like) or add a
`host_excludes.txt` entry — don't add heuristics to the body.

## Replay check

After editing this skill or its detector contract, run:

```bash
.venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py --help
SCAN_ID="scan-replay"
REPORT_DIR="/tmp/find-concept-divergence-${SCAN_ID}"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py \
  --output "$REPORT_DIR/findings.jsonl" \
  --report "$REPORT_DIR/report.md" \
  .claude/skills/find-concept-divergence
```

This bounded self-scan is the replay case for text/contract repairs. It
proves the documented argparse surface and output contract execute
against the current glossary; it does not prove the full repo is clean.

## When things go sideways

| Symptom | Action |
|---|---|
| `.claude/contracts/concepts.yaml` is missing or unparseable | Mark `scan-blocked`, paste the error, and stop; concept-divergence has no useful fallback without the glossary. |
| The report has hits but the glossary entry is ambiguous | Use row label `glossary gap`, cite the entry, and recommend updating `concepts.yaml` before renaming code. |
| A hit appears only in a deliberate quote of deprecated terminology | Label it `noise`, cite the surrounding line, and only add an exclusion if the same noise recurs. |
| A superseded concept declares `coverage_lint` | Treat that lint as owning the rename guard; do not double-count skipped co-occurrence noise as scanner drift. |
| Agent triage omits glossary citations | Reject the dispatch output and read the report/glossary directly. |
| Go is missing or older than 1.22.0 | Preserve the `unsupported` report/`scan.json`, restore Go >= 1.22.0 on `PATH`, and re-run. |
| An eligible Go file cannot be decoded | Keep the report `partial` and cite the failed inventory row; never treat the remaining scan as complete. |
| An eligible Java file cannot be decoded | Keep the report `partial` and cite the failed inventory row; malformed Java syntax remains valid strict-text input. |
