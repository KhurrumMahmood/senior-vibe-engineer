# Dart D7 read-only proposal family learning and economics packet

Status: isolated implementation candidate on exact base `d8b4755`, plus the
unchanged accepted-evidence validator commit `e210e1d`; no shared `SKILL.md`,
coverage, matrix, router, catalogue, active-plan, installer, `_common`, D1,
D4, D5, framework-profile, or publication change is made here.

## Dispositions and final outcomes

- `propose-boundary` is implemented against one accepted
  `dart-lsp-facts-v1` D4 query pack and one content-addressed human selection.
  Its ready artifact cites the selected public declarations, resolved callers,
  public barrel, compatibility shape, characterization-test surface, exact
  source edit, and new public library. The positive fixture proposes
  `lib/invoicing.dart` while preserving the root barrel and all old internal
  paths. A separately accepted cohesive target yields the successful final
  outcome `deferred/defer_cohesive_target`; unresolved, partial, stale, or
  unaccepted evidence never yields readiness.
- `propose-folder-reorganization` is implemented against one accepted D1
  `billing_*` cluster and the accepted D4 import-impact pack. The ready artifact
  accounts for all three members and all six resolved import/export edges,
  preserves `lib/src/billing.dart`, and proposes the exact
  `lib/src/billing/{invoice,payment,tax}.dart` after-tree. Accepted cohesive
  judgment and absent convention both yield successful `deferred` outcomes.
  Package-URI impact, unresolved edges, stale evidence, unsafe members, and
  incomplete acceptance do not yield a move plan.
- `unify-shadows` is stopped honestly and remains pending. The accepted D5
  `find-semantic-duplication` artifact is
  `partial/accepted_provider_fact_gap`, with zero leads and the exact missing
  fact `per-function outgoing call-hierarchy results with source and target
  lineage`. D4 v1 does not issue `textDocument/prepareCallHierarchy` or
  `callHierarchy/outgoingCalls`. This batch adds no Dart unification adapter,
  does not change D4, and does not substitute spelling, lexical similarity, or
  raw references for an accepted D5 finding.

## Accepted-evidence and artifact lifecycle

Both implemented consumers call
`_dart/dart_accepted_evidence.py::validate_accepted_evidence` unchanged. The
validator checks the producer/version/terminal status, artifact hashes,
selection hash, acceptance hash, source/configuration hashes, cited spans,
human verdict, reviewed boundaries, and native obligations before consumer
policy runs.

D1's existing final artifact uses integer schema version `1`, while the shared
validator intentionally requires a non-empty string producer schema. The
folder consumer therefore accepts a small `dart-folder-cluster-v1` producer
artifact that embeds the exact selected cluster hash and names both the
original D1 artifact and D4 query pack. Consumer-local checks re-open the
original D1 artifact, locate exactly one canonical-hash match, and compare its
pattern, language, parent, prefix, member list, and D1 evidence hash. This
preserves D1 as authority without changing it or weakening the validator.

Each consumer writes only `inspection.json` and `proposal.md` beneath its
authorized report root. The pair is staged and directory-replaced as one
terminal outcome, so a ready -> failed -> ready replay cannot retain stale
plan files. Existing symlink traversal is rejected. Invalid acceptance,
partial upstream status, stale source bytes, missing Dart, and native failure
produce visible terminal refusal artifacts with no edits or moves. The focused
test seeds an extra stale artifact and proves replacement removes it.

Accepted native commands are data, not executable authority. Each consumer
allowlists exactly the D0 matrix: fatal analyze, check-only format over safe
existing roots, one dependency-free direct Dart script, and one exact-output
smoke script. No Pub command, dependency resolution, network operation,
package repair, `dart run`, or `dart test` is invoked.

## Exact citations, read-only behavior, and disposable proof

Ready facts must match the envelope's already-validated cited spans at exact
`path:line:column` coordinates. Public declarations, resolved callers,
cluster members, and every import/export rewrite retain these citations in
both final artifacts. Tests and excluded roles may establish the available
characterization surface but never establish ownership.

