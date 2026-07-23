---
name: move-path
description: Deterministically plan, dry-run, apply, and verify standalone path moves while updating identity-resolved Markdown, HTML, config, backtick, and exact path references. Checked JavaScript updates bounded literal module references; checked Go supports one leaf non-main package-directory move in one root module; checked Java supports one leaf package-directory move with compiler-attributed package/import/FQCN edits; checked PHP supports one Composer PSR-4 leaf namespace-directory move; checked Swift supports one dependency-free SwiftPM target-directory move while retaining module identity; checked Rust supports one conventional Cargo library leaf-module file or directory move; checked Dart supports one evidence-authorized private library file or leaf-directory move with analyzer-resolved directive rewrites and public-barrel preservation. TypeScript/TSX source imports are never rewritten in v1.
argument-hint: "--plan moves.json --dry-run|--apply|--check"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: maintenance
job: refactor
best_for: |
  Everyday but high-blast path moves: moving or renaming Markdown docs,
  directories, fixtures, scripts, or mixed repo surfaces where references
  should update in one batch. Best when a move map can be reviewed first
  and the desired behavior is "compute a virtual after-tree, rewrite safe
  references once, apply with git-aware moves, then verify."
  Also use the checked-JavaScript mode for explicit `.js`, `.jsx`, `.mjs`, or
  `.cjs` file moves that must update safe relative imports and checked-project
  configuration while leaving unrelated TypeScript source unchanged.
  Use the checked-Java mode for one reviewed standalone-JDK leaf-package move
  whose package, import, and fully-qualified type identities must stay exact.
  Use the checked-Swift mode only for one reviewed dependency-free SwiftPM
  target-directory move that retains module identity and has an executable smoke product.
  Use the checked-Rust mode only for one reviewed conventional leaf-module
  file or directory move in a regular Cargo library target.
  Use the checked-Dart mode only for one reviewed private `lib/src` library
  file or leaf-directory move in a dependency-free Dart 3.12 package with a
  pre-existing package configuration, direct native test/smoke, and declared
  stable public barrel.
not_for: |
  Domain-concept terminology renames in prose (use /rename-concept).
  Python/TypeScript import refactors unless a language adapter has been
  explicitly added and enabled. Large behavior-changing subsystem splits
  that need characterization tests and human Phase 4 sign-off (use
  /refactor-subsystem). Blind global find-and-replace.
language: any
framework: any
scans: [dart, go, java, javascript, php, rust, swift, typescript]
---

# /move-path

You are the orchestrator for safe batched standalone TypeScript/TSX path
moves, plus opt-in bounded checked-Dart, JavaScript, Go, Java, PHP, Rust, and SwiftPM modes. The deterministic
script owns filesystem moves, path normalization, reference resolution, patch
generation, and verification. Your job is to prepare or inspect the plan, run
dry-run first, review uncertainty buckets and ignored-import risk, then apply
only when the report is clean enough for the intended change.

## Core Contract

The script computes a **virtual after-tree** before touching disk:

```text
plan -> virtual after-tree -> rewrite refs against after-tree -> apply moves + patches -> verify
```

It updates references by resolved identity, not by hopeful text replacement.
A Markdown link is auto-updated only when its target resolves to a file or
directory being moved. Ambiguous prose is reported, not rewritten.

## TypeScript v1 Boundary

Support standalone `.ts` and `.tsx` file or directory moves and rewrite
identity-resolved Markdown/HTML/config/backtick/exact text references. Use a
stdlib JSON plan as the guaranteed installed format. The script never rewrites
TypeScript or TSX source imports, including relative imports whose target or
referrer is moved; it emits those as `code_imports.ignored` risk records in
the JSON report and under **Ignored TypeScript Imports** in the Markdown report.
Treat remediation as unknown until a TypeScript module resolver proves the
correct spelling. The advisory scanner covers common single-line and multiline
static `import`/`export ... from` forms. For risk identity only, it follows
TypeScript's emitted-file substitution precedence: `.js` probes `.ts`, `.tsx`,
then `.d.ts`; `.mjs` probes `.mts`, then `.d.mts`; `.cjs` probes `.cts`, then
`.d.cts`; the emitted runtime file follows those substitutions. It is not an
exhaustive import inventory.

