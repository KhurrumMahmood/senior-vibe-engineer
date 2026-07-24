# C17 lexical/filesystem cohort handoff

Base revision: `63e98b4`

## Outcome and bounded support claims

Five independent read-only C consumers now reach distinct final artifact
boundaries from copied closures. All claims require a valid, current, complete
C17 `compile_commands.json`, Apple Clang 21+, GNU Make 3.81+, a passing
host-owned `make test`, and a passing executable smoke.

| Skill | Proved value | Final artifacts | Bounded claim |
|---|---|---|---|
| `adapt-project` | Counts five compiler-owned translation units and two headers, identifies Make, and emits the observed C17 check/test/smoke commands. | `adapter.yml`, `adapter.json`, `report.md`, `evidence.json` | Objective compile-database/project facts only; no framework or layout endorsement. |
| `explain-code` | Annotates direct `billing_state`, `billing_invoice`, and function declaration/definition spelling with exact spans and hashes. | explanation Markdown, `targets.json`, `scan.json`, annotations, unexplained/surprises sidecars | Direct static/lexical declarations only; no macro-expanded identity, callers, behavior, or ABI claim. |
| `find-concept-divergence` | Finds the glossary avoid term `cancelled_order` once in authored C and distinguishes a preferred-only clean run. | `findings.jsonl`, `report.md`, `findings.json`, `scan.json` | Strict text evidence only; comments/strings can be review noise and the hit is not symbol identity. |
| `find-duplication` | Finds exactly two seven-line functions with identical normalized direct body spelling and excludes a changed body. | `collapsed.json`, `ranked.json`, `triage.md`, `findings.json`, `scan.json` | Exact spelling lead only; never semantic/behavioral equivalence or consolidation authority. |
| `find-folder-topology-drift` | Finds exactly one three-file `billing_*` translation-unit cluster and produces a threshold-four clean run. | `detections.jsonl`, `report.md`, `findings.json`, `scan.json` | Direct-sibling filename evidence only; no framework/layout health, ownership, or safe-move claim. |

The accepted C `find-comment-drift` and `map-subsystem` implementations were
not modified.

## C-local fact contract

`.claude/skills/_c/c_lexical_facts.py` is the only shared implementation. It
owns facts/mechanics needed immediately by all five consumers:

- full pre-eligibility `.c`, `.i`, `.h`, `.inc`, Makefile, test, generated
  tree/marker, vendor, build, report, ambiguous-header, and symlink roles;
- content-derived manifests and post-process source preservation;
- Apple/upstream Clang 21+ and Make 3.81+ missing/old/failing states;
- exact C17 compile-command shape, compiler identity, complete translation-unit
  coverage, compiler dependency-owned headers, and freshness;
- per-translation-unit `clang -fsyntax-only` using recorded flags;
- direct comment/string-aware declaration and function spans/hashes;
- host-owned Make test and executable-smoke evidence with dead proxy endpoints;
- atomic artifacts, stale-artifact clearing, and terminal return policy; and
- explicit lexical/static limitations without interpreting them.

Consumers retain adaptation, explanation, glossary, clone, and topology
meaning plus their distinct schemas. No universal AST, shared `_common`
platform, cache, package manager, daemon, or external dependency was added.

Deleting the provider forces five consumers to recover role order, tool/version
policy, compile-database validation, dependency ownership, syntax commands,
native gates, manifests, preservation, and lifecycle. The focused test asserts
that each consumer imports `collect_snapshot` while embedding none of the
compile-database, generated-marker, or native-failure policy.

The provider is 762 physical/692 nonblank lines; the five consumers are 787/729
and the focused test is 424/371. Shared provider + consumers + test is 1,973
physical lines versus 5,021 with five literal provider copies, a **60.71%**
maintenance reduction. The installed unique provider/consumer union is 57,137
bytes versus 173,713 bytes with five provider copies, a **67.11%** reduction.

## Copied closures and fixture

Manifests hash sorted repository-relative `path + NUL + file SHA-256 + LF`
rows. Each copied consumer closure contains exactly its adapter and sibling
`_c/c_lexical_facts.py`.

