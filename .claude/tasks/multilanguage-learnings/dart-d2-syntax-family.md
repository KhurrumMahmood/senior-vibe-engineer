# Dart D2 syntax-family learning and economics

## Outcome and dispositions

Three read-only skills now have independent useful Dart 3.12 outcomes over one
locked public-`package:analyzer` syntax producer. These are integration
candidates; root still owns coverage, router, catalog, matrix, and `SKILL.md`
publication.

| Skill | Candidate disposition | Exact bounded outcome |
|---|---|---|
| `audit-decisions` | `dart-supported` within D2 | Existing `drift.md`, `raw-drift.json`, `registry-audit.json`, and `link-check.txt` retain real Dart line/block/doc `decision:0001` references and surface orphan `decision:9999`. The existing link artifact schema is preserved; the contract-map table's `link-audit.json` spelling was not introduced as a second schema. |
| `find-comment-drift` | `dart-supported`, advisory | `detections.jsonl`, `report.md`, `findings.json`, and `scan.json` report only the adjacent `///` 10-percent claim whose top-level function directly returns `125`; matching, computed, closure, detached, mixin, extension, string, and excluded-role decoys stay clean. |
| `find-standard-gaps` | `dart-supported` for one condition | `coverage.md`, `coverage.json`, and `scan.json` report exactly two direct spelled `parseInvoice` sites, one outside `try`, one gap, and 50% coverage. Receiver calls, declarations, tear-offs, strings, and excluded roles do not become sites. |

Each adapter retains its own final artifact, verdict, and exit semantics. The
shared producer emits facts and provenance only; it does not publish a skill
outcome.

## Interface depth check

- **Deletion test:** removing `_dart` makes all three consumers re-own SDK
  probing, offline locked package setup, roles, analyzer invocation, comment
  token semantics, parse failure, direct-body `try`, manifests, native proof,
  and zero-write checks.
- **Caller knowledge removed:** adapters know only bounded fact fields and
  their own report policy; they do not know Pub cache acquisition, analyzer
  APIs, exclusion markers, host native commands, or source-preservation logic.
- **Test surface:** the producer CLI is tested directly and every consumer is
  tested through its copied final-artifact command, including deletion/cold
  dependency and lifecycle failures.
- **Adapter reality:** three production consumers use the same snapshot; D3 is
  a named later consumer, not justification needed for the current seam.
- **Decision:** choose one Dart-local provider over three local copies (43.06%
  measured savings). Reject both family-local duplication and a universal
  cross-language AST/provider because the former repeats policy and the latter
  would erase incompatible semantics.

## Producer, package, and audited-host boundary

The copied closure contains sibling `.agents/skills/_dart` with:

- `scripts/dart_syntax_facts.py`, the stdlib orchestration, whole-host role
  inventory, source manifest, native D0 gate, terminal-status, and disposable
  tool setup;
- `tool/pubspec.yaml` and `tool/pubspec.lock`, pinning Dart
  `>=3.12.0 <3.13.0` and `analyzer` 14.1.0 exactly; and
- `tool/bin/dart_syntax_facts.dart`, which imports only public
  `package:analyzer/dart/...` libraries and emits parse diagnostics, real
  comment tokens, adjacent top-level doc/fixed-return facts, and direct spelled
  call/`try` facts.

The analyzer package is copied to an external temporary directory and prepared
only with:

```text
dart pub get --offline --enforce-lockfile
```

The audited host never runs `pub get`, `dart run`, or `dart test`. Its exact
native matrix is `dart analyze --fatal-infos --fatal-warnings .`, check-only
format over existing `lib`/`bin`/`tool` roots, direct `dart <test-script>`, and
direct `dart <smoke-entrypoint>` with exact stdout. Before/after manifests prove
no `.dart_tool`, lockfile, cache, source, or other host write. Missing cached
packages or a missing locked companion are visible
`partial/tool_dependency_unavailable`; a broken SDK probe, analyzer payload,
parse, or native gate is `failed`. No fallback lexer or network acquisition is
used.

## Syntax and source policy

The analyzer token stream distinguishes line, block, and doc comments from
ordinary, raw, triple-quoted, and interpolated string text. A real comment
inside an interpolation expression remains a comment. Parse diagnostics in any
selected authored source block a clean result.

The inventory is project-root-relative and cannot be bypassed by a narrowed
target. Test and integration-test trees, examples/benchmarks, generated trees,
generated headers and common generated suffixes, vendor/Pub-cache trees,
build/output/report trees, and symlinks are inventoried but excluded. `lib`,
`bin`, and ordinary `tool` Dart remain first-party; the fixture's direct native
test is excluded by its `_test.dart` name. The fixture proves generated, test,
example, vendor, build, report, and external-symlink decoys do not leak into any
final outcome.

`try` satisfaction applies only while walking the direct executable body. A
nested closure stops at its own `FunctionBody`, so an outer `try` does not
protect a callback call syntactically. Comment drift is narrower still: only an
immediately adjacent line-doc comment on a top-level named function with a
complete fixed numeric return is eligible.

## Lifecycle, closure, and frozen hashes