Do not claim an import-safe module move. Python import rewrites, TypeScript
path aliases, package exports, project references, barrel compatibility,
dynamic imports, and framework-specific routing are out of scope. They need a
named `tsconfig`-aware resolver and separate acceptance evidence.

## Checked-JavaScript Boundary

Enable JavaScript rewriting only with both
`rewrite.code_imports: "update-javascript"` and a named
`javascript.config`. The family-local Node helper loads the host's pinned
TypeScript Compiler API and requires that config to enable `allowJs` and
`checkJs`. It gathers literal AST spans for static `import`/`export`, literal
`import()`, and literal `require()` in `.js`, `.jsx`, `.mjs`, and `.cjs`.

The mover rewrites only explicit relative JavaScript filenames. Bare packages,
aliases, extension inference, framework conventions, and nonliteral dynamic
imports are unsupported; a moved referrer with one of those forms blocks
apply. Preflight and post-apply native checks must be `complete`; a failed
post-apply check reverses the moves and restores source snapshots. Review the
`javascript.status`, `javascript.exact_changes`, and any blocked records in
the JSON report before accepting the move.

## Checked-Go Package Boundary

Enable Go rewriting only with `rewrite.code_imports: "update-go"`. The pilot
automates exactly one non-`main`, leaf package-directory move inside the root
`go.mod` module, for example `pkg/legacy/` to `pkg/workflow/`. It discovers
`go`, `gofmt`, the root module path, and the declared minimum Go version from
`go.mod`; the actual toolchain must be Go 1.22 or newer (and meet a higher
declared minimum). It does not install tools or dependencies.

The bundled Go helper parses source with `go/parser` and rewrites only exact
`ImportSpec.Path` literals equal to the moved package's module import path.
Aliases, blank/dot imports, package names, and comments remain unchanged.
Before applying, the tool rejects workspaces, nested modules, package trees,
`main`, generated/vendor/symlink/cgo/build-tag/go-generate shapes, malformed
source, cgo importers, and any symlinked file or subdirectory within the moved
package. It also reports, without rewriting, an exact old module import path
in first-party `.json`, `.yaml`, `.yml`, `.toml`, `.md`, or `.txt` text; vendor,
generated, symlinked, and binary files are excluded from that bounded scan.
These are unsupported or partial findings, never guessed rewrites.

The transaction runs targeted `gofmt -d` before changing disk, then `gofmt
-w`, an exact source-diff oracle, and `go test ./...` after the move. A failed
native or exact check restores moved and rewritten source. It is not a Go
symbol rename, package-name rename, workspace migration, or general Go
refactor engine.

## Checked-Java Package Boundary

Enable Java rewriting only with `rewrite.code_imports: "update-java"`. The
pilot automates exactly one leaf package-directory move under the same inferred
source root, for example `src/main/java/example/legacy/` to
`src/main/java/example/workflow/`. Both `java` and `javac` must resolve from
`PATH` at JDK 17 or newer; the copied closure installs nothing.

The family-local single-file Java helper parses and attributes every eligible
first-party `.java` source with the JDK compiler tree API and annotation
processing disabled. It rewrites only exact compiler spans for package
declarations in moved files, imports resolving into the moved package, and
fully-qualified type references resolving into that package. A plain string,
comment, reflection name, service descriptor, framework registry, or other old
package occurrence is a blocking `partial` finding, never a text replacement.

Before apply, the mover rejects multiple moves, files instead of directories,
mixed/default or path-mismatched packages, nested package directories,
generated/vendor/build/symlink shapes, malformed source, unresolved
compilation, an invalid destination package, or a source-root change. It
compiles all eligible sources with `javac --release 17 -proc:none` before and
after mutation and checks the exact source diff. A failed post-move compile or
diff restores the moved tree and every rewritten file.

