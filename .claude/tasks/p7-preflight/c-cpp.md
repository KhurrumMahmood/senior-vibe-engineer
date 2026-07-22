# P7 preflight: C and C++

Date: 2026-07-22
Host: macOS 26.5.2 (`arm64-apple-darwin25.5.0`)
Scope: read-only language preflight; no product support was implemented or
claimed.

## Recommendation

Proceed with a **bounded family pilot**, but publish **separate `c` and `cpp`
profiles and separate 22-skill disposition truth**. Share only tool discovery,
process execution, artifact lifecycle, and narrowly identical Clang mechanics.
C and C++ are not one semantic profile: their driver/language modes, standard
flags, suffixes, headers, declaration models, linkage rules, diagnostics,
idioms, and refactoring hazards differ. A `.h` file is especially not enough
to infer language; its owning translation unit and compile command must decide,
or the inventory must report it as ambiguous/mixed.

Pilot now:

1. inventory plus raw-token/AST syntax with installed Apple Clang 21;
2. one semantic final outcome (`map-subsystem`) only against fixture-owned,
   trustworthy `compile_commands.json`; and
3. explicit missing/invalid compile-database behavior.

Defer source mutation (`move-path`) until the semantic pilot proves source
lineage, header ownership, conditional-compilation behavior, and a native
same-fixture build/test. Do not use clangd's fallback command as semantic
success. The local host has no representative first-party C/C++ project or
compile database, CMake is absent, and the available Ninja shim is unusable.

## Exact local evidence

All Python probes used
`<repo>/.venv/bin/python`
explicitly. No install or network command was run.

### Platform and compiler family

```text
$ uname -m
arm64
$ sw_vers
ProductName: macOS
ProductVersion: 26.5.2
BuildVersion: 25F84
$ xcode-select -p
/Library/Developer/CommandLineTools
$ xcrun --show-sdk-path
/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk
$ clang --version
Apple clang version 21.0.0 (clang-2100.1.1.101)
Target: arm64-apple-darwin25.5.0
InstalledDir: /Library/Developer/CommandLineTools/usr/bin
$ clangd --version
Apple clangd version 21.0.0 (clang-2100.1.1.101)
Features: mac+xpc
Platform: arm64-apple-darwin25.5.0
$ clang -print-resource-dir
/Library/Developer/CommandLineTools/usr/lib/clang/21
$ clang -print-target-triple
arm64-apple-darwin25.5.0
```

`cc`, `gcc`, `c++`, and `g++` all resolve to the same Apple Clang 21 toolchain;
their names do not demonstrate independent GCC/libstdc++ coverage.

### Build, database, and analysis tools

| Capability | Observed result |
|---|---|
| `clang`, `clang++`, `clangd` | `/usr/bin/...`; Apple 21.0.0; usable |
| `make` | `/usr/bin/make`; GNU Make 3.81; `make -f - -n all` exited 0 and printed `echo offline-build` |
| `cmake`, `ctest`, `meson`, `bazel`, `buck2` | missing |
| `ninja` | only `<user-home>/.pyenv/shims/ninja`; `ninja --version` timed out after 5 seconds, so unusable |
| `xcodebuild` | present, but `xcodebuild -version` exited 1 because the active developer directory is Command Line Tools rather than Xcode |
| `pkg-config` | `/opt/homebrew/bin/pkg-config`, version 2.5.1 |
| `bear`, `intercept-build` | missing; no Make compile-database capture tool |
| `clang-tidy`, `clang-format`, `clang-query`, `clang-check`, `clang-refactor`, `llvm-config` | missing; no local LibTooling CLI/development discovery surface |
| `scan-build`, `cppcheck`, `iwyu`/`include-what-you-use`, `flawfinder`, `infer`, `cpplint` | missing |
| Clang Static Analyzer driver | usable through `clang --analyze`; a null-dereference sample emitted `core.NullDereference` (exit 0 with a warning) |
| object/debug utilities | `nm`, `otool`, `dsymutil`, `ar` present; `lldb --version` timed out after 5 seconds and is not a preflight dependency |

The first-party tree scan (excluding `.git`, `.venv`, caches, and
`.claude/tasks/tool-evaluations`) found **0 C-family source/header files and 0
build/compile markers**. There is no `compile_commands.json` in a usable host.
Vendored Python packages under the tool-evaluation area contain C/C++ files;
they are evidence for vendor exclusion, not a representative host.

Clang can emit a compilation-database fragment without another generator:

```text
$ printf 'int f(void){return 0;}\n' | clang -x c -std=c17 -MJ /dev/stdout -c -o /dev/null -
{ "directory": "<repo>",
  "file": "-", "output": "/dev/null", "arguments": [...] },
exit 0
```

That proves `-MJ` exists, not that arbitrary Make/Xcode/Bazel hosts have a
complete or trustworthy database. A host-owned generator/database remains the
semantic gate.

