# Dart D4 semantic-topology family learning and economics packet

Status: isolated implementation candidate on base `737167d`; no router,
coverage, catalogue, or publication claim is made here.

## Independently useful outcomes

One Dart-owned standard-library JSON-RPC provider now supports three separate
read-only user contracts:

- `find-dormant` emits one unreferenced private top-level function as
  `review_required`, writes `report.md`, `findings.json`, `facts.json`, and
  `scan.json`, and fixes `certain_delete` at zero. Used functions, callbacks,
  tear-offs, public declarations, tests, generated source, vendor source, and
  unresolved boundary files do not become deletion leads.
- `map-subsystem` writes `.claude/docs/subsystems/<name>.md` and
  `reports/map/<name>/dart-map.json` with selected files, direct public
  surface, and LSP-resolved direct/package/export inbound and outbound edges.
  Its positive conditional-export fixture is a useful `partial`; the bounded
  clean package map is `complete`.
- `rename-concept` writes `reports/rename-concept/assessment.json`. Mixed
  public `OldLedger`/`NewLedger` authority produces
  `HALF-APPLIED / INCOMPLETE`, while the clean new-only authority is complete.
  Same-spelled locals remain unrelated evidence and old prose/string evidence
  remains visible under the strict-text deferred surface. The adapter is
  assess-only and never applies returned rename edits.

The provider records Dart version, initialize capabilities, clean/error
diagnostics, workspace-symbol readiness, document symbols, definitions,
references, read-only `prepareRename`/`rename` edit counts, module edges,
unresolved requests, clean shutdown, and external-cache cleanup. Its fact pack
and query plan are canonically hashed. Every regular Dart source and the
selected pre-existing package configuration are individually hashed and
revalidated before reuse.

## Configuration and completeness boundary

`dart language-server --protocol=lsp` runs with an external temporary
`--cache`. A pre-existing `.dart_tool/package_config.json`, or an explicitly
selected regular external package config, is passed via `--packages` and
hashed. The provider never invokes Pub, generates configuration, installs a
dependency, or repairs the audited host. Missing, stale, malformed, or
symlink-ambiguous package configuration cannot be clean when package imports
exist.

macOS paths and file URIs are realpath-canonicalized. SDK/dependency locations
never become first-party locations. Directory and file symlinks are inventoried
as excluded without traversal. Conditional imports/exports, parts,
augmentations, generated code, unresolved URIs/diagnostics, missing
capabilities, incomplete workspace readiness, and failed requests lower the
result to partial or failed. Valid → failed → valid reruns replace terminal
artifacts at the same destination, so stale clean output does not survive.

No result claims deletion safety, runtime reachability, reflection/registry
coverage, isolate behavior, native/JS interop, generated callers, external
compatibility, codemod safety, or Flutter behavior. Flutter remains an
unimplemented framework profile.

## Copied closure and fixtures

The isolated copied-layout test installs exactly the four Dart scripts under
sibling `map-subsystem`, `find-dormant`, and `rename-concept` skill paths. It
runs the provider once with the union of bounded consumer queries, then runs
all three consumers against that verified pack without repository imports.

Measured physical/nonblank LOC and bytes:

| Surface | Physical LOC | Nonblank LOC | Bytes |
|---|---:|---:|---:|
| Shared provider | 1,004 | 942 | 41,459 |
| Three adapters | 810 | 764 | 31,579 |
| Focused family test | 548 | 509 | 19,219 |
| Four-script copied closure | 1,814 | 1,706 | 73,038 |

The four-script closure manifest uses
`sha256(path + NUL + file_sha256 + LF)` in listed-path order and is
`5b1e4ee01fa891827698578a30740af9f931c7022e791682b4c9d7c09c82c9b8`.

The positive fixture has 14 files / 1,898 bytes and manifest
`cfd430456ae59f17d747f4f624d4ed0a2da18da780c2a61d0a8e32ad9395bc04`.
The clean fixture has 8 files / 879 bytes and manifest
`4e58ed9e12fff5c6fae29967c7c0d8e5e39c0d35bca128d6bfe480c4f7f607eb`.
Both contain a tracked, relative, pre-existing package configuration. The
tools never create it.

## ML-025 economics

Let `H` be the 1,004 physical provider LOC and `C` the 1,358 maintained adapter
plus focused-test LOC. Three duplicated providers would maintain
`C + 3H = 4,370` LOC; the accepted family-local layout maintains
`C + H = 2,362` LOC. Sharing saves 2,008 physical LOC, or **45.95%**, clearing
the 25% ML-025 threshold. The copied closure is also one provider rather than
three, and one union query run replaces three server startups, so closure size
and latency do not regress. Consumer schemas, judgments, and terminal
artifacts remain independent. This evidence supports Dart-local sharing only;
it does not justify a cross-language LSP abstraction.

## Focused verification

```text
/Users/<user>/Projects/engineering-skills-product/.venv/bin/python \
  -m pytest -q tests/test_dart_d4_semantic_family.py
# 9 passed

/opt/homebrew/bin/dart analyze --fatal-infos --fatal-warnings .
/opt/homebrew/bin/dart format --output=none --set-exit-if-changed lib bin test
/opt/homebrew/bin/dart test/native_test.dart
/opt/homebrew/bin/dart bin/smoke.dart
# both fixtures: analyze/format/direct test pass; smoke prints exactly 42
```

The focused suite also proves clean and positive artifacts, must-not-fire
roles, absent/stale/symlink package configuration, file/directory symlink
exclusion, missing/old/broken Dart/LSP, malformed protocol handling,
same-destination recovery, stale source/config rejection, exact artifact/hash
agreement, temporary cache cleanup, copied execution, source preservation, and
the economics assertion.
