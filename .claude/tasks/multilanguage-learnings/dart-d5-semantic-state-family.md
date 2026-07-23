# Dart D5 semantic-behavior/state family learning and economics packet

Status: isolated implementation candidate on exact base `f246f0b`; no router,
coverage, catalogue, profile, plan, installer, or publication claim is made
here.

## Dispositions and final outcomes

The accepted D4 `dart-lsp-facts-v1` provider was consumed unchanged from
`map-subsystem/scripts/dart_lsp_facts.py`. One content-addressed union pack for
the positive snapshot carries `charge`, `phase`, `state`, and `status`; all D5
artifacts cite the same fact-pack and query-plan hashes.

- `find-implicit-state` is an implemented review outcome. A direct class
  `String state` field is nominated only when at least three literal
  assignment/comparison operations resolve through
  `textDocument/definition` to that exact field declaration. The detector
  writes `candidates.jsonl`, `facts.json`, `scan.json`, `report.md`, and
  `findings.json`. It remains `partial/human_review_required` until a
  SHA-bound fixed review is supplied; accepted review files are preserved
  under `scout/`. The fixture promotes exactly `Job.state` with `done`,
  `queued`, and `running`. Typed state, insufficient evidence, local
  homonyms, dynamic access, serialization/wire carriers, tests, generated
  source, examples, vendor source, and tooling source do not promote.
- `find-incomplete-sweep` is an implemented review outcome. Direct call sites
  must resolve to one top-level Dart function, three of four calls must carry
  the same named argument, and every present site must be newer in Git than
  the one omitted site. It writes the existing `findings.md` and
  `manifest.json` schemas; the existing scout and triage writers now recognize
  Dart as a compiler-backed manifest. The fixture yields one `charge:audit`
  packet, one explicit `forgotten` verdict, and `triaged.md`. Same-spelled
  locals, tear-offs, wrappers, extension/dynamic dispatch, and excluded roles
  do not gate in.
- `find-semantic-duplication` is deliberately stopped, not weakened. Its
  required evidence includes per-function outgoing call hierarchy with source
  and target lineage. The accepted D4 public interface advertises the SDK
  capabilities but its query plan never issues
  `textDocument/prepareCallHierarchy` or `callHierarchy/outgoingCalls`, and it
  exposes no call-hierarchy result collection. Definitions, document symbols,
  raw references, spelling, and lexical bodies are not equivalent evidence.
  The adapter therefore writes `analysis.json`, `findings.json`, `triage.md`,
  `facts.json`, and `scan.json` with
  `partial/accepted_provider_fact_gap`, zero leads, and the exact missing fact.
  It creates no capability matrix because there is no evidence-backed lead.

This stop is local to the consumer. D4 was not modified, no second parser or
LSP client was added, and no cross-language abstraction was created.

## Artifact lifecycle, lineage, and human boundaries

All three adapters validate the provider schema, canonical fact-pack hash,
consumer query coverage, selected source hashes, and package-configuration
hash through the accepted D4 `load_or_collect` interface. Output paths are
confined below each skill's authorized `reports/` root and reject existing
symlink traversal. Directory-shaped outcomes are staged and replaced as a
unit, removing stale scout, matrix, or verdict artifacts on rerun.

The focused test exercises a complete pack, a conditional-directive partial
pack, a missing-Dart failed pack, then the original complete pack at the same
destinations. Old clean artifacts do not survive. It also rejects a stale
source pack and a state review whose candidate hash does not match. Source,
pubspec, tracked package configuration, direct test, and smoke bytes are
unchanged; only authorized report artifacts are written. Provider cache state
remains external and temporary under the accepted D4 lifecycle.

Human judgment stays explicit:

- state candidates do not appear in final findings before one accepted,
  candidate-hash-bound scout review;
- sweep detection creates packets but not verdicts; the fixed vocabulary and
  one-verdict-per-packet accounting remain enforced by `triage.py`; and
- semantic duplication never converts missing semantic evidence into a human
  review lead.

## Copied closure and fixtures

The isolated copied-layout test runs from outside both repository and audited
host. It copies exactly these six runtime files under sibling selected-skill
paths:

1. `map-subsystem/scripts/dart_lsp_facts.py`
2. `find-implicit-state/scripts/detect_dart_state.py`
3. `find-incomplete-sweep/scripts/detect_dart_incomplete_sweep.py`
4. `find-incomplete-sweep/scripts/scout.py`
5. `find-incomplete-sweep/scripts/triage.py`
6. `find-semantic-duplication/scripts/detect_dart_semantic.py`

The closure is 2,599 physical / 2,413 nonblank LOC and 106,610 bytes. Its
manifest uses `sha256(path + NUL + file_sha256 + LF)` in sorted relative-path
order and is
`2f4c7d88b66f0f6db8a705e61fa8b95c4f9c805f50c9799c7575d4c4e7cc86f1`.
No repository import, network access, Pub command, install, host package repair,
or source write is required.

