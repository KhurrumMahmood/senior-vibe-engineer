# Swift P7 preflight

Status: read-only evidence; no Swift product support implemented

Evidence base: repository `865d8507dc09e1f1ddc8629e98060728281e97ad`, macOS
26.5.2 (`25F84`), arm64, active developer directory
`/Library/Developer/CommandLineTools`. Probes used the repository runtime
`<repo>/.venv/bin/python`
where Python was required. No dependency was installed and no network-backed
tool acquisition was attempted. The disposable feasibility package was outside
the repository at `/private/tmp/es-swift-preflight.2UhxYv`.

## Recommendation

Rank Swift first among the currently queued P7 languages, but **defer product
implementation until P5/P6 close and P7 is authorized**. At that point, start a
bounded **SwiftPM-only pilot**, not broad Swift/Xcode support. This machine has
a recent compiler, SwiftPM, SourceKit-LSP, compiler index output, symbol-graph
tools, and `swift-format`; a dependency-free package builds under restrictive
resolution flags. The spine must stop rather than weaken claims if it cannot
establish an offline-owned SwiftSyntax path or a valid native test boundary.

Two concrete host gaps prevent an unconditional “pilot now”:

- `swift -e 'import SwiftSyntax; ...'` fails with `no such module
  'SwiftSyntax'`; syntax extraction cannot assume SwiftSyntax is bundled.
- Both the generated `import Testing` test and an XCTest replacement fail with
  `no such module` under this Command Line Tools-only installation. Full Xcode
  is not active, and `xcodebuild` refuses to run.

Thus the next authorized slice should prove or stop on these boundaries before
opening implementation lanes. Swift remains a better immediate candidate than
languages whose compiler is absent because its lexical/build/semantic
foundations can already be exercised locally.

## Existing product-contract fit and gaps

- The strict profile schema can describe suffixes, exact project markers,
  source roles, native tools, fact tiers, verification argv, outcomes, and
  limits. It permits only `lexical-filesystem`, `syntax`, and
  `semantic-project` tiers; proposal/mutation remains skill-owned as intended.
- The doctor resolves exact project-local executable paths before simple system
  command names, runs a bounded literal version argv, and reports
  available/too-old/unavailable/limited. It cannot currently model tools found
  only through `xcrun`, and `sourcekit-lsp --version` is not a valid probe.
- Project markers are exact relative files checked with `is_file()`. This fits
  `Package.swift` but cannot generically express arbitrary
  `*.xcodeproj`/`*.xcworkspace` directories. Initial scope must therefore be
  SwiftPM; Xcode projects need a later supplementary profile/contract.
- There is no `swift.json`. Running
  `.venv/bin/python -I -S scripts/language_doctor.py --project-root . --language swift`
  exits 2 with `error: unknown language profile: swift`.
- `scripts/source_inventory.py` has no `.swift` profile and does not list
  `.swift` in its explicit unsupported-suffix table. Swift files are currently
  invisible rather than honestly unsupported. A future root-owned spine must
  add `.swift`, classify `Package.swift` as configuration, recognize test
  naming/directories, and freeze generated/build/vendor/symlink boundaries.
- Swift interfaces (`.swiftinterface`), macros/plugins, generated sources,
  resources, mixed Swift/Objective-C/C targets, and package workspaces need
  explicit decisions; none should be implied by basic `.swift` inventory.

## Exact local toolchain evidence

