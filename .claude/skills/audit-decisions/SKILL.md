---
name: audit-decisions
description: "Read-only, portable decision-registry drift audit. It writes a final drift report, captures registry/link diagnostics, and validates `decision:NNNN` references from Python, Go, Java JDK 17+, bounded PHP, Ruby, Swift, Rust, and Dart, JavaScript-family, and TypeScript comments plus Markdown/HTML references."
argument-hint: "[--target PATH]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: guard
best_for: |
  Periodic (monthly / pre-release) decision-registry hygiene and a precise
  check that inline decision references still point at real ADRs.
not_for: |
  Authoring or amending ADRs, acting on a reported row, identifier/import
  resolution, or inferring runtime/framework semantics.
escalate_to: |
  None. This skill is read-only; each finding names the human's next command.
delegate_from: |
  /which-skill may recommend /audit-decisions for decision-registry hygiene
  and orphaned inline decision references.
language: any
framework: any
scans: [python, markdown, html, javascript, typescript, go, java, php, ruby, swift, rust, dart, c]
---

# /audit-decisions

## C17 branch

Use `scripts/audit_c.py` with the sibling `_c-syntax` provider; run
`python3 scripts/audit_c.py --help` for the exact CLI. This external-library
branch requires Clang 21+ and a current complete C17 compilation database. It
recognizes registry tokens in real comments only; macro meaning, inactive
branches, applicability, and runtime behavior remain unresolved.

## External syntax variants

For PHP, Ruby, or Swift, load the selected skill with its sibling provider and
read the matching on-demand guide before execution:

- [`../_php-syntax/GUIDE.md`](../_php-syntax/GUIDE.md)
- [`../_ruby-syntax/GUIDE.md`](../_ruby-syntax/GUIDE.md)
- [`../_swift-project-lexical/GUIDE.md`](../_swift-project-lexical/GUIDE.md)

These resolve comment tokens against the ADR registry only. The guides own the
exact commands, copied closures, native gates, and semantic non-claims.

## Dart v1

Dart v1 recognizes lowercase `decision:NNNN` only in real line, block, and doc
comments from eligible authored source. Its copied closure includes sibling
`_dart/scripts` and the locked public `package:analyzer` tool. It runs locked
offline setup only in a disposable tool copy, never in the audited host.

```bash
SKILL_ROOT=".agents/skills/on-demand/audit-decisions"
python3 "${SKILL_ROOT}/scripts/audit_dart.py" \
  --project-root "$PWD" --target . \
  --output-dir "$PWD/reports/audit-decisions/dart" \
  --native-test "${DART_DIRECT_TEST:?Set a dependency-free direct test path}" \
  --smoke "${DART_SMOKE:?Set a direct smoke entrypoint}" \
  --smoke-stdout "${DART_EXPECTED_STDOUT:?Set exact stdout including any newline}"
```

This is comment syntax evidence only; it does not interpret whether a decision
applies, resolve symbols, or claim coverage across generated/conditional code.

## Rust v1

For Rust, run the bounded comment-reference adapter over one explicit Cargo
source target. It preserves the four audit artifacts and distinguishes real
line/block/doc comments from strings. The copied closure must include sibling
`_rust-syntax`; cfg, macros, build output, generated roles, and symlinks make
the result partial rather than clean.

```bash
SKILL_ROOT=".agents/skills/on-demand/audit-decisions"
python3 "${SKILL_ROOT}/scripts/audit_rust.py" \
  --project-root "$PWD" --target src \
  --output-dir "$PWD/reports/audit-decisions/rust"
```

Run a read-only drift scan over `ai-docs/decisions/` and the host's authored
reference files. The final artifact is `drift.md`; `raw-drift.json` preserves
both drift evidence and every resolved reference, so a healthy TypeScript/TSX
reference is visible rather than silently disappearing.

## How success is judged

- Write `drift.md`, `raw-drift.json`, `registry-audit.json`, and
  `link-check.txt` under one requested run directory that resolves below
  `--project-root/reports/audit-decisions/`. Do not claim a scan ran without
  all four artifacts.
- Include valid `decision:NNNN` references from TypeScript and TSX comments in
both final artifacts. JavaScript uses the same syntax-only parser for `.js`,
`.jsx`, `.mjs`, and `.cjs`. A valid reference prevents an old accepted ADR from
  being reported as unreferenced.
- Preserve Python comment, Markdown, and HTML reference handling additively.
  Registry status/link checks remain visible in their compatibility artifacts.
- Include valid references from authored Go line and block comments in both
  final artifacts; strings, raw strings, tests, generated source, and vendor
  source must not create references.
- Include valid references from authored Java line and block comments in both
  final artifacts; strings, chars, text blocks, tests, generated source, and
  vendor source must not create references.