| Closure | Files | Bytes | Manifest SHA-256 |
|---|---:|---:|---|
| `adapt-project` | 2 | 33,495 | `e5a8531b0ba900bae51c5b7d78185960fe087b566d180884a11658b3c09660df` |
| `explain-code` | 2 | 34,065 | `8a438946126dae1297423712387817ade0a6eebf14905ccee73d23b37fe22ef8` |
| `find-concept-divergence` | 2 | 37,501 | `b48e910d7b5ad05c1ad084ca1b6a4cdbc74bc34f1f7433fb16b2f0e12d076d7e` |
| `find-duplication` | 2 | 34,607 | `a2d023b10ac22224c8e9563825b2bb51673d4f4e739dfbde8ea665f5cc8d35a7` |
| `find-folder-topology-drift` | 2 | 34,045 | `8a327e85718ea7304ac897eb642137dc7b4a87f17cfe83bf88c37657241645b1` |

The 19-file fixture is 5,934 bytes with manifest
`9622d593cc47036546e76a3d7f5fc06da5aec4554f609f0eb1475f67164163ff`.
The provider content SHA-256 is
`f22b103336ce858dfb007eb46365155b0ccde5efa52a98237d6af0b0ffc94a31`.

## Lifecycle, native proof, and verification

The focused suite proves all five copied consumers through complete -> missing
Clang -> complete transitions at the same destinations. It also proves:

- distinct positive artifacts and complete-evidence clean outcomes;
- malformed/unlisted C source becomes `partial` through an incomplete database,
  with no false clean and no source mutation;
- missing/old tools and missing/stale/incomplete metadata are partial evidence,
  while malformed metadata and native process failures are failed evidence;
- role decoys cannot become concept, clone, or topology findings;
- exact source/spelling hashes resolve against copied host bytes; and
- `make test` prints `c-native-test:ok` while the smoke prints exactly
  `c-lexical-smoke:132`.

Verification completed without installation, network, or caches:

- focused cohort: `14 passed in 16.89s`;
- targeted Ruff over the provider, five consumers, and focused test: passed;
- preserved map/comment/spine replay: 25 passed, one pre-existing frozen
  runtime-closure manifest mismatch described below.

The preserved-suite mismatch is not caused by this lane. At base `63e98b4`,
`.claude/tasks/p7-baseline/c-pilot-baseline.json` records the six-file generic
runtime closure as 43,204 bytes / SHA
`82e09630b66710dc479d254f32bd6949140f9a67e2f69bfc8a6503d24d768edb`,
while the unchanged listed files are 39,725 bytes / SHA
`b83ecd3f9791b59f0e37fa03835f18bf255f1565088dd273a640eb31436508fe`.
This lane intentionally did not alter the frozen baseline or any listed file.

## Honest limitations

- Direct source spelling is not macro-expanded symbol identity, reachability,
  runtime behavior, a complete type model, or conceptual identity.
- Inactive preprocessor branches and arbitrary compile/build variants remain
  unresolved even when the recorded database is complete.
- Function pointers, callbacks, aliasing, linkage across variants, dynamic
  loading, ABI, object layout, and undefined behavior are unresolved.
- Exact normalized function bodies are advisory clone leads, never semantic or
  behavioral equivalence and never safe-consolidation proof.
- Filename clusters prove no framework convention, layout quality, ownership
  boundary, include/build impact, or move safety.
- C++, Objective-C, CUDA, OpenCL, assembly, and framework semantics are outside
  this cohort.

## Root integration

Root should integrate this commit serially, then publish shared truth:

1. Keep `_c/c_lexical_facts.py` as a sibling external-library closure for all
   five consumers; reject consumer-only installs and do not duplicate it.
2. Update exactly the five shared `SKILL.md` files, C coverage rows, generated
   matrix/catalog/router projections, and closure manifests in the root-owned
   publication lane. Preserve all other language paths and the two accepted C
   implementations.
3. Replay this focused suite plus `tests/test_map_subsystem_c.py` and
   `tests/test_find_comment_drift_c.py`. Treat the frozen spine-manifest issue
   as a separate pre-existing baseline repair, not permission to widen this
   cohort.
4. Keep future semantic C work separate; these lexical facts must not be
   promoted into equivalence, framework, runtime, or mutation claims.