All three adapters clear their prior artifact set before analysis, atomically
write complete/partial/failed replacements, and pass valid -> malformed/failed
-> valid at one destination. Old references, findings, and scanned coverage
cells do not survive a failed rerun. Every copied adapter plus sibling `_dart`
runs from a working directory outside both repository and host.

The frozen owned-runtime manifest uses sorted
`repository-relative-path + NUL + file-SHA-256 + LF` rows over the provider,
locked tool package, and three adapters:

- 7 files, 53,682 bytes,
  `8bb34a1c1c57a08a69ed5cd38fa3dc5f3d78c4f23e9f71507435796bae104944`.
- Fixture: 15 files, 3,968 bytes,
  `f122c7d992591cdc09bdd913e96ffc225b9484e42b942d4d386795b7264d2b14`.

Whole selected-skill plus shared-helper copied closures at this branch are:

| Closure | Files | Bytes | SHA-256 |
|---|---:|---:|---|
| `audit-decisions` + `_dart` | 11 | 119,206 | `86ac558d2846d89f63c798a9ea5fa404aa89d194adc163b10e1c48277ea7bf2f` |
| `find-comment-drift` + `_dart` | 27 | 242,651 | `c685421a68e6b0f4b3c9e26881ec01773bf2d6d99d28319b3f9a5954c5a0948e` |
| `find-standard-gaps` + `_dart` | 16 | 195,526 | `a0e694f06e51b4264159101163b82c398b0d502b8d4723d232f9c61c4cbbfcd7` |

## ML-025 economics

Physical maintained code counts are:

- shared producer/tool/pubspec `H`: 732 physical / 673 nonblank lines,
  24,736 bytes;
- three skill adapters plus the focused final-outcome test `C`: 1,204 physical
  / 1,087 nonblank lines, 43,270 bytes; and
- lockfile: 149 physical lines, retained as acquisition evidence but excluded
  from adapter-plus-test LOC.

Sharing therefore costs `C + H = 1,936` physical lines. Duplicating the same
producer package in all three selected skills would cost
`C + 3H = 3,400` physical lines. The reduction is 43.06%, clearing ML-025's
25% gate. Nonblank savings are 43.34% (3,106 to 1,760). Per-selected-skill
closure bytes and analyzer execution are identical to a local copy of the same
producer, so sharing adds 0% closure size and 0% producer latency versus local
duplication; the installed three-skill union stores the helper once. Consumer
schemas, interpretation, and lifecycle remain skill-local.

## Native acquisition and verification

- Python: the provided product-worktree `.venv/bin/python`, 3.11.10.
- Dart: `/opt/homebrew/bin/dart` 3.12.2 stable, macOS arm64.
- Analyzer: locked public package 14.1.0 from the already populated Pub cache.
- Network used: none; install/update performed: none.

One complete copied provider observation took 6.8922 seconds end to end. The
recorded subprocess breakdown was: locked offline Pub setup 0.1261s, analyzer
fact production 5.7122s, native analyze 0.5973s, check-only format 0.0438s,
direct test 0.1753s, and smoke 0.1625s (6.8172s measured subprocess time).
This is a local single observation, not a performance threshold. Analyzer JIT
startup/fact production is the dominant known per-invocation cost; locked setup
and the full native proof are comparatively small. No persistent state or
compiled artifact was added because that would complicate the copied,
source-preserving closure without a measured safe win. If a root workflow runs
multiple D2/D3 consumers on one unchanged snapshot, the concrete later
candidate is one content-addressed producer invocation shared by that bounded
consumer set, with the existing source/tool manifest as its cache key. That
optimization needs its own stale/failure and copied-closure proof; independent
skill invocations remain uncached and honest today.

Focused verification covers positive, clean, malformed, invalid-standards,
cold-cache, missing companion, broken SDK, source-role, direct-body,
same-destination lifecycle, exact hash, copied closure, native zero-write, and
source-preservation cases. Root should replay the focused suite and the
preserved audit/comment-drift/standard-gaps language-family suites before
publication.

## Explicit limitations

- Syntax only: no callee identity, import/alias/receiver/type resolution,
  exception flow, data flow, runtime behavior, or closed-world claim.
- Comment drift covers one fixed numeric percentage/rate shape on top-level
  named functions; no methods, inheritance, macros/codegen meaning, inherited
  docs, or API-correctness claim.
- Standards cover only direct spelled calls and `enclosed_by: "try"`; this is
  not a general Dart lint replacement.
- Audit recognizes the exact lowercase `decision:NNNN` token in real comments;
  it does not decide whether an ADR applies.
- Pub workspaces, parts/augmentations, conditional configuration, generated
  ownership, dynamic invocation, mirrors, isolates, FFI/JS interop, and package
  semantics are outside D2's claim.
- No Flutter SDK or framework profile was evaluated. Pub dependencies, widget
  names, or project layout do not imply Flutter support.

## Root integration

Root should integrate the D0 spine before this branch, then copy `_dart` beside
each selected skill, document the locked offline setup and Dart adapter command,
and publish only the three bounded dispositions above. It should preserve the
existing four-file audit schema, run the copied commands from outside repository
and host, replay same-destination terminal transitions, run preserved language
families, then update coverage/matrix/router/catalog/projections serially. D3
may consume this accepted producer; it must not create another Dart parser.