### Offline syntax and fact feasibility

The following stdin-only checks used the installed SDK and completed with dead
HTTP/HTTPS/ALL proxy endpoints; no dependency resolution was attempted:

| Command | Result |
|---|---|
| `clang -x c -std=c17 -Wall -Wextra -pedantic -fsyntax-only -` | valid fixture exit 0 |
| `clang -x c -std=c23 -Wall -Wextra -pedantic -fsyntax-only -` | valid fixture exit 0 |
| `clang++ -x c++ -std=c++20 -Wall -Wextra -pedantic -fsyntax-only -` | valid fixture exit 0 |
| `clang++ -x c++ -std=c++23 -Wall -Wextra -pedantic -fsyntax-only -` | valid fixture exit 0 |
| the C17 command on malformed input | exit 1; 2 diagnostics |
| the C++20 command on malformed input | exit 1; 1 diagnostic |
| the C17 and C++20 commands with `http_proxy`, `https_proxy`, and `ALL_PROXY` set to `http://127.0.0.1:9` | both exit 0 |
| `clang -x c -std=c17 -Xclang -ast-dump=json -fsyntax-only -` | exit 0; 70,663-byte parseable `TranslationUnitDecl` JSON |
| `clang++ -x c++ -std=c++20 -Xclang -ast-dump=json -fsyntax-only -` | exit 0; 76,055-byte parseable `TranslationUnitDecl` JSON |
| `clang -x c -std=c17 -Xclang -dump-raw-tokens -fsyntax-only -` | exit 0; retained the sample `// decision: ...` comment and exact locations |

AST JSON and raw-token output are promising bounded provider inputs, but they
are compiler CLI output rather than a promised stable cross-version schema.
Pin/version-gate the provider and preserve `partial`/`failed` outcomes.

The compile-database boundary is concrete:

```text
$ clangd --check=/dev/null --log=verbose
exit 0
... Loading compilation database...
... Failed to find compilation database for /dev/null
... Generic fallback command is: ... clang -xobjective-c++-header ... /dev/null
```

This false-friendly exit 0 is why the doctor must inspect clangd's database
status and effective command. The fallback guessed Objective-C++ header mode;
it cannot prove either C or C++ project semantics.

## Separate profile truth

### C profile

- Primary source: `.c`; preprocessed source: `.i`.
- Headers/includes: `.h` and `.inc`, but classify as C only from an owning C
  compile command or explicit fixture/profile rule; otherwise `ambiguous`.
- Standards are profile/host facts (`-std=c11`, `c17`, `c23`, GNU variants),
  as are target, sysroot, defines, include paths, ABI, freestanding/hosted mode,
  and language extensions.
- Exclude Objective-C (`.m`), Objective-C++ (`.mm`), CUDA (`.cu`, `.cuh`),
  OpenCL (`.cl`), assembly (`.s`, `.S`), and generated bindings from baseline C
  unless a supplementary profile explicitly selects them.
- C-specific risks include macro-generated declarations, conditional builds,
  translation-unit-local `static` linkage, function pointers, opaque structs,
  ABI/layout, and generated headers.

### C++ profile

- Primary source: `.cc`, `.cpp`, `.cxx`, `.c++`, and case-sensitive `.C`;
  preprocessed source: `.ii`.
- Header/template includes: `.hpp`, `.hh`, `.hxx`, `.h++`, `.ipp`, `.inl`,
  `.tpp`; `.h`/`.inc` remain ambiguous without owning compile commands.
- Module interface/partition suffixes such as `.cppm`, `.ixx`, and `.mpp` must
  start partial until the selected compiler/build graph proves them.
- Standards (`c++17`, `c++20`, `c++23`, GNU variants), standard library,
  modules flags, target/sysroot, defines, include order, and ABI are host facts.
- C++ adds overloads, templates/instantiations, namespaces, ADL, implicit
  operations, exceptions/RTTI, concepts, header-only definitions, ODR, and
  modules; those materially change semantic and mutation confidence.

### Shared roles and boundaries

Both profiles need first-party source, tests/benchmarks, generated, vendor,
build output, configuration/tooling, declaration/header, and ambiguous roles.
Typical evidence includes `src/`, `include/`, `tests/`, `benchmarks/`;
generated/build paths such as `build/`, `out/`, `cmake-build-*`, `CMakeFiles/`,
and `bazel-*`; and vendor paths such as `third_party/`, `external/`, `_deps/`,
`vendor/`, `vcpkg_installed/`, and package-manager caches. Names are defaults,
not proof; explicit build metadata and host overrides win.

