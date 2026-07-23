# Dart D1 project/lexical family handoff

Base revision: `737167dc0a142b399c897599e478d7114e024794`

## Outcome and disposition recommendations

Three independent copied consumers reach their existing final artifact
boundaries over a dependency-free plain-Dart 3.12 package. These are bounded
language outcomes, not a Flutter, semantic, package-graph, or architecture
claim.

| Skill | Proved value | Final artifacts | Recommended disposition |
|---|---|---|---|
| `adapt-project` | Counts nine authored Dart library files, preserves all observed roles, reports `pubspec.yaml`, and emits the exact analyze/format/direct-test/smoke commands it executes without host writes or framework inference. | `adapter.yml`, `adapter.json`, `report.md`, `evidence.json` | `dart-supported` for objective dependency-free plain-Dart project/layout facts |
| `find-concept-divergence` | Reports the one glossary avoid-term `cancelled_order` in authored source with exact byte/line span and spelling/source hashes; the preferred-only host is clean. | `findings.jsonl`, `report.md`, `findings.json`, `scan.json` | `dart-supported` for strict glossary-backed text evidence |
| `find-folder-topology-drift` | Reports one policy-backed three-file `billing_*.dart` direct-sibling cluster; two siblings and an explicitly allowed folder are clean. | `detections.jsonl`, `report.md`, `findings.json`, `scan.json` | `dart-supported` for explicit-root direct-sibling filename topology evidence |

## Shared project snapshot and economics

`.claude/skills/_dart/dart_project_snapshot.py` owns only the identical D1
facts and mechanics used by all three consumers: Dart 3.12 SDK preflight,
pubspec/configuration fingerprints, full `.dart` role inventory, selected
library roots, source/config manifests, host-safe native gates, source and
host-state preservation, atomic writes, stale-artifact clearing, report-path
containment, status, and terminal return codes. Consumers retain adaptation,
glossary, and topology meaning plus their final schemas.

Physical maintained adapter-plus-test LOC:

- shared snapshot `H`: 563 lines;
- consumer adapters plus focused test `C`: 1,041 lines (576 adapter, 465 test);
- duplicated snapshot design `C + 3H`: 2,730 lines;
- shared design `C + H`: 1,604 lines;
- deleted maintenance `2H`: 1,126 lines;
- reduction: **41.25%**.

This clears ML-025's 25% LOC gate. Every copied consumer contains one helper
plus one adapter, which is the same implementation content an inline consumer
would require; sharing adds no cache, daemon, dependency, network call, or
second native pass. Each invocation collects one snapshot and executes one
native matrix, so closure size and process latency do not grow by 10% relative
to the equivalent inline implementation. The seam remains Dart-only; no
cross-language project provider or universal fact/report schema is justified.

The deletion test is substantive: removing the helper makes all three
consumers recover tool/version policy, project/config hashes, eleven role
boundaries, native command isolation, preservation checks, artifact lifecycle,
and terminal status. Durable tests exercise only copied public commands.

## Fixture and exact provenance

The bounded fixture has 49 regular files, 3,159 bytes, manifest
`8dbf9fc7ea46eb04c043cce1cade2c75e3a8d60fed38edef771546c934e1a12d`
using sorted `path + NUL + file_sha256 + LF` rows. The positive copied run
records:

- source manifest: 43 Dart files,
  `e7cc93946769cd9ee08ccf0bd4e815336ac641a44f533ef3fdf4ea3808570cfb`;
- configuration manifest:
  `a1ab7fdc0a4785e7c63754e914a44b4004e58647a71c175bb78ccbc127a352b4`;
- content-addressed snapshot:
  `d6bd770d98adbcd20185da2e83bda2fb927900c7c4d5513ce43dd49c126e395a`;
- `pubspec.yaml`:
  `3bffaf2642698d7dc38c37ea3c0f27d5ea2812f49e6ff2325ac2527b4499a2b3`;
- glossary:
  `417547d17032aac19fe42dfa47cc6415f36c4e52f248748893e7484fd3528cff`.

The source manifest covers selected and excluded Dart files. Configuration
fingerprints cover every existing `pubspec.yaml`, `pubspec.lock`,
`analysis_options.yaml`, `build.yaml`, and pre-existing package configuration.
The fixture begins without `.dart_tool/` or `pubspec.lock`; both remain absent.
Pre-existing `reports/decoys/*.dart` bytes receive a separate before/after
assertion so authorized final artifacts cannot mask mutation of report-role
source.