The positive fixture has 16 files / 3,716 bytes, manifest
`74fd57906235c8acdbac41e810df5d5658817cb2100125cb294e6fe99c691ed2`,
and exercises resolved package imports,
state identity, Git sweep trajectory, a semantic-duplication-shaped pair, and
all named decoys. The clean fixture has 8 files / 1,189 bytes, manifest
`91ed9e351fa3f60ef62ff73b0e4bd360163e18a9df6e3f1b19a387621e4d1379`,
with enum-owned state,
consistent direct calls, and no review candidate. Both own a tracked relative
package configuration, dependency-free direct test, and exact `42` smoke.

## ML-025 economics and measured batching value

The unchanged D4 provider is 1,004 physical / 942 nonblank LOC and 41,459
bytes. The three D5 adapters are 1,074 physical / 1,010 nonblank LOC and 42,959
bytes. The focused test plus the eight-line Dart scout/triage enablement yields
a conservative maintained consumer/test cost `C = 1,645` physical LOC. Only
the two completed D5 consumers count as real shared-fact consumers; the stopped
semantic-duplication adapter does not inflate `n`.

With provider cost `H = 1,004` and `n = 2`:

- duplicated providers: `C + 2H = 3,653` physical LOC;
- one shared D4 provider: `C + H = 2,649` physical LOC; and
- saved maintenance: 1,004 physical LOC, or **27.48%**.

This clears the 25% ML-025 maintenance threshold even while charging the
stopped adapter and its tests to `C`. The copied closure carries one provider,
not two, so closure size does not regress relative to duplication.

Three alternating-order local trials measured a single four-name union pack at
2.690 s, 2.517 s, and 2.567 s (median **2.567 s**). The equivalent state and
sweep packs run separately took 4.928 s, 4.971 s, and 4.917 s combined (median
**4.928 s**). One union run saved a median 2.362 s / **47.92%** and one SDK LSP
startup. These are local macOS arm64 Dart 3.12.2 measurements, not a portable
latency SLA. They justify the already-existing Dart-local provider seam only;
they do not justify a cache, a new platform, or cross-language extraction.

## Native and preserved verification

The frozen product interpreter is
`/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python`. <!-- # host-ref-allow: required frozen P7 runtime -->
The Dart executable is `/opt/homebrew/bin/dart`. <!-- # host-ref-allow: required frozen P7 runtime -->

```text
python -m pytest -q tests/test_dart_d5_semantic_state_family.py
# 7 passed

python -m pytest -q tests/test_dart_d4_semantic_family.py
# 9 passed

python -m pytest -q \
  tests/test_find_implicit_state_go.py tests/test_java_state_chain.py \
  tests/test_find_incomplete_sweep_go.py tests/test_find_incomplete_sweep_java.py \
  tests/test_find_incomplete_sweep_typescript.py \
  tests/test_find_semantic_duplication_go.py \
  tests/test_find_semantic_duplication_java.py \
  tests/test_find_semantic_duplication_python.py \
  tests/test_find_semantic_duplication_typescript.py \
  tests/test_rust_semantic_family.py
# 50 passed

python -m ruff check <three Dart adapters> <scout.py> <triage.py> <focused test>
# All checks passed
```

For both Dart fixtures the focused suite also runs:

```text
dart analyze --fatal-infos --fatal-warnings .
dart format --output=none --set-exit-if-changed lib bin test
dart test/native_test.dart
dart bin/smoke.dart
# analyze/format/direct test pass; smoke prints exactly 42
```

## Reusable lessons and integration guidance

- Definition targets plus consumer-local bounded syntax are sufficient for
  field operations and direct named-argument sites; they are not sufficient
  for a per-function call graph. Keep that boundary visible.
- Query packs should contain the union actually required by completed
  consumers. Adding speculative semantic-duplication names would increase
  request count without filling the missing call-hierarchy fact.
- A shared provider can clear ML-025 with two real consumers, but stopped rows
  must not be counted as support or used to exaggerate economics.
- Human verdicts need content-addressed candidate lineage. A presence-only
  review file can silently approve changed evidence.
- Direct compiler-manifest scout/triage support is a small language admission
  change; detection policy and Git semantics remain Dart-local.

Root integration should merge this batch after D4, replay the copied command
and same-destination lifecycle, and publish only the two completed rows.
`find-semantic-duplication` must remain `dart-pending-implementation`. If a
future, separately accepted D4 revision adds call-hierarchy queries/results,
re-run D4 conformance and then implement D5 semantic duplication against that
public surface; do not patch D4 from this batch or fall back to a second client.