This is not Maven/Gradle/module-path discovery, annotation-processor execution,
Spring/Jakarta/Android reflection analysis, Kotlin support, a type rename, or a
general JVM refactor engine. Hosts requiring those semantics remain outside the
standalone Java v1 claim.

## Checked-PHP Namespace Boundary

Enable PHP rewriting only with `rewrite.code_imports: "update-php"` and an
explicit `php.verification_scripts` list. The pilot automates exactly one leaf
namespace-directory move beneath one unambiguous string-valued Composer PSR-4
`autoload` mapping, for example `src/Legacy/` to `src/Archive/`. Source and
destination must remain under the same mapping. An optional absolute
`php.binary` pins the executable; otherwise `php` resolves from `PATH`. PHP 8.1
or newer is required, and the copied closure installs nothing.

The family-local helper uses `token_get_all(..., TOKEN_PARSE)` to rewrite exact
namespace declarations and qualified-name tokens whose prefix is the moved
namespace. In explicitly named verification scripts it also rewrites only an
exact constant string in a `require`, `require_once`, `include`, or
`include_once` statement when that string points to a PHP file inside the moved
directory. Strings, comments, reflection names, variable includes, and other
dynamic occurrences are blocking `partial` findings.

Only non-generated PHP files beneath Composer production `autoload` roots and
the explicitly named verification scripts are analyzed for edits. Composer
`autoload-dev` tests and generated, vendor, build, and other PHP files are never
rewritten; an old path or namespace in one of those excluded files is blocking
`unsupported` evidence so apply cannot leave a stale identity silently. The
mover also rejects multiple or file moves, nested namespace directories,
generated or non-PHP moved files, symlink boundaries or children, malformed
Composer metadata, malformed PHP, ambiguous/non-string PSR-4 mappings, missing
verification scripts, and unavailable or old PHP runtimes.

Every verification script runs before and after mutation. The post-apply pass
re-tokenizes the resulting project, requires no old namespace/path token to
remain, and compares a whole-host content fingerprint against the exact virtual
after-tree. Any native, token, or exact-diff failure restores the moved tree,
rewritten consumers, changed unrelated files, and removes unexpected regular
files. This is not Composer dependency installation, PHPStan/Psalm semantic
resolution, framework-container discovery, a class rename, a general autoload
migration, or a universal PHP rewrite engine.

## Checked-SwiftPM Target Boundary

Enable Swift rewriting only with `rewrite.code_imports: "update-swift"` and
an explicit `swift` section naming the `swift` and `swiftc` binaries, one
executable smoke product, and its exact expected stdout. The bounded mode moves
exactly one dependency-free regular SwiftPM target directory from
`Sources/<Target>/` to `Sources/<NewDirectory>/`, retains the target/module
identity, and adds the exact static `path:` argument to that target's manifest
entry. It does not rewrite imports or rename modules, products, or symbols.

Dry-run requires a restrictive package dump and standalone source typecheck.
Apply and check require a restrictive SwiftPM build, the executable smoke, and
an exact whole-project diff; failure restores the complete source snapshot.
Dynamic manifests, dependencies, resources, settings, frameworks, Xcode
projects/workspaces, macros/plugins, mixed-language targets, generated files,
symlinks, reflective path strings, and non-Swift target contents remain partial
or unsupported. The copied closure installs no Swift tooling.

## Checked-Rust Module Boundary

Use `knowledge/rust-v1.md` and the standalone
`scripts/rust_module_move.py` only for one conventional leaf module in one
regular Cargo library target. Version 1 moves either `name.rs` to
`new_name.rs` or `name/mod.rs` to `new_name/mod.rs`, updates the exact parent
`mod` declaration and statically resolved first-party Rust paths, and preserves
the reviewed public re-export.