Copied closure manifests are:

| Consumer | Files | Bytes | Manifest |
|---|---:|---:|---|
| shared snapshot | 1 | 20,493 | `bc1f2048397080ed90ed37ea47d50dd01e8a9af208cb373f13bc6aa239df80ca` |
| `adapt-project` | 2 | 24,980 | `7bf0536807dd5dcd3de3af915d26be94c87b3b35081f007da80c35cc6a721b84` |
| `find-concept-divergence` | 2 | 31,848 | `c05925469cf7bd0ff47935056caafbd41a6bfc9f3809def7cb2bfc8c27417be4` |
| `find-folder-topology-drift` | 2 | 25,947 | `372440f3f5cd896a17d59b08be4b45ca48c9e425dc1e9e9ee53534315c9b92ac` |

## Contract coverage and limitations

The focused module proves positive, clean, must-not-fire, malformed UTF-8 and
malformed syntax, missing/old/broken Dart, valid -> failed -> valid recovery at
the same destination, symlinked report refusal, copied isolated-Python closure,
exact spans/hashes, source preservation, and zero host writes. Findings exclude
test/integration-test, executable `bin`, tooling `tool`, example, generated
tree/header/common suffix (`*.g.dart`, `*.freezed.dart`, `*.mocks.dart`), part,
vendor, build, report, symlink, barrel, below-threshold, allowed-folder, and
nested-cousin shapes.

The generated suffixes remain an explicit Dart-only helper boundary. This
does not redesign the generic language-profile schema.

- Adaptation describes observed filesystem layout only. It does not endorse
  architecture, resolve a package graph, validate pubspec syntax, or infer a
  framework from Flutter-shaped prose/dependency names.
- Concept divergence is strict glossary text evidence. It does not establish
  symbol identity, conceptual equivalence, or rename completeness.
- Folder topology is advisory filename evidence. It does not establish Dart
  library ownership, import impact, safe moves, package/workspace layout, or
  Flutter conventions.
- No analyzer package or LSP is imported or invoked. Parts, generated APIs,
  conditional imports, augmentations, reflection, runtime dispatch, pub
  workspaces, and Flutter stay unresolved.

## Verification evidence

No network, install, Pub resolution, dependency update, or audited-host
mutation occurred. The exact frozen runtimes were Dart 3.12.2 at
`/opt/homebrew/bin/dart` and Python 3.11.10 at the required product venv path.

- Focused copied D1 module: 24 passed in 19.71s.
- Preserved TypeScript, Go, Java, and Rust tests for the three affected skill
  families: 79 passed in 101.20s.
- Independent native fixture: `dart analyze --fatal-infos --fatal-warnings .`,
  check-only format over existing authored roots, direct test, and exact smoke
  all passed; 31 files formatted with zero changes; exact smoke was
  `dart-d1-ok`; full regular-file before/after manifest matched and no
  `.dart_tool/` or lock appeared.
- Targeted Ruff, Python byte compilation, `git diff --check`, and skill metadata
  lint passed.
- Ecosystem skill smokes reported 10/11 explicit and 46/46 import-floor checks;
  the unrelated pre-existing `rename-concept` smoke failed its injected band-1
  oracle. No selected D1 skill smoke or import-floor check failed.

## Root integration instructions

1. Copy `_dart/dart_project_snapshot.py` beside any selected Dart D1 consumer;
   reject a consumer-only closure.
2. Add each copied Dart command, exact artifacts/statuses, native matrix,
   role exclusions, and bounded limitation to its existing `SKILL.md` without
   changing preserved language commands.
3. Change exactly the three accepted coverage rows from
   `dart-pending-implementation` to the recommended disposition, citing the
   integrated revision and this packet; then regenerate matrix/projections.
4. Replay each copied command from outside the repository through
   valid -> failed -> valid and rerun the 79 preserved family tests before
   enabling routing/catalog claims.
5. Keep consumer interpretations local. Revisit a broader project provider
   only after another language proves an identical public contract and its own
   economics; do not merge D2 syntax or D4 semantic facts into this snapshot.