Build markers include `compile_commands.json`, `CMakeLists.txt`, Makefiles,
`meson.build`, Bazel `BUILD`/`MODULE.bazel`/`WORKSPACE`, Xcode projects,
Visual Studio solutions/projects, Autotools files, `conanfile.*`, and
`vcpkg.json`. Baseline language support must not rewrite or infer all of these.
Treat CMake, Make, Meson, Bazel, Xcode/MSBuild, embedded cross-builds, and
package managers as build-system profiles. Treat Qt, ROS, Unreal, GLib/GObject,
kernel/freestanding, embedded/RTOS, MPI/HPC, CUDA, and platform frameworks as
supplementary framework/domain profiles after baseline language truth.

## Established tooling and idiom sources

Use the host compiler/build tools instead of recreating their checks:

- language/diagnostics: the selected ISO C or ISO C++ revision, Clang driver
  diagnostics, Clang Static Analyzer, and sanitizers in native verification;
- idioms: C Core Guidelines do not exist as a direct analogue; use the chosen C
  standard plus project policy, SEI CERT C where security is in scope, and
  MISRA only for an explicitly licensed/safety profile. For C++, use the C++
  Core Guidelines and project-selected clang-tidy check sets;
- formatting/style: host-owned `.clang-format` and clang-format when present;
- build/test: the selected build system's own docs/commands, CTest when CMake
  owns the host, and the host's existing test runner;
- dependency/include policy: host-owned clang-tidy, IWYU, cppcheck, or other
  configured analyzers when already installed.

The router/doctor may name missing tools and installation guidance but must not
install them. Do not present cppreference, generic style guides, or a default
clang-tidy preset as the host's standard. Compiler warnings are evidence, not
automatic proof of portability, safety, or best-practice conformance.

## Representative fixture feasibility

Two separate small fixtures are feasible and necessary:

1. **C17/C23 Make fixture:** two translation units, public and private headers,
   a function pointer, file-local state, macros/conditional branches, tests,
   generated and vendor decoys, malformed source, symlink/boundary case, a
   committed fixture `compile_commands.json`, and `make test` using `clang`.
2. **C++20/C++23 Make fixture:** two translation units plus a header-only
   template, overloads/namespaces, an enum/class relationship, macro/conditional
   branch, the same source-role/negative cases, a separate committed database,
   and `make test` using `clang++`.

Make 3.81 and Clang 21 are sufficient for these deliberately portable fixtures.
Do not make CMake a pilot prerequisite merely to compensate for its local
absence. Database entries must contain real absolute fixture paths, language
mode, standard, defines, include roots, and target-relevant flags. Conformance
must test missing, malformed, stale, mismatched-directory, and incomplete
databases, plus valid-to-failed and failed-to-valid same-destination reruns.

## Initial 22-skill disposition forecast

This is preflight guidance, not earned matrix publication. No C/C++ skill is
currently `supported`: there is no profile/provider/final-outcome evidence.
`partial candidate` below means a bounded implementation could honestly earn
partial support after its final artifact passes; `unsupported initially` means
retain unsupported through the first pilot unless later expansion proves more.