Cargo metadata, check, test, and Clippy run locked/offline across the workspace,
all targets, and all features; rustfmt and an explicit smoke package also gate
apply. `#[path]`, relevant cfg, `include!`, macro-generated modules, build
output, reflective strings, excluded roots, symlinks, multiple/cross-package
moves, and ambiguous topology remain `partial` and block writes. Post-apply or
exact-after-tree failure restores the full pre-apply snapshot. This is not a
crate/package rename or arbitrary Rust refactoring engine.

## Checked-Dart Library Boundary

Use `scripts/dart_library_move.py` for exactly one private Dart library file
or leaf-directory move below `lib/src/`. Dry-run joins exact public-analyzer
directive spans to SDK Analysis Server/LSP-resolved module targets, runs the
native preflight, and writes `evidence.json`. Apply requires both that exact
evidence file and its SHA-256 on the command line; this is the explicit human
approval boundary. Any changed source, package configuration, tool facts,
plan, edit span, or expected after-tree makes the evidence stale and blocks
writes.

The bounded adapter rewrites all impacted resolved first-party `import` and
`export` URIs, including a moved referrer's relative imports and internal
`package:<name>/src/...` imports. At least one stable public barrel must be
declared and must continue to export the moved library. Moving a public
`lib/*.dart` library, changing a public package URI, or crossing packages is
not supported.

The host must explicitly declare itself `disposable` or `user-approved`.
Generated source, parts/part files, augmentations, and dynamic/reflective
loading evidence stop when they occur on the moved path or its resolved direct
impact closure; symlinks stop when a moved or required evidence path crosses
one, and exact old-identity strings remain blocking wherever found. Unrelated
generated, part/augmentation, dynamic-token, and symlink decoys remain
content-addressed in the whole-host proof rather than globally refusing the
move. Conditional directives, unresolved or
excluded-role impacts, multiple moves, public-library moves, and an incomplete
package graph also stop before mutation. Postflight reruns analyzer-backed
facts plus format/analyze/direct-test/smoke, checks the exact whole-host after
tree, and restores the complete byte/mode/symlink snapshot on any failure. The
copied closure installs no Dart SDK or host dependency and never runs Pub
inside the audited host.

## Commands

The installed/on-demand command resolves either supported agent location and
therefore does not assume a repository-local `.claude/skills` tree.

<!-- installed-command:java-move:start -->
```bash
MOVE_PLAN="${MOVE_PLAN:-moves.json}"
MOVE_MODE="${MOVE_MODE:---dry-run}" # --dry-run | --apply | --check
MOVE_REPORT_DIR="${MOVE_REPORT_DIR:-reports/move-path}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/move-path" \
  ".claude/skills/move-path"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "move-path is not installed in .agents/skills or .claude/skills" >&2
  exit 2
fi
if [ -n "${ENGINEERING_SKILLS_PYTHON:-}" ]; then
  if [ ! -x "${ENGINEERING_SKILLS_PYTHON}" ]; then
    printf '%s\n' "ENGINEERING_SKILLS_PYTHON must name an executable Python 3.11+ runtime" >&2
    exit 2
  fi
  HOST_PYTHON="${ENGINEERING_SKILLS_PYTHON}"
elif [ -x ".venv/bin/python" ]; then
  HOST_PYTHON="$(pwd)/.venv/bin/python"
else
  HOST_PYTHON="python3"
fi
case "${MOVE_MODE}" in
  --dry-run|--apply|--check) ;;
  *) printf '%s\n' "MOVE_MODE must be --dry-run, --apply, or --check" >&2; exit 2 ;;
esac
"${HOST_PYTHON}" "${SKILL_ROOT}/scripts/move_path.py" \
  --plan "${MOVE_PLAN}" \
  --project-root "$(pwd)" \
  --report-dir "${MOVE_REPORT_DIR}" \
  "${MOVE_MODE}" \
  --json
```
<!-- installed-command:java-move:end -->

For Rust, invoke the copied standalone adapter instead of `move_path.py`; run
dry-run first and pass its source fingerprint to apply:

<!-- installed-command:rust-move:start -->
```bash
MOVE_PLAN="${MOVE_PLAN:-moves.json}"
MOVE_MODE="${MOVE_MODE:---dry-run}" # --dry-run | --apply | --check
MOVE_REPORT_DIR="${MOVE_REPORT_DIR:-reports/move-path}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/move-path" \
  ".agents/skills/move-path" \
  ".claude/skills/move-path"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "move-path is not installed" >&2
  exit 2
fi
RUST_ARGS=("--plan" "${MOVE_PLAN}" "--project-root" "$(pwd)" \
  "--report-dir" "${MOVE_REPORT_DIR}" "${MOVE_MODE}" "--json")
if [ "${MOVE_MODE}" = "--apply" ]; then
  : "${EXPECTED_SOURCE_SHA256:?Set from the reviewed dry-run report}"
  RUST_ARGS+=("--expected-source-sha256" "${EXPECTED_SOURCE_SHA256}")
fi
python3 "${SKILL_ROOT}/scripts/rust_module_move.py" "${RUST_ARGS[@]}"
```
<!-- installed-command:rust-move:end -->

For Dart, invoke the copied standalone adapter. Dry-run produces the evidence
hash; apply must repeat that reviewed hash explicitly:

<!-- installed-command:dart-move:start -->
```bash
MOVE_PLAN="${MOVE_PLAN:-moves.json}"
MOVE_MODE="${MOVE_MODE:---dry-run}" # --dry-run | --apply | --check
MOVE_REPORT_DIR="${MOVE_REPORT_DIR:-reports/move-path}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/move-path" \
  ".agents/skills/move-path" \
  ".claude/skills/move-path"
do
  if [ -f "${SKILL_CANDIDATE}/scripts/dart_library_move.py" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "Dart move-path external-library closure is not installed" >&2
  exit 2
fi
DART_ARGS=(--plan "${MOVE_PLAN}" --project-root "$(pwd)" \
  --report-dir "${MOVE_REPORT_DIR}" "${MOVE_MODE}" --json)
if [ "${MOVE_MODE}" = "--apply" ]; then
  : "${APPROVED_EVIDENCE_SHA256:?Set from the reviewed dry-run evidence}"
  DART_ARGS+=(--evidence "${MOVE_REPORT_DIR}/evidence.json" \
    --approve-evidence-sha256 "${APPROVED_EVIDENCE_SHA256}")
elif [ "${MOVE_MODE}" = "--check" ]; then
  DART_ARGS+=(--evidence "${MOVE_REPORT_DIR}/evidence.json")
fi
python3 "${SKILL_ROOT}/scripts/dart_library_move.py" "${DART_ARGS[@]}"
```
<!-- installed-command:dart-move:end -->

For a repository checkout, the residue audit remains:

```bash
python3 .claude/skills/move-path/scripts/audit_path_residue.py --plan moves.json
python3 .claude/skills/move-path/scripts/audit_path_residue.py --plan moves.json --exclude 'source-materials/input-bundles/**'
```

Useful options:

- `--project-root DIR` — default is git toplevel, else cwd.
- `--report-dir DIR` — default `.engineering/local/move-path/`.
- `--stage` — stage moved and rewritten paths after apply.
- `--allow-dirty-touched` — bypass dirty touched-file refusal.
- `--json` — print the JSON report to stdout.

## Plan Shape

```json
{
  "version": 1,
  "moves": [
    {
      "id": "rename-source",
      "from": "src/legacy/report.ts",
      "to": "src/reports/current.ts"
    }
  ],
  "reference_scope": {
    "include": ["**/*.md", "**/*.html", "**/*.json", "**/*.yml", "**/*.yaml"],
    "exclude": [".git/**", ".engineering/local/**", "node_modules/**"]
  },
  "rewrite": {
    "markdown_links": "update",
    "markdown_images": "update",
    "html_href_src": "update",
    "backtick_paths": "update",
    "exact_text_paths": "suggest",
    "code_imports": "ignore"
  },
  "safety": {
    "require_clean_touched_files": true,
    "fail_on_broken_links": true,
    "fail_on_blocked": true
  }
}
```

