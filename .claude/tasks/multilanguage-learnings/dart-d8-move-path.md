# Dart D8 transactional `move-path`

Status: isolated implementation candidate on base `19f7bb2`; this branch does
not publish coverage, matrix, router, catalogue, projection, or execution-plan
state.

## Final user outcome

The checked Dart journey moves one private `lib/src` library file or one leaf
directory, rewrites every impacted first-party import/export URI whose exact
public-analyzer span agrees with the SDK LSP-resolved target, and preserves at
least one declared public barrel. The fixture proves a moved referrer's changed
relative import, relative and internal-package importers, two exports, a stable
public package import in the native test, file and directory forms, and a clean
post-apply check.

Dry-run is source-preserving and emits `evidence.json`. Its hash covers the
normalized plan, complete source tree, expected after tree, exact edit spans,
public barrels, syntax/tool manifests, semantic fact-pack/query hashes,
package configuration, and source hashes. Apply requires the human to repeat
that evidence SHA explicitly. A stale tree, changed plan, changed evidence, or
changed span refuses before mutation.

Apply snapshots every regular file, mode, and symlink outside the report and
Git metadata; mutates only the reviewed move/edits; reruns Dart
format/analyze/direct-test/smoke plus semantic resolution; compares the exact
whole-host after tree; audits old identities; and restores the exact snapshot
on any failure. The injected direct-test failure proves byte-for-byte rollback.

## Honest boundary

The adapter requires an explicit `disposable` or `user-approved` host scope, a
pre-existing current package configuration, Dart `>=3.12.0 <3.13.0`, the locked
public analyzer 14.1.0 closure, a direct native test, exact smoke stdout, and a
declared public barrel that exports the moved library.

It stops before writes for multiple moves, public `lib/*.dart` moves,
cross-package/public package-URI changes, unresolved or excluded-role impacts,
conditional imports/exports, parts/part files, augmentations, generated source,
any symlink boundary, dynamic/reflective loading evidence, malformed source,
missing/stale configuration, unsupported tooling, or an incomplete semantic
graph. There is no regex/lexer fallback when D2 or D4 evidence is partial.

This is not a package rename, public API/semver migration, dependency install,
Pub workspace operation, arbitrary codemod, generated-code move, Flutter
asset/platform refactor, reflection/isolate proof, or crash-consistent
filesystem journal. Rollback is guaranteed for every observed process,
analysis, native, edit, residue, or exact-tree failure after mutation; power
loss outside the process remains an operating-system concern.

## Reuse and economics

The new maintained adapter and focused final-outcome test are 1,822 physical
lines (1,644 nonblank) and 68,946 bytes. The exact runtime closure reuses 2,862
physical lines of accepted D1/D2/D4 producers rather than forking their
inventory, locked-analyzer, native-lifecycle, or SDK-LSP implementations into
D8. Against an embedded `C + H` shape, the maintained D8-local surface is
`C = 1,822` rather than `C + H = 4,684` lines, avoiding 2,862 duplicate lines
(61.10%). This is deletion/reuse value, not evidence for a generic transaction
platform; Dart move policy, evidence schema, refusal rules, and rollback remain
in one mutation-local adapter.

The seven-file copied runtime is 151,831 bytes / 4,081 physical lines and uses
sorted `repository-relative-path + NUL + file-SHA-256 + LF` rows. Its manifest
at implementation time is
`74b1ec0903b4ff7d3524850301017e81ab4fe8673d616ec8e4d3f72c61d2d120`:

- `move-path/scripts/dart_library_move.py`
- `_dart/dart_project_snapshot.py`
- `_dart/scripts/dart_syntax_facts.py`
- `_dart/tool/bin/dart_syntax_facts.dart`
- `_dart/tool/pubspec.yaml`
- `_dart/tool/pubspec.lock`
- `map-subsystem/scripts/dart_lsp_facts.py`

The copied test installs only those files outside both repository and audited
host, invokes the adapter from a third directory, and completes the real
preview/apply journey. Pub's offline enforce-lockfile step runs only in a
temporary copy of the locked analyzer tool; Pub never runs in the host.

## Root publication boundary

Root alone should (1) merge this branch after D1-D7, (2) add the seven-file
external-library dependency closure for Dart `move-path`, (3) change only the
Dart `move-path` capability from pending to supported with this packet and the
committed revision as evidence, (4) regenerate matrix/router projections and
catalogue prose, (5) update the active P7 ledger, and (6) replay the committed
installed journey plus the whole preserved move-path family. Do not advertise
stock-selected install: the Dart mode needs sibling `_dart` and
`map-subsystem` files. Do not broaden the claim beyond the one private library
file/leaf-directory transaction above.