| Language-level skill | C | C++ | Initial rationale |
|---|---|---|---|
| `adapt-project` | partial candidate | partial candidate | Inventory/build-marker output is feasible; no final C/C++ adapter artifact exists, and framework/build selection must remain explicit. |
| `audit-decisions` | partial candidate | partial candidate | Raw Clang tokens retain comments and locations; association across macros/templates and generated headers is not proven. |
| `explain-code` | partial candidate | partial candidate | Lexical/AST explanation can be useful per TU; project meaning needs the effective compile command, with C++ templates/overloads adding uncertainty. |
| `extract-enum` | unsupported initially | unsupported initially | Proposal safety needs use/reference, ABI/layout, macro, and build compatibility facts; C++ scoped enums, overloads, and templates raise the bar. |
| `find-comment-drift` | **pilot partial candidate** | **pilot partial candidate** | Best lexical pilot: raw tokens prove comments/spans offline; semantic comment-to-symbol claims remain bounded. |
| `find-complexity-hotspots` | partial candidate | partial candidate | Per-TU AST control-flow metrics are feasible; macros, generated code, templates, and instantiations require explicit counting policy. |
| `find-concept-divergence` | partial candidate | partial candidate | Identifier/comment vocabulary is lexical; preprocessor spelling and C++ overload/template identity prevent semantic claims. |
| `find-dormant` | unsupported initially | unsupported initially | Reachability needs roots, link/build variants, callbacks/function pointers, conditional compilation, and cross-TU facts; templates/virtual dispatch deepen C++ limits. |
| `find-duplication` | partial candidate | partial candidate | Token-normalized candidates are feasible, but preprocessor branches and template/macro expansion prevent semantic-equivalence claims. |
| `find-folder-topology-drift` | partial candidate | partial candidate | Filesystem/source roles are feasible; build targets and ambiguous headers prevent a complete project-topology claim. |
| `find-implicit-state` | unsupported initially | unsupported initially | Globals/statics, aliasing, callbacks, TLS, and conditional compilation require semantics; C++ constructors, RAII, templates, and hidden special members add effects. |
| `find-incomplete-sweep` | unsupported initially | unsupported initially | Completeness across declarations, definitions, build variants, headers, macros, and generated files requires trusted project facts. |
| `find-omnibus` | partial candidate | partial candidate | AST/file metrics can nominate large mixed-responsibility units; header reuse and C++ template instantiation require deduplication policy. |
| `find-semantic-duplication` | unsupported initially | unsupported initially | Equivalent behavior cannot be established from token/AST similarity, especially across macros, aliasing, overloads, templates, and undefined-behavior edges. |
| `find-standard-gaps` | partial candidate | partial candidate | Compiler diagnostics/analyzer and host tools can be orchestrated; clang-tidy/IWYU/cppcheck are absent and project policy must choose standards/checks. |
| `map-subsystem` | **semantic pilot partial candidate** | **semantic pilot partial candidate** | A compile-DB-backed clangd/Clang fixture can prove declarations/references/edges; no-DB fallback must be partial/failed, never success. |
| `move-path` | unsupported initially; deferred mutation | unsupported initially; deferred mutation | Moving sources/headers can break includes and build manifests; C++ also has modules/header-only/ODR risk. Require semantic lineage and native build/test first. |
| `prevent-regression` | unsupported initially | unsupported initially | Guard generation must consume an accepted producer artifact and compile/test in the host; no such C/C++ producer contract exists yet. |
| `propose-boundary` | unsupported initially | unsupported initially | Boundary proposals need a trustworthy target/reference graph across TUs and build variants; C++ templates/virtual calls complicate edges. |
| `propose-folder-reorganization` | unsupported initially | unsupported initially | Requires semantic graph plus build-system-specific manifest impact; baseline language support must not pretend to understand every build system. |
| `rename-concept` | unsupported initially | unsupported initially | Safe reference coverage must prove macro, declaration/definition, linkage, and textual-build uses; C++ overloads/templates/ADL/modules raise collision risk. |
| `unify-shadows` | unsupported initially | unsupported initially | A proposal needs semantic equivalence and compatibility/ABI evidence unavailable from the bounded syntax foundation. |

Forecast counts for each language: 10 partial candidates (including 2 frozen
read-only pilots) and 12 initially unsupported. Supported remains 0 until final
outcomes earn it.

## Proposed bounded packets

### Packet 1 — separate spine, shared mechanics only (`pilot now`)

Own only language-named profiles/provider helpers, C and C++ fixtures, focused
tests, and a learning fragment. Declare separate suffix/role/standard/build
truth; doctor Clang/clangd and compile-database state; freeze final outcomes for
`find-comment-drift`, `map-subsystem`, and `move-path`; record all 22 rows above.
Do not edit shared routers, matrices, catalogs, or common profiles in the lane.

### Packet 2 — lexical/syntax cohort (`pilot now`)

Implement only `find-comment-drift` as the frozen final outcome, backed by raw
tokens/source spans and source-role exclusions. Exercise valid, clean,
malformed, generated/vendor, ambiguous-header, tool-missing/old, and terminal
artifact transitions for both fixtures. If successful, an expansion packet may
evaluate the other lexical/syntax candidates; it must not batch or normalize C
and C++ semantic schemas.

### Packet 3 — semantic cohort (`conditional pilot`)

Implement only `map-subsystem` against the two committed fixture databases.
Prove that the effective command is C for the C fixture and C++ for the C++
fixture; capture declarations/references/project edges through a version-gated
Clang/clangd boundary; and reach the final map artifact. Missing, invalid,
incomplete, or fallback databases must be explicit `partial`/`unsupported`/
`failed` results. Stop if extracting stable facts requires private compiler APIs
or a network-installed toolchain.

### Packet 4 — mutation cohort (`defer`)

Only after Packet 3 passes, run `move-path` serially on disposable copies of
each fixture. Bound it to one source/header move and explicit include/Makefile
updates; preserve proposal-to-source lineage; reject vendor/generated/symlink
escapes and unsupported build systems; run the native build/tests; and prove
rollback plus same-destination terminal state. A passing C move does not earn a
C++ disposition, or vice versa.

## Stop/expand gate

Expand beyond the three frozen contracts only if both separate profiles remain
honest, offline execution needs no undeclared closure, the semantic provider
rejects fallback compile commands, and each supported tier reaches its final
artifact with native verification. Otherwise stop after lexical support,
publish semantics/mutations as partial or unsupported, and retain this evidence
as the learning packet. Missing CMake and clang-tidy are not by themselves stop
conditions; absence of a trustworthy compile database and stable semantic fact
boundary is.
