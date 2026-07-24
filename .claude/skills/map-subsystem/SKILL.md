---
name: map-subsystem
description: Produce or refresh a durable inventory doc for a Python, TypeScript/TSX, checked-JavaScript, Go, bounded Java, Kotlin/JVM, C# 14/.NET 10, Composer PSR-4 PHP, dependency-free SwiftPM, compile-database-backed C/C++, plain locked Ruby gem, Cargo-backed Rust, or bounded plain-Dart subsystem at .engineering/docs/subsystems/<name>.md. Python covers file list, public surface, responsibility table, dependency graph, and convention-compliance score; language branches use family-local native attribution for their bounded facts. No refactor intent — MAP skill in the maintenance nervous system.
argument-hint: "<subsystem-name-or-path> [--refresh]"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: map
best_for: |
  Producing or refreshing a durable inventory doc for a subsystem at
  `.engineering/docs/subsystems/<name>.md` — file list, public surface,
  responsibility table, dependency graph, convention-compliance
  score. MAP skill in the maintenance nervous system.
not_for: |
  Cross-subsystem product workflows (use /map-product-workflow).
  Per-symbol behavior annotation (use /explain-code). Refactor
  execution (use /refactor-subsystem with a spec).
language: any
framework: any
scans: [python, typescript, javascript, go, java, kotlin, csharp, php, swift, c, cpp, ruby, rust, dart]
---

# /map-subsystem

## C# 14 / .NET 10 bounded branch

Trigger this branch only for one target selected from current
`csharp-project.json` and `csharp-semantic-project.json` manifests. The two
manifests must name identical ordered source/test paths, and the copied lexical
and semantic providers must report identical current SHA-256 values for every
selected input. Read `../_csharp-semantic/GUIDE.md` and
`knowledge/csharp-v1.md`, keep both `_csharp` and `_csharp-semantic` beside the
selected skill, and run:

```bash
SKILL_ROOT=".agents/skills/on-demand/map-subsystem"
python3 -I -S "${SKILL_ROOT}/scripts/map_csharp.py" \
  --name "${MAP_NAME:?Set the subsystem name}" \
  --target "${MAP_TARGET:?Set the manifest-owned C# target}" \
  --project-root "$PWD" \
  --output "$PWD/.engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "$PWD/reports/map/${MAP_NAME}/csharp-map.json" \
  --semantic-manifest csharp-semantic-project.json \
  --dotnet "${DOTNET:?Set the pinned .NET 10.0.302 dotnet executable}"
```

The complete artifact records exact source/test hashes, selected namespaces,
types, methods, properties and declared accessibility, plus only direct calls
and references resolved by the pinned SDK-bundled Roslyn helper. Native direct
`csc` compilation, test, and smoke replay are mandatory. Runtime reachability,
reflection and runtime names, delegates, override/interface dispatch,
generated/source-generator inputs, project/solution graphs, and framework
registration remain explicit unresolved boundaries. Any missing, stale,
malformed, incoherent, or authority-mismatched evidence atomically replaces
old structural claims with a claim-free terminal artifact; host source is never
edited.

## Kotlin/JVM 2.4.10 bounded branch

Trigger this branch only for a manifest-selected dependency-free Kotlin/JVM
subsystem with current lexical and semantic manifests whose selected source
paths and hashes agree. Read `../_kotlin/GUIDE.md` and
`../_kotlin-semantic/GUIDE.md`, keep both provider directories beside the
selected skill, and run:

```bash
SKILL_ROOT=".agents/skills/on-demand/map-subsystem"
python3 -I -S "${SKILL_ROOT}/scripts/map_kotlin.py" \
  --name "${MAP_NAME:?Set the subsystem name}" \
  --target "${MAP_TARGET:?Set the manifest-owned Kotlin target}" \
  --project-root "$PWD" \
  --output "$PWD/.engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "$PWD/reports/map/${MAP_NAME}/kotlin-map.json" \
  --kotlinc "${KOTLINC:?Set the absolute Kotlin/JVM 2.4.10 compiler}" \
  --java "${JAVA:?Set the absolute JDK 17 java executable}"
```

The result maps selected declarations, Kotlin visibility, and direct
compiler-resolved calls/references only. Runtime dispatch, overrides,
reflection, callable references, delegates, generated/KAPT/KSP inputs,
Gradle variants, Java/external callers, Android/Multiplatform, frameworks,
JVM ABI, and runtime reachability remain unresolved; the skill never edits
host source.

## Dart v1

Dart v1 uses the SDK-owned `dart language-server --protocol=lsp` through this
skill's stdlib-only provider. It maps selected authored files, direct public
surface, and resolved first-party import/export edges. It uses an external
temporary cache and a pre-existing hashed package configuration; it never runs
Pub or repairs the host.