| Command | Result |
|---|---|
| `uname -m`; `sw_vers` | `arm64`; macOS `26.5.2`, build `25F84` |
| `xcode-select -p` | `/Library/Developer/CommandLineTools` |
| `command -v swift swiftc sourcekit-lsp xcodebuild` | `/usr/bin/swift`, `/usr/bin/swiftc`, `/usr/bin/sourcekit-lsp`, `/usr/bin/xcodebuild` |
| `swift --version`; `swiftc --version` | Apple Swift `6.3.3` (`swiftlang-6.3.3.1.3`, clang `2100.1.1.101`), target `arm64-apple-macosx26.0` |
| `swift package --version` | Swift Package Manager `6.3.3` |
| `sourcekit-lsp --version` | Fails: `Unknown option '--version'`; help identifies a Swift/C-family LSP with SwiftPM, compilation-database, and build-server workspace modes |
| `xcrun --find swift-format` / `xcrun swift-format --version` | `/Library/Developer/CommandLineTools/usr/bin/swift-format`; version `6.3.0` |
| `xcrun --find swift-symbolgraph-extract` | `/Library/Developer/CommandLineTools/usr/bin/swift-symbolgraph-extract` |
| `xcrun --find swift-api-digester` | `/Library/Developer/CommandLineTools/usr/bin/swift-api-digester` |
| `xcrun --find swiftlint sourcekitten indexstore-db` | All unavailable |
| `xcrun --show-sdk-path`; `xcrun --show-sdk-version` | `/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk`; `26.5` |
| `xcodebuild -version` | Fails because active developer directory is Command Line Tools, not Xcode |
| `swift -e 'import Foundation; ...'` | Passes |
| `swift -e 'import SwiftSyntax; ...'` | Fails: `no such module 'SwiftSyntax'` |
| `swiftc -print-target-info` | Confirms compiler `6.3.3`, arm64 macOS target, and CLT runtime/resource paths |

Established native surfaces already present are: compiler type checking/build,
SwiftPM package graph and manifest JSON, SourceKit-LSP/index-store generation,
symbol graphs/API digester, and `swift-format`. Host-owned SwiftLint, Periphery,
SourceKitten, or another analyzer may supplement idiom/dead-code checks, but
they are absent and must never be silently installed. Durable guidance should
point to Swift language/API design guidance, SwiftPM target/package structure,
compiler diagnostics, `swift-format`, and host-native build/test commands;
framework lint rules should remain supplementary.

## Offline and representative-host feasibility

`swift package init --type library --name SwiftPreflight` created a normal
Swift 6.3 SwiftPM library. The following restrictive command succeeded without
dependencies:

```text
swift build --cache-path .preflight/cache --config-path .preflight/config \
  --security-path .preflight/security --scratch-path .preflight/build \
  --disable-dependency-cache --manifest-cache local --disable-netrc \
  --disable-keychain --disable-prefetching --disable-automatic-resolution \
  --enable-index-store
```

Result: exit 0, `Build complete! (27.95s)`, with a 1.3 MB index store. The same
global isolation/resolution flags also let `swift package dump-package` and
`show-dependencies --format json` exit 0; the graph contained only the root and
no dependencies. SwiftPM exposes no single `--offline` flag; an external
dependency fixture must separately prove that a complete `Package.resolved`
plus owned cache works with automatic resolution/prefetching disabled. The
dependency-free run does not prove cached third-party packages.

`swift test` with the same flags failed first for generated `import Testing`
and again after substituting `import XCTest`; both modules were missing. By
contrast, `swiftc -typecheck` and `swiftc -dump-ast` succeeded for the library
source, and `xcrun swift-format lint --strict --recursive Sources` exited 0.

`sourcekit-lsp debug index --project .` indexed the library and exited 0, but
its log also showed the test target failing on missing XCTest. Therefore its
process exit status alone is not a trustworthy complete-project result; a
provider must inspect target-level failures and source manifests. Likewise,
`swift package dump-symbol-graph --minimum-access-level internal --pretty-print`
exited 0 and wrote `SwiftPreflight.symbols.json` while reporting failure to
load `SwiftPreflightPackageTests`. Final-outcome checks must reject such mixed
success when the selected project scope includes the failed target.

## Framework boundary

The representative fixture should be a dependency-free or fully cached
multi-target SwiftPM package with `Package.swift`, first-party sources, tests,
generated/build/vendor/symlink sentinels, a malformed source, and at least one
cross-target symbol/call. Initial claims exclude Xcode-only projects, iOS/macOS
app lifecycle, SwiftUI/UIKit/AppKit semantics, Objective-C bridging, build
settings/schemes, asset catalogs/resources, plugins/macros/code generation,
and arbitrary remote dependencies. Each can enter only through an explicit
supplementary profile after the SwiftPM language contract is honest.