- Keep the registry and source files read-only. Exit `0` for clean, `1` when
  drift rows are present, and `2` for invalid paths, unsupported/malformed
  decision frontmatter, unavailable project-local TypeScript tooling, invalid
  JavaScript/TypeScript syntax, or a
  report directory outside the per-run audit-report location.

Successful audits are atomic and write `status: complete` to `raw-drift.json`.
The Go v1 path never publishes `partial` evidence: any in-scope Go file must
parse before artifacts are written. Missing/old Go is `unsupported`; malformed
Go or a parser execution/data error is `failed`; both exit `2` without a report
directory. These states are not clean audits.

The Java comments v1 path has the same atomic rule. Missing/old JDK is
`unsupported`; malformed Java, source-read, or helper execution/data errors are
`failed`; all exit `2` without a report directory. It never publishes a partial
Java inventory as a clean audit.

## Supported reference contract

### TypeScript and TSX v1

The supported token is lowercase `decision:NNNN`, where `NNNN` is exactly four
digits. It is recognized only in these real comment forms:

- `// decision:0001` line comments;
- `/* decision:0001 */` block comments;
- `/** decision:0001 */` JSDoc comments, including multi-line JSDoc;
- comments inside a template interpolation (`${/* decision:0001 */ ...}`) and
  TSX expression (`{/* decision:0001 */}`), including expressions inside JSX
  fragments.

The bundled Node helper parses each TS/TSX source with the host project's
project-local `typescript` Compiler API. It accepts real comment trivia in code
(including JSX expressions and generic JSX type arguments) while excluding
string literals, template text, regex literals, and TSX text nodes, including
comment-shaped text in elements or fragments. It rejects syntax errors rather
than producing a partial reference inventory. The helper does not parse
identifiers, resolve imports, interpret types, or infer React/Node/other
framework behavior; it needs no `tsconfig`, Program, or type checker.

If a scannable `.ts` or `.tsx` file exists, Node.js and a `typescript` package
resolvable from `--project-root/package.json` are required. Install the host's
locked dependencies before running the audit (for example `npm ci`); do not
substitute a global TypeScript installation. The scan itself performs no package
manager operation or network access.

### Existing reference forms

- Python: `decision:NNNN` inside a real `#` comment (Python's tokenizer
  distinguishes it from strings).
- Markdown: the established `# decision:NNNN` form.
- HTML: the established `# decision:NNNN` form, normally inside `<!-- -->`.

### Go comments v1

For `.go`, the supported token is the same lowercase `decision:NNNN` form in a
real `//` line comment or `/* ... */` block comment. The bundled Go helper uses
the standard-library `go/parser` comment groups, so quoted/interpreted strings,
raw strings, identifiers, and comment-shaped text never count. Every selected
Go file must parse; the audit does not silently keep references from the
well-formed subset.

Go is discovered from `PATH` and must be Go 1.22 or newer. The helper is
stdlib-only and runs from the copied skill; it does not load packages, honor or
evaluate build tags, resolve imports, use `go/packages`, mutate the module, or
access the network. This is the weakest native fact needed to distinguish real
Go comments from literals.

The selected runner accepts ordinary scalar frontmatter plus inline or block
lists for the registry fields it checks (`supersedes`, `superseded_by`,
`applies_to`, `embodied_by`, `tags`). It fails clearly instead of silently
misreading unsupported frontmatter syntax.

### Java comments v1

For `.java`, the supported token is the same lowercase `decision:NNNN` form in
a real `//` line comment or `/* ... */` block/Javadoc comment. The bundled JDK
17 Compiler Tree API helper first parses every selected source, then uses its
family-local lexer for ordinary comment trivia (the public compiler tree API
does not expose it). Strings, chars, text blocks, and comment-shaped literals
never count. Java Unicode escapes are translated before lexing so an eligible
escaped delimiter follows Java tokenization rules.

Java is discovered from `PATH`; both `java` and `javac` must be JDK 17 or
newer. The helper is copied with the skill, runs neither Maven nor Gradle, and
does not load a classpath, resolve imports/types/overloads, use compiler
internals, mutate a build, or access the network. An unresolved Java name is
still valid syntax evidence, not a symbol-identity claim.

## Source policy

Exclusions are always evaluated relative to `--project-root`, even when a
caller directly targets an excluded directory or file. Generated, vendor,
dependency, build, report, coverage, fixture, and test/spec paths never create
references. The same policy excludes common VCS/venv/cache trees and TypeScript
declarations, `.test`, `.spec`, and minified files.
Go additionally excludes `*_test.go`, generated-name files, and files with the
canonical `// Code generated ... DO NOT EDIT.` header.
Java additionally excludes conventional `*Test.java`, `*Tests.java`, `*IT.java`,
and generated-name files; the conventional generated header is excluded too.

`--target` narrows the reference scan only. It still validates the registry and
links, but intentionally omits the whole-project `unreferenced-decision`
inverse check because a partial target cannot establish that conclusion.

## Installed workflow