```bash
SKILL_ROOT=".agents/skills/on-demand/map-subsystem"
MAP_NAME="${MAP_NAME:-dart-subsystem}"
MAP_TARGET="${MAP_TARGET:-lib}"
python3 "${SKILL_ROOT}/scripts/map_dart.py" \
  --name "${MAP_NAME}" --target "${MAP_TARGET}" --project-root "$PWD" \
  --output "$PWD/.engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "$PWD/reports/map/${MAP_NAME}/dart-map.json"
```

The bounded selected configuration is complete when every selected authored
file and first-party edge resolves. Conditional imports/exports, parts,
augmentations, generated code, unresolved URIs, reflection, runtime dispatch,
external dependency internals, and Flutter routes/widgets instead produce an
explicit runtime partial or unavailable boundary; they are never inferred.

<!-- Legacy Go metadata token: scans: [python, typescript, javascript, go] -->
<!-- Legacy PHP/C metadata token: scans: [python, typescript, javascript, go, java, php, swift, c] -->

You are the **orchestrator** for a MAP skill. Given a subsystem name or
path, you produce (or refresh) a durable inventory doc at
`.engineering/docs/subsystems/<name>.md`. You do not edit production code
and you do not refactor.

Before writing in the normal router-plus-external-library journey, run
`scripts/host_migrations.py status` from that current library. Continue only
when it reports `current`; if it reports `ready`, preview and explicitly apply
the migrations first, and if it reports `blocked`, stop with its recovery
instruction. Always stop when both `.claude/docs/subsystems/` and
`.engineering/docs/subsystems/` exist. Never create the canonical directory
beside an unmigrated legacy directory.

This is the MAP job in the five-jobs nervous system (see
`.claude/docs/skill-catalog.md`). The output feeds every downstream
SUSPECT / EXPLAIN / REFACTOR invocation on the same subsystem — so it
needs to be accurate, re-readable without the skill loaded, and
cheaply refreshable.

Procedural detail lives in one knowledge file:

- `knowledge/output-format.md` — the exact shape of
  `.engineering/docs/subsystems/<name>.md` + worked example.
- `knowledge/typescript-v1.md` — the narrow Compiler API model, resolver,
  exclusions, completeness states, and unavailable TypeScript fields.
- `knowledge/go-v1.md` — the active-build Go package-map facts, exclusions,
  partial states, and unavailable Go fields.
- `knowledge/php-v1.md` — the native PHP lint + Composer PSR-4 static-map
  facts, exclusions, terminal states, and deliberate non-semantic boundary.
- `knowledge/cpp-v1.md` — the C++20 compile-database, compiler AST/reference,
  build-target, artifact-verification, and deliberate semantic boundaries.
- `knowledge/ruby-v1.md` — the plain locked-gem Ruby syntax map, literal-load
  evidence, native checks, partial semantic boundary, and deliberate non-claims.
- `knowledge/rust-v1.md` — the Cargo/compiler/stable-LSP evidence chain,
  source roles, partial completeness, lifecycle, and deliberate non-claims.
- `knowledge/csharp-v1.md` — the paired lexical/Roslyn manifest contract,
  exact SDK authority, final map schema, lifecycle, and deliberate non-claims.

## SwiftPM v1

Use `scripts/map_swift.py` only for a dependency-free SwiftPM regular target
under `Sources/` with Swift 6+, `sourcekit-lsp`, and a clean restrictive build.
It writes the durable subsystem Markdown plus JSON evidence from the SwiftPM
target graph, fresh build/index results, symbol graph, SourceKit facts, source
roles, public surface, and cross-target edges. A process exit alone is never a
success claim: every selected target must have explicit fresh index evidence,
and missing, stale, limited, malformed, or mixed-target evidence becomes
`partial`, `unsupported`, or `failed` in both final artifacts.

The boundary excludes dependencies, Xcode projects/workspaces/schemes, Apple
framework semantics, conditional-compilation completeness, macros/plugins,
reflection/dynamic dispatch, and mixed-language targets. The adapter installs
nothing and never mutates host source.

## TypeScript / TSX v1

Use this branch only for a TypeScript/TSX subsystem when the host supplies a
named, project-local `tsconfig.json` and a `typescript` package installed under
that host. It produces a complete module-fact map: eligible source inventory,
exported surface, resolved inbound/outbound static imports (direct relative and
`paths` alias), barrel re-export boundaries, workflow-map participation, and
TypeScript diagnostic counts. It does not infer responsibility clusters or
write judgment-oriented open questions; those fields are explicit
`unavailable`, never silently omitted.

