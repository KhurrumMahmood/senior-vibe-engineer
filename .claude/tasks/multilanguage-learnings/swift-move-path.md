# SwiftPM `move-path` cohort learning

## Outcome

The bounded Swift mutation cohort is complete for exactly one dependency-free
SwiftPM target-directory move: `Sources/BillingCore/` to
`Sources/InvoicingCore/`. The adapter deliberately retains the module and
product identity `BillingCore`; it adds the single reviewed manifest edit
`.target(name: "BillingCore", path: "Sources/InvoicingCore")`. Consequently,
the executable's `import BillingCore` and the excluded test import remain
correct and require no speculative rewrite.

Dry-run emits the exact manifest edit, file rename, whole-host source manifest,
and before/expected fingerprints without changing source. Authorized apply
runs compiler preflight, performs the move, evaluates the resulting manifest,
uses restrictive dependency-resolution flags for `swift build --product
swift-pilot-smoke`, executes that product, and requires the exact output
`invoice:INV-42:fixed-2026`. Expected and actual whole-host fingerprints must
then match. Native failure or an injected mutation outside the reviewed diff
restores the complete pre-apply snapshot.

This is one earned SwiftPM pilot outcome, not broad Swift or `move-path`
support. The root integration lane still owns capability publication.

## Toolchain and acquisition

- Python: `<external-product-worktree>/.venv/bin/python` 3.11.10, supplied as
  an explicit absolute path by the worker packet and used for every Python check
- Swift and SwiftPM: `/usr/bin/swift`, Apple Swift 6.3.3
- Swift compiler: `/usr/bin/swiftc`, Apple Swift 6.3.3
- Active scope: Command Line Tools, dependency-free SwiftPM
- Dependency acquisition and network access: none

Every `dump-package` and build invocation uses isolated cache, configuration,
security, and scratch directories plus `--disable-dependency-cache`, local
manifest caching, disabled netrc/keychain/prefetching/automatic resolution,
and (for build) an index store. Build output never enters the host snapshot.

The frozen `tests/fixtures/swift-pilot` source fixture remains unchanged at 9
regular files, 1,787 bytes, manifest SHA-256
`099f8b10d41d17a245846ef70f7d4a3deba6c210da65035dd25b451646763147`.
All mutations in tests occur only in temporary copies.

## Contract and terminal states

- `complete`: one `Sources/<Target>/` directory moves to another direct
  `Sources/` child; SwiftPM reports one regular target with the retained
  identity; the manifest has one statically reviewable target declaration;
  typecheck, restrictive build, executable smoke, and exact fingerprint pass.
- `partial`: a source/comment/string contains the old filesystem identity and
  its reflective meaning cannot be proved.
- `unsupported`: the move shape, dynamic manifest target declaration,
  dependency graph/resolution, Xcode project/workspace, resource/build-setting,
  macro/plugin/system/binary target, framework/external import, mixed-language
  target, generated input, excluded path, or symlink boundary is outside the
  cohort.
- `failed`: a valid-shape manifest/source is malformed, a native postcondition
  fails, or the actual mutation differs from the reviewed expected manifest.

Generated, test, vendor, and build files are excluded from edits and proven
byte-for-byte stable by the whole-host fingerprint. The same report destination
was exercised through complete -> failed -> complete. Unsupported shapes stop
before secondary native checks so they are not mislabeled as concrete compiler
failures.

## Reused versus Swift-local mechanics

Reused from the existing mover are plan loading, explicit `--dry-run` /
`--apply` / `--check` authority, a stable JSON/Markdown report destination,
and minimal dispatch selection. Swift-specific logic remains in
`swiftpm_move.py`: SwiftPM graph validation, the one safe static manifest edit,
source-role/reflection refusals, restrictive native commands, executable-smoke
proof, source manifests, exact diff, and rollback.

No shared mutation executor or cross-language rewrite schema was introduced.
The source fingerprint policy resembles PHP's transaction, but the Swift
adapter keeps its policy local because its snapshot exclusions, build-state
isolation, and native outcome differ.

## Size, closure, and timing

Counted adapter-plus-test paths are:

- `.claude/skills/move-path/scripts/move_path.py`
- `.claude/skills/move-path/scripts/swiftpm_move.py`
- `tests/test_swift_move_path.py`

They contain 3,586 physical / 3,260 nonblank lines at closeout. This cohort
adds 784 physical lines and removes 4 (net +780): 22 added / 4 removed in the
existing dispatch, 441 in the Swift helper, and 321 in the focused test.

The clean copied `move-path` closure is 10 files / 206,776 bytes with manifest
SHA-256 `67095b4264f784017464ff7ef2a79ff6d004652614b0cb5b4d453d7590f1b4fa`,
using sorted `relative-path + NUL + file-SHA-256 + LF` rows. That is 11.3%
larger than the PHP closeout closure of 185,800 bytes, above the 10% promotion
threshold. The result reinforces keeping Swift facts and transaction policy
family-local.

The final focused suite ran 13 tests in 119.86 seconds (120.10 seconds wall)
and includes multiple real restrictive builds plus copied-closure apply. The
initial broad family run was stopped on coordinator request to avoid concurrent
native-tool contention after 29 passed / 1 skipped; root owns the serial
post-integration family replay.

## Limits and next-language guidance

This cohort does not rename modules/products, move individual files, rewrite
imports, evaluate arbitrary/dynamic `Package.swift` edit points, resolve
dependencies, build Xcode projects/schemes, move resources, support Apple
framework targets, macros/plugins, C/Objective-C bridging, mixed-language
targets, or rewrite reflection/string identities. Those cases remain partial
or unsupported.

The active Command Line Tools installation still lacks usable XCTest/Testing
modules. The built executable is a strong final smoke boundary for this frozen
fixture, but it is not a Swift test-framework claim. Do not expand mutation
support until a representative host supplies a working native test boundary.

For the next language, reuse the outer preview/authority/report vocabulary,
not SwiftPM's manifest model. Keep edit-span proof, excluded-role semantics,
native commands, and reflective-identity refusals local until two consumers
demonstrate identical policy and the measured closure/LOC gates improve.
