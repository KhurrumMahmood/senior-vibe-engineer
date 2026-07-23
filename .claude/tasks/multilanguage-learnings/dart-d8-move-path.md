# Dart D8 transactional `move-path`

Status: repaired isolated implementation candidate on base `ef9a9fb`; this branch does
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

Unrelated host evidence is preserved rather than confused with move risk. A
generated Dart file, valid part/part-of pair, raw augmentation token, dynamic
loading token, or symlink that has no resolved connection to the requested
move can coexist with a complete preview/apply. Those decoys still
participate in the source hash and exact after-tree proof. The same boundary on
the moved source or its resolved direct consumer/dependency closure remains a
refusal, and an exact old library identity remains blocking wherever found.

Dry-run is source-preserving and emits `evidence.json`. Its hash covers the
normalized plan, complete source tree including regular-file modes, expected
after tree, exact edit spans, public barrels, syntax/tool manifests, semantic
fact-pack/query hashes, package configuration, and source hashes. Apply
requires the human to repeat that evidence SHA explicitly. A stale tree,
changed mode, changed plan, changed evidence, or changed span refuses before
mutation.

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
or conditional imports/exports, parts/part files, augmentations, generated
source, and dynamic/reflective loading evidence on the moved path or resolved
direct impact closure. A moved/required path crossing a symlink, a symlinked
Dart consumer with lexical evidence of the moved identity, an exact old
identity anywhere, malformed source, missing/stale configuration, unsupported
tooling, or an incomplete relevant semantic graph also refuses. The unrelated
augmentation case proves only a raw augmentation-like token false positive,
not an executable augmentation construct. There is no regex/lexer fallback
when move-relevant D2 or D4 evidence is partial.

This is not a package rename, public API/semver migration, dependency install,
Pub workspace operation, arbitrary codemod, generated-code move, Flutter
asset/platform refactor, reflection/isolate proof, or crash-consistent
filesystem journal. Rollback is guaranteed for every observed process,
analysis, native, edit, residue, or exact-tree failure after mutation; power
loss outside the process remains an operating-system concern.

## Red-to-green repair evidence

Against the pre-repair cherry-pick `0dfd6ac` (source commit `45f0c3f`), the
five-case `unrelated_boundary_decoys` regression selection failed 5/5 in 0.52s
without producing evidence. The reports named the old global blockers exactly:
`dart_generated_source`, `dart_part_or_augmentation` for both part and
augmentation cases, `dart_dynamic_loading_boundary`, and
`dart_symlink_boundary`. The augmentation fixture is valid compiling Dart; its
triple-quoted payload deliberately proves the old raw line-anchored scanner's
false-positive behavior.

After the scope repair, the same five cases passed the complete
preview/apply/exact-after-tree journey (5 passed in 115.84s). Six moved-source
boundary cases passed their preserved-refusal assertions, and a valid `part`
relationship on a resolved direct consumer independently proved the impacted
closure still refuses without leaving `evidence.json`.

The adversarial follow-up reproduced two correctness escapes on `4779e2a`: an
analysis-excluded symlinked Dart consumer could retain the old package URI in
its external target, and file-mode changes neither made preview evidence stale
nor failed post-apply `--check`. The regression selection failed all four new
acceptance assertions before the fix. The repaired adapter now reads only the
logical Dart symlink text needed for lexical move-identity detection, never
mutates the external target, hashes regular-file modes, and proves both
pre-apply and post-apply mode drift. A sixth unrelated-boundary cell proves a
valid conditional directive can coexist with the move while an impacted
conditional still refuses. The test subprocess uses `sys.executable` and finds
Dart on `PATH`; only absence of the native Dart SDK skips the module.

## Reuse and economics

The maintained adapter and focused final-outcome test are 2,344 physical lines
(2,130 nonblank) and 86,154 bytes. The exact runtime closure reuses 2,720
physical lines of accepted Dart producers rather than forking their
inventory, locked-analyzer, native-lifecycle, or SDK-LSP implementations into
D8. Against an embedded `C + H` shape, the maintained D8-local surface is
`C = 2,344` rather than `C + H = 5,064` lines, avoiding 2,720 duplicate lines
(53.71%). This is deletion/reuse value, not evidence for a generic transaction
platform; Dart move policy, evidence schema, refusal rules, and rollback remain
in one mutation-local adapter.

The six-file copied runtime is 157,874 bytes / 4,243 physical lines and uses
sorted `repository-relative-path + NUL + file-SHA-256 + LF` rows. Its manifest
at implementation time is
`7c34867d6de20e797596349cfec0967dbb92e31c98b184ac1cac7a038f3a339b`:

- `move-path/scripts/dart_library_move.py`
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

Root alone should (1) merge this branch after D1-D7, (2) add the six-file
external-library dependency closure for Dart `move-path`, (3) change only the
Dart `move-path` capability from pending to supported with this packet and the
committed revision as evidence, (4) regenerate matrix/router projections and
catalogue prose, (5) update the active P7 ledger, and (6) replay the committed
installed journey plus the whole preserved move-path family. Do not advertise
stock-selected install: the Dart mode needs sibling `_dart` and
`map-subsystem` files. Do not broaden the claim beyond the one private library
file/leaf-directory transaction above.