## Three pilot cohorts

1. **Lexical/filesystem — `find-comment-drift`.** Retains the PHP/C# comparison
   cohort. Freeze comments, strings/raw strings, nested block comments,
   generated/test/build exclusions, malformed input, and final report/lifecycle
   cases. Preferred producer is an offline-owned SwiftSyntax/SourceKit syntax
   path; stop if only an unvalidated regex scanner is available.
2. **Semantic/project — `map-subsystem`.** Use SwiftPM manifest/target facts plus
   compiler/SourceKit index facts for declarations, imports, references, and
   target edges. Mixed target failures must yield partial/failed, not a clean
   map. Dynamic dispatch, reflection, conditional compilation, macros, and
   framework DI remain explicit limits.
3. **Mutation — `move-path`.** Limit the pilot to one SwiftPM source-file or
   target-directory move with exact source fingerprint, preview/diff, rollback,
   package-target membership checks, and native `swift build` plus runnable
   smoke. Do not claim Xcode project-file/scheme/resource rewriting. Require a
   working native test boundary before expanding mutation support.

## Initial 22-skill disposition forecast

**Current publishable disposition: all 22 are Swift-unsupported.** There is no
profile, inventory visibility, copied provider closure, or final-outcome
fixture, so local tool availability earns no support claim. None is inherently
not-applicable. The following forecast is only for packet ordering:

- **Likely early lexical/filesystem or syntax candidates (9):**
  `adapt-project`, `audit-decisions`, `find-comment-drift`,
  `find-complexity-hotspots`, `find-concept-divergence`, `find-duplication`,
  `find-folder-topology-drift`, `find-omnibus`, `find-standard-gaps`. These need
  final artifacts and role/tool-failure cases; idiom claims should orchestrate
  compiler diagnostics/`swift-format` and optional host-owned analyzers.
- **Likely semantic-project candidates, initially partial (8):** `explain-code`,
  `find-dormant`, `find-implicit-state`, `find-incomplete-sweep`,
  `find-semantic-duplication`, `map-subsystem`, `propose-boundary`,
  `rename-concept`. SourceKit/index and SwiftPM can provide useful facts, but
  cross-module completeness depends on a successful recent build/index;
  reflection, dynamic dispatch, macros, conditional compilation, and mixed
  Xcode graphs prevent blanket completeness.
- **Producer-dependent proposal/guard candidates (4):** `extract-enum`,
  `prevent-regression`, `propose-folder-reorganization`, `unify-shadows`.
  Leave unsupported until an accepted, fingerprinted Swift producer reaches
  each proposal/guard boundary and stale evidence is rejected.
- **Mutation last (1):** `move-path`. Keep unsupported beyond the narrow pilot
  until rollback and native verification cover package membership and all
  affected references; Xcode/resource/project mutations remain out of scope.

## Proposed bounded worker packets

- **Spine (root/one exclusive owner):** SwiftPM-only profile and doctor probes;
  representative host; source roles; exact tool/cache/version evidence; frozen
  three contracts; current 22-row unsupported map. Stop on missing offline
  syntax producer or inability to establish build plus native test/smoke.
- **Lexical worker:** own only Swift-named comment provider/helper, fixture,
  focused tests, and learning fragment. Prove positive/clean/malformed/role/
  tool/lifecycle/copied-closure outcomes. No shared profile/router/matrix edits.
- **Semantic worker:** own only Swift-named SwiftPM/SourceKit provider, fixture,
  focused tests, and learning fragment. Prove target graph, resolved facts,
  mixed-target failure, stale index, and final map. No universal fact schema.
- **Mutation worker:** own only Swift `move-path` helper, disposable fixture,
  focused tests, and learning fragment. Serialize mutation; prove preview,
  exact diff, rollback, source preservation, build, and smoke/test. No Xcode
  project mutation.

Root should integrate each lane serially, publish no claim before exact-library
final outcomes pass, then record expand/stop. A stop remains a valid result and
must retain all 22 honest dispositions and this toolchain learning.