`.yml` and `.yaml` plans remain compatible only when PyYAML is installed.
They are not part of the guaranteed copied-skill path; choose `.json` for a
stdlib-only installation.

For checked JavaScript, add this opt-in branch to the plan:

```json
{
  "rewrite": {
    "code_imports": "update-javascript"
  },
  "javascript": {
    "config": "jsconfig.json"
  }
}
```

For the bounded Go package move, use:

```json
{
  "moves": [
    {"from": "pkg/legacy/", "to": "pkg/workflow/", "mode": "directory"}
  ],
  "rewrite": {"code_imports": "update-go"}
}
```

For the bounded Java package move, use:

```json
{
  "moves": [
    {
      "from": "src/main/java/example/legacy/",
      "to": "src/main/java/example/workflow/",
      "mode": "directory"
    }
  ],
  "rewrite": {"code_imports": "update-java"}
}
```

For the bounded PHP namespace-directory move, use:

```json
{
  "moves": [
    {"from": "src/Legacy/", "to": "src/Archive/", "mode": "directory"}
  ],
  "rewrite": {"code_imports": "update-php"},
  "php": {
    "verification_scripts": ["tests/lint.php", "tests/smoke.php"]
  }
}
```

Set `php.binary` to a reviewed absolute executable path when the host must pin
runtime provenance rather than use `PATH` discovery.

For the bounded SwiftPM target-directory move, use:

```json
{
  "moves": [
    {"from": "Sources/BillingCore/", "to": "Sources/InvoicingCore/", "mode": "directory"}
  ],
  "rewrite": {"code_imports": "update-swift"},
  "swift": {
    "binary": "/usr/bin/swift",
    "swiftc_binary": "/usr/bin/swiftc",
    "smoke_product": "project-smoke",
    "smoke_expected_stdout": "ok\n"
  }
}
```

For the bounded Rust module move, use one file or leaf-directory row and pin
the host-owned toolchain plus an executable smoke expectation:

```json
{
  "moves": [
    {"from": "crates/billing-core/src/invoice/service.rs", "to": "crates/billing-core/src/invoice/invoice_service.rs", "mode": "file"}
  ],
  "rewrite": {"code_imports": "update-rust"},
  "rust": {
    "cargo": "/absolute/path/to/cargo",
    "rustc": "/absolute/path/to/rustc",
    "cargo_clippy": "/absolute/path/to/cargo-clippy",
    "rustfmt": "/absolute/path/to/rustfmt",
    "smoke_package": "rust-move-smoke",
    "smoke_expected_stdout": "invoice:INV-42:125\n"
  }
}
```

For the bounded Dart private-library move, declare the audited host scope,
pre-existing configuration, direct native obligations, and stable barrel:

```json
{
  "version": 1,
  "moves": [
    {
      "from": "lib/src/legacy/invoice_service.dart",
      "to": "lib/src/billing/internal/invoice_service.dart",
      "mode": "file"
    }
  ],
  "rewrite": {"code_imports": "update-dart"},
  "dart": {
    "binary": "/absolute/path/to/dart",
    "host_scope": "disposable",
    "package_config": ".dart_tool/package_config.json",
    "native_test": "test/native_test.dart",
    "smoke": "bin/smoke.dart",
    "smoke_expected_stdout": "INV-42:125\n",
    "public_barrels": ["lib/my_package.dart"]
  }
}
```

## Confidence Buckets

- `auto` — resolved identity, safe to update.
- `suggest` — likely path/reference, requires review.
- `ignore` — outside configured scope or explicitly unsupported.
- `blocked` — unsafe ambiguity; apply fails unless the plan relaxes the
  relevant safety gate.

For directory moves, `exact_text_paths: update` also rewrites nested
plain-text path tokens such as `inputs-1/kb` when they are rooted under
the moved directory. Use `suggest` first when historical prose may be
describing the old layout rather than linking to the current identity.

## Workflow

1. Write or inspect a move plan. Include many moves in one plan when the
   intended transform is one conceptual batch.