Before validation, each consumer hashes every audited-host file outside
`.git/` and `reports/`. It repeats that snapshot after current-tree native
verification and after disposable verification. Only report artifacts change.
The exact plan is applied to a temporary copied host and must pass analyze,
format, direct test, and exact smoke there. The focused test independently
re-applies each emitted plan to a second disposable tree and runs the same
matrix, proving the final executable boundary rather than trusting an
intermediate planner result.

## Copied closure and fixtures

Each on-demand closure is the selected consumer plus the accepted-evidence
validator copied beside it; it imports no repository runtime and performs no
network/install operation.

| Closure | Physical / nonblank LOC | Bytes | Manifest SHA-256 |
|---|---:|---:|---|
| `propose-boundary` + validator | 1,139 / 1,025 | 45,621 | `e60dd296ba8ef17847628e115ccba24a6c198487beedc5c348c09303f9b3dd57` |
| `propose-folder-reorganization` + validator | 1,259 / 1,145 | 50,116 | `df9ca990b134c83a9a810aee80d87aec60304d527f12ec21ca0334fac470faa7` |
| both consumers + one validator | 1,968 / 1,796 | 77,228 | `e2bb4715cfa456adf0349aa003c076938455781b633598e978a7acb8e0c808a0` |

The manifest hashes sorted repository-relative
`path + NUL + file_sha256 + LF` rows. The positive fixture has 17 files / 1,817
bytes and manifest
`ea0923b64488a62cfe9c8abed5c70b147a278e7b14612385d59df91b55af6650`.
It contains the accepted child domain, three-file prefix cluster, direct
callers, public barrels, package-aware configuration, exact test/smoke, and
generated/example/vendor decoys. The clean fixture has 9 files / 839 bytes and
manifest
`f71ed78994ccf4d37699794d7018f7c3430d4df8aefe825c12ca6c08325ae305`;
it supplies a cohesive boundary defer case and below-threshold flat siblings.

## ML-025 economics

Only the two implemented D7 consumers count. `unify-shadows` is stopped and
does not inflate `n`.

- consumer adapters plus focused test: `C = 2,288` physical LOC;
- accepted-evidence validator: `H = 430` physical LOC;
- literal per-consumer validators: `C + 2H = 3,148` physical LOC;
- one shared validator: `C + H = 2,718` physical LOC; and
- saved maintenance: 430 physical LOC, or **13.66%**.

The D7-only comparison does **not** clear the 25% extraction threshold. This
batch therefore extracts no additional provider, platform, proposal schema,
native runner, or lifecycle layer. It consumes the already-owned D6 acceptance
contract because the work packet requires the same acceptance boundary, but
does not claim D7 economics independently justify a new shared abstraction.

## Native and preserved verification

The frozen product interpreter is `/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python`. <!-- # host-ref-allow: required frozen P7 runtime -->
The Dart executable is `/opt/homebrew/bin/dart`.
<!-- # host-ref-allow: required frozen P7 runtime -->

```text
python -m pytest -q tests/test_dart_d7_proposal_family.py
# 10 passed
```

The positive and clean fixtures, both consumer-run disposable after-trees, and
both independently applied emitted plans execute:

```text
dart analyze --fatal-infos --fatal-warnings .
dart format --output=none --set-exit-if-changed lib bin test
dart test/native_test.dart
dart bin/smoke.dart
# exact smoke: invoice:116 (positive/after-trees), core:42 (clean)
```

Final preserved-family, validator, Ruff, self-lint, and hook transcripts belong
in the worker handoff and commit evidence; this packet does not pre-claim runs
that have not completed.

## Limitations and root integration

Both artifacts remain selected-configuration, proposal-only evidence. They do
not prove runtime reachability, external consumers, semver, reflection,
dynamic loading, generated APIs, parts/augmentations, conditional platforms,
cross-package moves, or Flutter/framework semantics. Human review remains
mandatory and no audited source is edited.

Root should integrate serially after D1/D4 and after the standalone D6
validator commit. Replay the exact copied closures from outside repository and
host, then publish only `propose-boundary` and
`propose-folder-reorganization`. Keep `unify-shadows` at
`dart-pending-implementation` until a separately accepted D5 producer carries
complete call-hierarchy lineage and a selected human-approved consolidation
shape. Do not patch D4 or create a second semantic detector from this batch.