Do not use a lexical import inventory as a substitute. An unresolved specifier
is rendered in the final Markdown and JSON evidence as `partial`; malformed
TypeScript, missing `tsconfig`, missing Node, or missing project-local
TypeScript stops with exit code 2. The mapper accepts a file or directory
target, applies exclusions project-root-relatively even for a direct excluded
target, and never follows an external or internal directory symlink.

The TypeScript command is self-contained in this selected skill. It does not
call the repository renderer, sibling skills, shared adapters, repository
scripts, or a toolkit Python environment. Keep the current Python stages below
unchanged; this is a parallel v1 output contract, not a replacement Python
parser.

### Installed TypeScript map command

Run this verbatim from the target host root after the selected skill is present
at `.agents/skills/map-subsystem` (or from this source checkout at
`.claude/skills/map-subsystem`). It writes only the durable map, its JSON
evidence, and the optional effectiveness row; it never mutates host source.

To make the stock Codex location from a released source, set
`MAP_SUBSYSTEM_SOURCE` to that pinned source/ref and run:

<!-- installed-command:stock-install:start -->
```bash
: "${MAP_SUBSYSTEM_SOURCE:?Set this to the pinned skill source/ref}"
npx --yes skills@1.5.19 add "${MAP_SUBSYSTEM_SOURCE}" \
  --skill map-subsystem --agent codex --copy -y
```
<!-- installed-command:stock-install:end -->

<!-- installed-command:typescript-map:start -->
```bash
MAP_NAME="${MAP_NAME:-typescript-features}"
MAP_TARGET="${MAP_TARGET:-src/features}"
MAP_TSCONFIG="${MAP_TSCONFIG:-tsconfig.json}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/map-subsystem" \
  ".agents/skills/map-subsystem" \
  ".claude/skills/map-subsystem"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "map-subsystem is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/map_typescript.mjs" \
  --target "${MAP_TARGET}" \
  --project-root "$(pwd)" \
  --tsconfig "${MAP_TSCONFIG}" \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/typescript-map.json" \
  --effectiveness-log "reports/_meta/effectiveness.jsonl"
```
<!-- installed-command:typescript-map:end -->