Stock Codex copies this selected skill to `.agents/skills/audit-decisions`.
From the host project root, with Python 3.11+, Go 1.22+ when `.go` files are in
scope, JDK 17+ when `.java` files are in scope, and Node.js plus the host's
project-local `typescript` dependency when JavaScript-family files are in scope:

```bash
AUDIT_PROJECT_ROOT="$PWD"
AUDIT_SKILL_DIR="$AUDIT_PROJECT_ROOT/.agents/skills/audit-decisions"
AUDIT_SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
AUDIT_REPORT_DIR="$AUDIT_PROJECT_ROOT/reports/audit-decisions/$AUDIT_SCAN_ID"

python3 -I -S "${AUDIT_SKILL_DIR}"/scripts/audit.py \
  --project-root "$AUDIT_PROJECT_ROOT" \
  --output-dir "$AUDIT_REPORT_DIR"
```

For a bounded code-reference check, add a project-relative target:

```bash
python3 -I -S "${AUDIT_SKILL_DIR}"/scripts/audit.py \
  --project-root "$AUDIT_PROJECT_ROOT" \
  --output-dir "$AUDIT_REPORT_DIR" \
  --target src
```

The registry and Python/Markdown/HTML paths import only Python standard-library
modules from this selected directory. When a TS/TSX file is in scope, the
selected skill invokes its bundled `.mjs` helper with host Node.js and the
project-local `typescript` Compiler API. It does not need a toolkit virtualenv,
repository helper, sibling skill, global TypeScript installation, host `tsconfig`,
or network connection at scan time.
When Go is in scope, the selected skill instead invokes its bundled `.go`
helper with the discovered Go 1.22+ executable; it has no host module or
third-party dependency.
When Java is in scope, it invokes its bundled `.java` helper once with every
selected eligible Java source, using the discovered JDK 17+ source launcher;
it has no Maven, Gradle, or third-party dependency.

## Read the final artifact before acting

`drift.md` lists summary counts, resolved-reference inventory, and every drift
row with a resolution command. `raw-drift.json` is the structured evidence:
`references[]` always includes path, line, language, comment form, ADR id, and
whether the id resolves. `registry-audit.json` and `link-check.txt` retain the
registry status/link diagnostics for direct troubleshooting.

The report can surface these drift classes:

| Symptom | Default severity | Resolution |
|---|---|---|
| `code-ref-orphan` | P0 for code, P1 for docs | `/decide <id>` or remove the stale reference |
| `broken-supersession` | P0 | `/decide --amend <id>` |
| `applies-to-missing` | P1 (P0 when every non-host path is absent) | `/decide --amend <id>` |
| `proposed-too-long` | P1 (P0 after 90 days) | `/decide --amend <id>` |
| `unreferenced-decision` | P2 (P1 for lint/enforced tags) | review whether the ADR remains load-bearing |
| `registry-audit` | P0 | amend the named malformed registry field |

## When things go sideways

| Symptom | Action |
|---|---|
| Exit 2 | Correct the project/target path or frontmatter; restore Node.js/the host's local `typescript`; or repair TS/TSX syntax. Do not treat a failed parse as a clean audit. |
| Go reports `status=unsupported` | Put Go 1.22+ on `PATH` and re-run; do not present an audit that omitted selected Go files. |
| Go reports `status=failed` | Repair the named Go syntax/parser failure and re-run; no partial report is valid. |
| Java reports `status=unsupported` | Put JDK 17+ (`java` and `javac`) on `PATH` and re-run; do not omit selected Java files. |
| Java reports `status=failed` | Repair the named Java syntax/read/helper failure and re-run; no partial report is valid. |
| Report directory is rejected | Use a run directory below `reports/audit-decisions/`, such as `reports/audit-decisions/scan-20260719-120000`. Absolute paths are allowed only when they resolve below that same directory. The report root itself, source/arbitrary project paths, `..` escapes, output/ancestor symlinks that escape it, and a report-root symlink are rejected before any artifact is written. |
| TS/TSX exists but TypeScript is unavailable | Install the project's locked dependencies so `typescript` resolves from `package.json`, then re-run. Do not present an incomplete TypeScript scan as clean. |
| A desired reference is in an identifier, string, regex, or JSX text | Do not count it. Add a supported comment at the authoritative location. |
| An excluded tree is supplied directly with `--target` | The scan is clean for references by design; exclusions cannot be bypassed by narrowing the target. |
| A relationship/link diagnostic is present | Read `link-check.txt`, repair the ADR deliberately, then re-run. |

## Installed layout

```
audit-decisions/
├── SKILL.md
└── scripts/
    ├── audit.py
    ├── detect_go_comments.go
    ├── detect_java_comments.java
    └── detect_typescript_comments.mjs
```

## Replay case

```bash
(cd tests/fixtures/audit-decisions-go-g1 && go test ./...)
.venv/bin/python -m pytest -q tests/test_audit_decisions_go_g1.py
```