2. Run `--dry-run`.
3. Read `.engineering/local/move-path/report.md` and
   `.engineering/local/move-path/report.json`.
4. Resolve `blocked` findings. Review `suggest` findings and every ignored
   TypeScript import that resolves to a move target. In checked-JavaScript
   mode, require a `complete` JavaScript status and review each exact change.
   In checked-Java mode, require a `complete` Java status, review every exact
   package/import/FQCN change, and resolve every dynamic old-package finding.
   In checked-PHP mode, require a `complete` PHP status, review every exact
   namespace/name/require change, confirm the excluded-file inventory, and
   resolve every dynamic or excluded old-identity finding.
   In checked-Swift mode, require a `complete` Swift status, review the one
   target-path manifest change and every moved file, and resolve every refused
   manifest, target, dependency, framework, generated, symlink, or reflective shape.
   In checked-Rust mode, require a `complete` Rust status, review the exact
   module declaration/path edits and source fingerprint, and resolve every
   cfg, macro, include, build-output, symlink, excluded-root, or topology refusal.
   In checked-Dart mode, require a `complete` dry-run, review every exact
   analyzer-resolved directive edit and the declared public barrel, then pass
   the content-addressed evidence hash explicitly to apply. Any partial or
   stale evidence is a stop, not permission to fall back to text replacement.
5. Run `--apply` only after the dry-run report matches the intended
   transform.
6. Run `--check` after manual follow-up edits or before commit.
7. When moved areas include machine-readable manifests, scripts, command
   examples, generated reports, or absolute local paths, run
   `audit_path_residue.py` and review its assumptions, samples, and spot
   checks.

## Git Rules

- Tracked paths move with `git mv`.
- Untracked paths move with filesystem rename and are reported as
  untracked.
- Case-only renames use a temporary path internally.
- Dirty touched files block apply by default.
- `--stage` stages changed old and new paths after apply; otherwise the
  tool leaves the index alone.
- After manual reference or signpost edits, run `--check` before commit. If
  `--stage` was not used, stage the move and rewrite surfaces together so the
  commit is a coherent topology change.
- Keep generated reports under `.engineering/local/move-path/` or clean them
  before handoff. Reports are review artifacts, not source files, unless the
  project explicitly wants to retain them.
- Review low-similarity renames with `git diff -M10 --find-renames` when
  content rewrites make Git show a moved file as delete/add at the default
  threshold.

## Operational Residue Audit

Use `scripts/audit_path_residue.py` when a move touches operational artifacts
that may store paths outside Markdown links: JSON/CSV manifests, lockfiles,
scripts, notebooks, generated reports, command examples, or copied absolute
paths. The helper scans the move plan's reference scope for old relative,
root-relative, absolute POSIX, and Windows-style path spellings, then writes:

The selected move plan is an authority input. Both the mover and residue audit
exclude its exact resolved path even when `reference_scope` matches it; never
rewrite or report the plan's required `from` values as stale residue.

- assumptions that define what the scan can and cannot prove;
- machine-readable findings in
  `.engineering/local/move-path/path-residue-audit.json`;
- a Markdown review report with sampled contexts and spot checks showing
  whether old and new paths exist.

Use repeated `--exclude` flags for known preserved provenance areas when the
goal is operational cleanup rather than source-history rewriting.

When a repeatable residue pattern appears during manual cleanup, prefer adding
or refining a deterministic micro-tool here over relying on an LLM-only sweep.
Keep the helper narrow, fixture-backed, and explicit about what would disprove
its assumptions.

## AI Review

Keep the core deterministic. Use AI review only around the report:

- Are any moves conceptually wrong?
- Are skipped or suggested references likely real breakages?
- Does an ignored TypeScript import require a resolver-aware refactor rather
  than this standalone path/text move?
- Is the scope too broad for one commit?
- Are source snapshots or historical records intentionally excluded?

Do not let an LLM perform unstructured rewrites. If the script cannot
prove identity, the reference is a human review item.