The host's normal native check remains separate evidence. For example, run
`npm run typecheck` (or that host's documented `tsc --noEmit` command) before
and after mapping; the mapper records diagnostics but does not repair them.

## Checked JavaScript v1

Use `map_typescript.mjs --language javascript` only with a host-local
`typescript` package and an explicit `jsconfig.json` or `tsconfig.json` that
sets `allowJs` and `checkJs`. It accepts `.js`, `.jsx`, `.mjs`, and `.cjs`,
maps explicit ESM edges plus bounded literal `require(...)` edges, and leaves
unresolved edges visible. It records config, compiler diagnostics, uncovered
files, compiler-parsed JSDoc, and inferred edge counts. Missing tools/configs
are unsupported, malformed selected JS is syntax-error, and unresolved or
excluded relevant sources are partial. It never falls back to `npx`, a global
compiler, framework inference, or a shared language platform.

<!-- installed-command:javascript-map:start -->
```bash
: "${MAP_TARGET:?Set MAP_TARGET to the checked-JavaScript file or directory to map}"
JSCONFIG="${JSCONFIG:-jsconfig.json}"
MAP_NAME="${MAP_NAME:-javascript-subsystem}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/map-subsystem" \
  ".agents/skills/map-subsystem" \
  ".claude/skills/map-subsystem"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "map-subsystem is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
node "${SKILL_ROOT}/scripts/map_typescript.mjs" \
  --target "${MAP_TARGET}" --project-root "$(pwd)" \
  --tsconfig "${JSCONFIG}" --language javascript \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/javascript-map.json"
```
<!-- installed-command:javascript-map:end -->

This is a standalone host-root command: it resolves the selected skill itself
and does not inherit `SKILL_ROOT` from the TypeScript command above.

## Go v1

Use this branch only from the root of one Go 1.22+ module, with no active
workspace or `go.mod` `replace` directive. It maps one package **directory**
for the current Go build: active non-generated source files, exported
top-level declarations and methods, parser-recorded import spelling, and
first-party inbound/outbound package edges established by `go list -e -json -mod=readonly ./...`.

The selected skill ships one family-local standard-library helper. It uses
`go/parser` and `go/ast` after `go list` has established the active package
graph. It does not use `go/packages`, `go/types`, a language server, or a
shared Go platform. It records ignored build files and makes build matrices,
cgo, runtime dispatch, call identity, responsibility clustering, lint policy,
and behavioral interpretation explicitly unavailable. Generated, vendor,
testdata, test, and symlinked sources do not enter the source inventory. Any
`.go` symlink in the selected package directory is rejected, including a link
to source outside the project root.

An incomplete target package or unresolved first-party import writes a visible
`partial` map. Ordinary active Go files are parsed before cgo causes a
`partial` result, so malformed non-cgo source still writes `failed` and exits
non-zero. Missing or old Go is a prerequisite failure and writes no map.
An active workspace, module replacement, non-root module, excluded/missing
target, or package directory with no eligible source writes `unsupported`.
The final map is complete only for the active `GOOS`/`GOARCH` selection, never
for all build-tag or platform variants.

### Installed Go map command

Run this from the root of the target Go module after the selected skill is
installed. The host's normal native check remains separate evidence: run
`go test ./...` before and after mapping. The mapper is read-only against Go
source and writes only the durable Markdown and JSON evidence.

<!-- installed-command:go-map:start -->
```bash
MAP_NAME="${MAP_NAME:-go-package}"
MAP_TARGET="${MAP_TARGET:-internal/package}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/map-subsystem" \
  ".agents/skills/map-subsystem" \
  ".claude/skills/map-subsystem"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "map-subsystem is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
if ! command -v go >/dev/null 2>&1; then
  printf '%s\n' "Go 1.22+ is required before running the Go map" >&2
  exit 2
fi
go run "${SKILL_ROOT}/scripts/map_go.go" \
  --name "${MAP_NAME}" \
  --target "${MAP_TARGET}" \
  --project-root "$(pwd)" \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/go-map.json"
```
<!-- installed-command:go-map:end -->

## Java v1

Use this branch for one conventional Java package directory with a full JDK
17+. The copied, family-local source launcher attributes all eligible Java
source in its inferred source root through `JavacTask.parse()` and `analyze()`
with `--release 17` and `-proc:none`. It reports public declarations plus
compiler-resolved first-party import and fully-qualified type edges; it makes
Maven/Gradle/classpath/module-path resolution, annotation processors, Kotlin,
runtime dispatch, and build variants explicit boundaries. Syntax errors are
`failed`; unresolved compilation or Kotlin is `partial`; excluded, missing, or
unsafe topology is `unsupported`. Details are in `knowledge/java-v1.md`.

<!-- installed-command:java-map:start -->
```bash
MAP_NAME="${MAP_NAME:-java-package}"
MAP_TARGET="${MAP_TARGET:-src/main/java/example/package}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/map-subsystem" \
  ".agents/skills/map-subsystem" \
  ".claude/skills/map-subsystem"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"; break; fi
done
if [ -z "${SKILL_ROOT}" ] || ! command -v java >/dev/null 2>&1; then
  printf '%s\n' "map-subsystem Java v1 requires an installed skill and JDK 17+" >&2; exit 2
fi
java "${SKILL_ROOT}/scripts/map_java.java" \
  --name "${MAP_NAME}" --target "${MAP_TARGET}" --project-root "$(pwd)" \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/java-map.json"
```
<!-- installed-command:java-map:end -->

## PHP v1

Use this branch for one production directory inside a host-owned Composer
`autoload.psr-4` root, with PHP 8.1+ and Composer 2.2+. The copied,
family-local provider runs native `php -l` across eligible production source,
runs `composer validate --no-check-publish --no-interaction` without installing
or updating dependencies, and establishes only the static first-party class
file/import facts licensed by the validated Composer PSR-4 configuration.

It maps class-like declarations in the selected directory, resolved outbound
`use` imports, and resolved inbound `use` importers from the production PSR-4
roots. It does not resolve dynamic calls, runtime class loading, types,
framework behavior, or project-wide references. Missing/old PHP or Composer,
unsafe/excluded targets, and absent PSR-4 configuration are explicit
`unsupported` artifacts; malformed PHP or failed Composer validation is
`failed`; unresolved first-party PSR-4 imports are `partial`. Details are in
`knowledge/php-v1.md`.

### Installed PHP map command

Run this from the host root after the selected skill is installed. It writes
only `.engineering/docs/subsystems/<name>.md` and `reports/map/<name>/php-map.json`;
it neither follows source/artifact symlinks nor changes host source. Run the
host's own PHP tests separately before and after mapping.

<!-- installed-command:php-map:start -->
```bash
MAP_NAME="${MAP_NAME:-php-subsystem}"
MAP_TARGET="${MAP_TARGET:-src/Subsystem}"
PHP_BIN="${PHP_BIN:-php}"
COMPOSER_BIN="${COMPOSER_BIN:-composer}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/map-subsystem" \
  ".agents/skills/map-subsystem" \
  ".claude/skills/map-subsystem"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ] || ! command -v "${PHP_BIN}" >/dev/null 2>&1; then
  printf '%s\n' "map-subsystem PHP v1 requires an installed skill and PHP 8.1+" >&2
  exit 2
fi
if ! command -v "${COMPOSER_BIN}" >/dev/null 2>&1; then
  printf '%s\n' "map-subsystem PHP v1 requires Composer 2.2+" >&2
  exit 2
fi
"${PHP_BIN}" "${SKILL_ROOT}/scripts/map_php.php" \
  --name "${MAP_NAME}" --target "${MAP_TARGET}" --project-root "$(pwd)" \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/php-map.json" \
  --composer "${COMPOSER_BIN}"
```
<!-- installed-command:php-map:end -->

## C v1

Use this branch for a `.c`/`.i` subsystem whose host supplies Clang and
clangd 21+ plus a current, complete C17 `compile_commands.json`. The copied
helper maps selected translation units, compiler-owned headers, declarations,
public surface, resolved include dependencies, and shared-header edges. It
writes one durable Markdown map and one JSON evidence artifact while preserving
source fingerprints.

The claim is limited to the exact recorded compile-command snapshot. Macro
expansion and inactive branches, function-pointer targets, ABI/layout,
arbitrary build variants, C++, Objective-C, and framework semantics remain
unavailable. Missing, malformed, stale, incomplete, or non-C compile commands
produce explicit terminal artifacts; clangd output is never accepted as a
fallback for missing compiler attribution.

```bash
MAP_NAME="${MAP_NAME:-c-subsystem}"
MAP_TARGET="${MAP_TARGET:-src}"
SKILL_ROOT=".agents/skills/on-demand/map-subsystem"
python3 "${SKILL_ROOT}/scripts/map_c.py" \
  --name "${MAP_NAME}" --target "${MAP_TARGET}" --project-root "$PWD" \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/c-map.json" \
  --clang "$(command -v clang)" --clangd "$(command -v clangd)"
make test
```

## C++20 v1

Use this branch for a C++ subsystem whose host supplies Clang++ and clangd 21+
plus Make and a current, complete C++20 `compile_commands.json`. The copied
helper writes machine-checkable Markdown and JSON containing selected source
and compiler-owned headers, namespace-qualified public declarations with
overload signatures and template declarations, compiler include dependencies,
direct compiler-resolved internal/inbound references, and project-local Make
target relationships.

Completeness is limited to the exact recorded compile-command snapshot.
Virtual/dynamic dispatch, reflection/runtime registration, all possible
template instantiations, macro/inactive-branch completeness, link-time
behavior, and unrecorded build variants remain explicit unsupported fields.
Missing, malformed, stale, incomplete, mismatched-root, wrong-language, or
fallback databases fail closed. Compiler, clangd attribution, or Make database
failures write `failed` artifacts and exit 2. `status` remains distinct from
the compiler `diagnostic_state`.

Run this verbatim from the target host root after the selected skill is copied.
Run the host's restrictive native C++20 build/tests and executable smoke before
and after mapping. The final verification command rejects stale sources or
tampered Markdown/JSON using recorded hashes.

<!-- installed-command:cpp-map:start -->
```bash
MAP_NAME="${MAP_NAME:-cpp-subsystem}"
MAP_TARGET="${MAP_TARGET:-src}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/map-subsystem" \
  ".agents/skills/map-subsystem" \
  ".claude/skills/map-subsystem"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "map-subsystem is not installed" >&2
  exit 2
fi
python3 "${SKILL_ROOT}/scripts/map_cpp.py" \
  --name "${MAP_NAME}" --target "${MAP_TARGET}" --project-root "$(pwd)" \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/cpp-map.json" \
  --clangxx "$(command -v clang++)" --clangd "$(command -v clangd)" \
  --make "$(command -v make)"
python3 "${SKILL_ROOT}/scripts/map_cpp.py" \
  --name "${MAP_NAME}" --target "${MAP_TARGET}" --project-root "$(pwd)" \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/cpp-map.json" --verify-artifacts
```
<!-- installed-command:cpp-map:end -->

## Ruby v1

Use this branch for a plain Ruby 3.3+ gem with a root `Gemfile`, lockfile,
gemspec, and Bundler 2.6+. The copied helper writes a useful, bounded static
map: source roles and hashes; module, class, and method declarations; literal
load-layout matches; reopening and mixin syntax; constant-reference candidates;
and explicit test/executable evidence. It installs nothing and never mutates
host source.

Ruby has a supported bounded static-map contract. Its successful artifact still
reports runtime `partial` completeness when dynamic loading, reflection,
metaprogramming, callbacks, Rails/Zeitwerk, or runtime identity remain
unresolved. See `knowledge/ruby-v1.md` for the exact boundary.

<!-- installed-command:ruby-map:start -->
```bash
MAP_NAME="${MAP_NAME:-ruby-subsystem}"
MAP_TARGET="${MAP_TARGET:-lib}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/map-subsystem" \
  ".agents/skills/map-subsystem" \
  ".claude/skills/map-subsystem"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "map-subsystem is not installed" >&2
  exit 2
fi
python3 "${SKILL_ROOT}/scripts/map_ruby.py" \
  --name "${MAP_NAME}" --target "${MAP_TARGET}" --project-root "$(pwd)" \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/ruby-map.json" \
  --ruby "$(command -v ruby)" --bundle "$(command -v bundle)"
```
<!-- installed-command:ruby-map:end -->

## Rust v1

Use this branch for one Cargo workspace package when the host owns Rust/Cargo
1.85+, rust-analyzer, a current lockfile, and a compiler-clean locked/offline
workspace. The copied helper maps package/target/dependency provenance,
selected ordinary module and re-export paths, compiler diagnostics, selected
host cfg evidence, source roles, and stable-LSP symbols/definitions. It never
uses rust-analyzer's unstable CLI or private rustc interfaces.

Rust has a supported bounded selected-configuration contract. Its artifact
still reports runtime `partial` completeness across macro expansion,
build-script `OUT_DIR`, `include!`, unselected cfg/feature/target variants, and
runtime trait-object dispatch. See `knowledge/rust-v1.md` for the exact
boundary.

<!-- installed-command:rust-map:start -->
```bash
MAP_NAME="${MAP_NAME:-rust-subsystem}"
MAP_TARGET="${MAP_TARGET:-crates/core}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/map-subsystem" \
  ".agents/skills/map-subsystem" \
  ".claude/skills/map-subsystem"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "map-subsystem is not installed" >&2
  exit 2
fi
python3 "${SKILL_ROOT}/scripts/map_rust.py" \
  --name "${MAP_NAME}" --target "${MAP_TARGET}" --project-root "$(pwd)" \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/rust-map.json" \
  --cargo "$(command -v cargo)" --rustc "$(command -v rustc)" \
  --rust-analyzer "$(command -v rust-analyzer)"
python3 "${SKILL_ROOT}/scripts/map_rust.py" \
  --name "${MAP_NAME}" --target "${MAP_TARGET}" --project-root "$(pwd)" \
  --output ".engineering/docs/subsystems/${MAP_NAME}.md" \
  --evidence "reports/map/${MAP_NAME}/rust-map.json" --verify-artifacts
```
<!-- installed-command:rust-map:end -->

## How success is judged

- Python maps are complete per `knowledge/output-format.md`: file inventory,
  public-vs-private surface, responsibility clusters, dependency graph, and
  convention-compliance score. TypeScript/TSX v1 maps are complete per
  `knowledge/typescript-v1.md`: eligible inventory, exported surface, resolved
  module edges, workflow participation, and applicable compliance; intentionally
  unavailable fields must remain explicit. Go v1 maps are complete only for
  the active package/build facts in `knowledge/go-v1.md`; package-resolution
  gaps remain visible as `partial`, and unavailable Go facts stay explicit.
  Java v1 follows `knowledge/java-v1.md`: only error-free JavacTask-attributed
  source facts are complete; unresolved or Kotlin coverage stays `partial`.
  PHP v1 follows `knowledge/php-v1.md`: only linted, validated Composer PSR-4
  class-file/import facts are complete; dynamic semantics remain unavailable.
  C v1 is complete only for the exact current C17 compile-command snapshot and
  compiler dependency closure; every listed non-claim remains explicit.
  C++20 v1 follows `knowledge/cpp-v1.md`: complete means a current, exact
  C++20 compile database plus successful compiler/clangd attribution across
  every production translation unit. Direct static references are
  compiler-resolved; dynamic/reflection/template-instantiation boundaries
  remain explicit and final artifact/source hashes must verify.
  Ruby v1 follows `knowledge/ruby-v1.md`: its bounded static-map contract is
  supported for the selected plain-gem snapshot, while the artifact reports
  runtime `partial` completeness because runtime reachability and dynamic
  behavior are not inferred. Rust v1 follows `knowledge/rust-v1.md`: its
  bounded selected-configuration contract is supported, while the artifact
  reports runtime `partial` completeness across macros, build output, include
  contents, variants, and runtime trait dispatch. C# v1 follows
  `knowledge/csharp-v1.md`: complete means exact paired-manifest path/hash
  coherence, pinned direct-csc native gates, and SDK-bundled Roslyn binding;
  every runtime/reflection/delegate/dispatch/generated/project/framework
  boundary remains explicit.
- On `--refresh`, the doc opens with a diff section against the prior
  version — what changed, not just what is.
- The run cites artifact truth: pasted `render_doc.py` `wrote ...`
  output, the final doc path, and the effectiveness-row write or the
  exact logger failure.
- No judgment leaked: the map counts and reports; "should be split"
  verdicts belong to the SUSPECT skills downstream.
- Beyond the doc, writes are limited to the `reports/map/<name>/`
  scratch dir and the `reports/_meta/effectiveness.jsonl` line.
Write toward these gates from Stage 0.

## Core beliefs

The map is a living, refreshable fact artifact: distinguish public surface,
workflow context, responsibility count, and dependency evidence without saying
what should be split. Keep language resolution family-local until a second
accepted consumer proves a shared contract.

## Argument parsing

Two forms:

### Form A — subsystem name (preferred)
`views-crawling`, `services-ai-training`, `services-discovery-field-matcher`.
Names use kebab-case, match `<layer>-<domain>`.

Resolve to a path by convention: the first segment is usually the layer
(`views`, `services`, `tasks`, `models`, `scripts`, `skills`), and the
remaining segments name the module or package. Check for an exact file
or directory match before inference. If the name doesn't resolve, ask
once for a path; don't guess.

### Form B — explicit path
`core/views/crawling.py`, `core/services/discovery_field_matcher/`,
`core/tasks/exports.py`.

Directories and files both work. The subsystem name is derived from
the path (path segments joined with `-`, minus `core-`).

### `--refresh` flag
Indicates a re-run against an existing `.engineering/docs/subsystems/<name>.md`.
The skill MUST produce a diff section at the top of the new doc
summarizing what changed since the previous version's "Regenerated"
timestamp.

## Python scope

- **Target:** a single subsystem (one file or one directory package).
- **Worktree:** current working directory.
- **Python:** `.venv/bin/python` (never bare `python`).
- **Output:** `.engineering/docs/subsystems/<name>.md`, scratch artifacts
  under `reports/map/<name>/`, and one effectiveness row under
  `reports/_meta/`. Never touches production code.

## Python pipeline stages

Each stage has a contract — what it reads, what it writes. Scripts run
with `.venv/bin/python` and capture stderr.

### Stage 0 — Resolve target + setup

**Pre:** argument parsed. **Post:** `$OUTPUT_PATH` resolved,
`$SCRATCH` exists under `reports/map/<name>/`.

```bash
NAME="<resolved subsystem name>"
TARGET="<resolved subsystem path>"
TS=$(date -u +%Y%m%d-%H%M%S)
REFRESH=0  # set to 1 when --refresh was passed
OUTPUT_PATH=".engineering/docs/subsystems/${NAME}.md"
MAP_DIR="reports/map/${NAME}"
SCRATCH="${MAP_DIR}/scan-${TS}"
mkdir -p "${SCRATCH}" reports/_meta .engineering/docs/subsystems
ln -sfn "scan-${TS}" "${MAP_DIR}/latest"
PRIOR_DOC="$([ -f "$OUTPUT_PATH" ] && printf '%s' "$OUTPUT_PATH" || true)"
```

If `$OUTPUT_PATH` exists and `--refresh` was not passed, warn and
exit with guidance to re-run with `--refresh`.

### Stage 1 — File inventory

**Pre:** target resolved. **Post:** `$SCRATCH/files.jsonl` — one line
per file in the subsystem with `{path, loc, last_commit, last_author}`.

Use `find` (well — `Glob`) for the file list and
`git log --format=...` for per-file last-commit info. Skip `.venv/`,
`__pycache__/`, migrations.

### Stage 2 — Public surface + AST inventory

**Pre:** file list. **Post:** `$SCRATCH/symbols.jsonl` — one line per
top-level declaration with `{file, name, kind, is_public, decorators,
lineno, loc}`. `is_public` = not leading underscore AND not in a
module-level `__all__` that excludes it.

Reuse `scripts/chunk_file.py --format json` for files > 2,000 LOC (it
emits declarations). For smaller files, run an AST walk directly.

### Stage 3 — Responsibility clusters (SRP-lite)

**Pre:** symbols.jsonl. **Post:** `$SCRATCH/clusters.jsonl` — one line
per cluster with `{cluster, symbols, loc_sum, domain_hint}`.

Group top-level symbols by noun extraction on the function/class name
(e.g. `upload_*`, `download_*`, `process_*` become three clusters).
Apply the SRP sentence test over the cluster names — if three or more
"and"-joinable domains show up, flag the file as omnibus-candidate.

Do **not** run a full SOLID audit here — the full audit lives in
`refactor-subsystem` §1.2.5. The MAP skill just counts clusters.

### Stage 4 — Dependency graph

**Pre:** file list. **Post:** `$SCRATCH/deps.json` with
`{internal_imports, external_imports, inbound}` — inbound edges come
from a repo-wide grep for `from <subsystem> import` plus
`import <subsystem>`. If `.claude/docs/workflows/` contains maps that
name the subsystem, also write `$SCRATCH/workflows.json` as a list of
`{name, path, reason}` rows.

Bounded cost: use `Grep` with glob-filtering, cap at 200 files per
direction.

### Stage 5 — Convention-compliance score

**Pre:** file list. **Post:** `$SCRATCH/compliance.json` with per-rule
counts.

Run:
- `.venv/bin/ruff check <target> --select F,E,B,BLE --output-format=json`
  and capture stdout/stderr plus exit code; non-zero means violations or
  a tool failure, not an automatic skill failure.
- `.venv/bin/python scripts/lint/silent_catch.py <target>` and count
  reported violations; non-zero is recorded in `compliance.json`.
- Future: new rule counters as `/prevent-regression` adds them.

Record raw counts. Do not fail the skill on non-zero counts — that's
guard territory.

### Stage 6 — Render the subsystem doc

**Pre:** stages 1–5 outputs. **Post:** `$OUTPUT_PATH` written.

Format per `knowledge/output-format.md`: front matter; refresh diff; files;
public surface; clusters; dependency and workflow evidence; compliance; and
open questions for `/explain-code`.

Then run the renderer exactly:

```bash
HEADER="<one-paragraph subsystem summary>"
PRIOR_ARGS=()
if [ -n "${PRIOR_DOC}" ] && [ "${REFRESH:-0}" = "1" ]; then
  PRIOR_ARGS=(--prior-doc "${PRIOR_DOC}")
fi

.venv/bin/python .claude/skills/map-subsystem/scripts/render_doc.py \
  --name "${NAME}" \
  --target "${TARGET}" \
  --scratch "${SCRATCH}" \
  --output "${OUTPUT_PATH}" \
  "${PRIOR_ARGS[@]}" \
  --header "${HEADER}" \
  --effectiveness-log reports/_meta/effectiveness.jsonl
```

Paste the renderer's `wrote <output> (<bytes> bytes)` line in the
summary. That line, the output file, and the effectiveness row are the
truth artifacts for Stages 6-7.

### Stage 7 — Append to effectiveness log

`render_doc.py` appends the `map-<name>-<ts>` row when requested. Verify it;
if it fails after a rendered doc, keep the doc and report that exact failure.

### Stage 8 — Summarize to user

In ≤10 lines, cite the output, timestamp, file/public/cluster/compliance
counts, and one evidence-based next job (`/fix-workflow`, a SUSPECT skill,
`/find-dormant`, or `/explain-code`). The document remains the source of truth.

## Non-goals

- Refactoring.
- Detecting smells (that's SUSPECT skills).
- Proposing fixes.
- Editing durable files except `$OUTPUT_PATH` and the effectiveness log.
- Writing scratch outside `reports/map/<name>/`.
- Running tests.
- Generating diagrams that require non-repo tooling (graphviz, mermaid
  renderers). Plain markdown only.

## When things go sideways

| Symptom | Action |
|---|---|
| Target path doesn't exist | Abort with a one-line error + suggestion to re-run with the correct path |
| `scripts/chunk_file.py` errors on a non-Python file | Flag in the doc's Files section; skip AST inventory for that file |
| Existing doc + no `--refresh` flag | Warn and exit; don't overwrite |
| A required scratch file is missing before Stage 6 | Stop before rendering; name the missing file and the stage that should have produced it |
| `render_doc.py` exits non-zero | Paste stdout/stderr, do not claim the doc or effectiveness row was written |
| `render_doc.py` writes the doc but not the effectiveness row | Keep the doc; report the missing log row and rerun only Stage 7 if needed |
| `ruff` is unavailable or exits 2 | Record the tool failure in `compliance.json`; do not report zero violations |
| `reports/_meta/` missing | Create it — `reports/_meta/README.md` is already tracked so the dir exists in committed state |

## Repository layout

```
.claude/skills/map-subsystem/
├── SKILL.md                      # this file — orchestrator
├── scripts/
│   ├── map_go.go                 # Go v1 package map + final artifacts
│   ├── map_java.java             # Java v1 package map + final artifacts
│   ├── map_csharp.py             # C# v1 paired-provider map + final artifacts
│   ├── map_php.php               # PHP v1 Composer PSR-4 static map + final artifacts
│   ├── map_c.py                  # C v1 compile-database map + final artifacts
│   └── render_doc.py             # Python Stages 6-7 — renders the doc + appends log
└── knowledge/
    ├── go-v1.md                  # bounded active-build Go contract
    ├── java-v1.md                # bounded compiler-attributed Java contract
    ├── csharp-v1.md              # bounded paired C# lexical/Roslyn contract
    ├── php-v1.md                 # bounded native PHP + Composer contract
    └── output-format.md          # Python doc structure + worked example
```
