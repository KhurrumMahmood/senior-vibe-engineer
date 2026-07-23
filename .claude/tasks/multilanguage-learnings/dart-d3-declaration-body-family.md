# Dart D3 declaration/body family stop packet

## Outcome and exact dispositions

D3 stopped at the locked-provider gate on base revision
`8821fb4be855c517225eb5593170e2e4140db71e`. The accepted D2 producer runs
successfully and preserves the audited host, but its public payload does not
contain the declaration/body facts that D3 is required to consume. The D3
packet forbids changing that producer, forking it, or adding a second parser,
so no D3 adapter, fixture, or support claim was created.

| Skill | Disposition | Blocking public fact |
|---|---|---|
| `explain-code` | `dart-pending-implementation` | Direct class, enum, extension, typedef, and top-level-function declarations; declaration kinds/privacy/spans; export directives. |
| `find-complexity-hotspots` | `dart-pending-implementation` | General named function/method body spans and direct-body branch events that stop at nested closures/local functions. |
| `find-duplication` | `dart-pending-implementation` | General named function/method body spans and their public-analyzer token sequence for consumer-local normalization. |
| `find-omnibus` | `dart-pending-implementation` | Direct named declarations with kinds, containers, privacy, and exact spans so syntax candidates can be linked to fixed scout verdicts. |

Nothing in this packet publishes Dart support. Central `SKILL.md`, coverage,
matrix/projections, routers/catalog, profiles, plan, installer, and backlog
surfaces remain unchanged.

## Reproduced public contract

The provider was invoked with the required product Python and Dart 3.12.2 over
the accepted D2 host fixture, including locked offline analyzer setup and the
native analyze/format/direct-test/smoke matrix. It returned `0`, status
`complete`, failure kind `none`, and `source_manifest.preserved: true`.

The observed per-file keys were exactly:

```text
calls, comments, diagnostics, file, functions, source_sha256
```

The observed `functions` rows were only the two D2 doc-adjacent fixed-return
shapes, `invoiceRate` and `matchingRate`, with:

```text
comment, comment_end, comment_line, comment_offset, end, fixed_return,
line, name, offset
```

The observed `calls` rows contained:

```text
column, end, in_try, line, offset, spelling
```

This agrees with the locked Dart tool: `_FactsVisitor` emits only top-level
functions accepted by `_functionFact` (adjacent `///` plus fixed numeric
return) and unqualified method invocations. It emits no directives,
declarations, general bodies, body tokens, or branch events. The producer's
claim boundary also remains the narrower D2 comments/fixed-return/direct-call
contract.

Verification actually run from the isolated D3 worktree:

Product Python:
`/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python`. <!-- # host-ref-allow: required frozen P7 runtime -->

```text
$PRODUCT_PYTHON -m pytest -q \
  tests/test_dart_d2_syntax_family.py::test_dart_locked_public_analyzer_facts_roles_native_and_zero_write \
  tests/test_dart_d2_syntax_family.py::test_dart_tool_package_lock_and_public_api_surface_are_exact
```

Result: `2 passed in 5.45s`. The live schema probe and timing runs also
returned complete, source-preserving snapshots. No network, dependency
install/update, audited-host report write, push, or main-worktree change was
performed.

## Exact minimal additive D2 gap

Root/D2 ownership must add the following syntax facts through the existing
public-`package:analyzer` tool before D3 can resume. These are facts only; the
four consumers must continue to own thresholds, normalization, ranking,
prose, scout judgment, and final artifact schemas.

| Public fact group | Minimum fields/semantics | D3 consumers |
|---|---|---|
| `directives` | Directive kind (`import`, `export`, `part`, `part_of`), URI text where present, and exact offset/end/line/column. Conditional/augmentation shapes must remain visibly unsupported or partial. | `explain-code` |
| `declarations` | Name, declaration kind (including class, enum, extension, mixin, typedef, top-level function, method, constructor, getter/setter/operator), top-level/container identity, privacy, and exact declaration offset/end/line range. Anonymous declarations remain explicit rather than guessed. | `explain-code`, `find-omnibus` |
| `named_bodies` | Name, declaration kind, container, declaration span, body offset/end/line range, and enough identity to join the row to its declaration. Include named top-level functions and methods; label constructors/accessors/operators so each consumer can apply its own eligibility policy. | `find-complexity-hotspots`, `find-duplication` |
| `direct_body_branches` | Per named body, exact kind/span events for `if`, loops, non-default switch cases, `catch`, `&&`, and `||`; traversal must stop at nested closures and local-function bodies. Do not emit a complexity score. | `find-complexity-hotspots` |
| `body_tokens` | Ordered public-analyzer tokens with exact offsets/end and lexeme/token kind for each named body. Do not emit clone groups, normalized hashes, thresholds, or rankings. | `find-duplication` |

The existing file `source_sha256`, exact spans, tool-package SHA, analyzer
version, SDK version, inventory, native results, and source manifest are
sufficient for D3 provenance once these facts exist. A D3 adapter can compute
spelling/body hashes from the cited source slice and reject a stale producer
by its accepted tool-package SHA; no universal AST or second parser is needed.

## Why no legal workaround exists

- Reading Dart source with consumer regexes or a new lexer would be the second
  parser prohibited by D3 and would not reliably distinguish declarations,
  nested bodies, operators, comments, or strings.
- Treating the current D2 `functions` rows as general functions would silently
  omit every undocumented, computed-return, method, class, enum, extension,
  and typedef declaration and could incorrectly report a clean result.
- Reusing `calls` as complexity evidence would miss every required branch
  shape and cannot establish the direct-body nested-function boundary.
- File size, strings, or raw identifier counts cannot replace declaration
  facts for omnibus nomination and cannot produce candidate-to-scout span/hash
  lineage.
- Raw source slicing cannot produce a body slice until the analyzer publishes
  the body span, and whitespace stripping is not token normalization.

Therefore partial D3 adapters would add no useful bounded outcome; the honest
state is to keep all four skills pending until the accepted producer contract
is extended by its owner.

## Batching measurement and analyzer-JIT value

One source-preserving provider run was compared with four independent starts
over the same accepted fixture and options. This is a local observation, not a
performance threshold.

| Shape | Wall time | Analyzer execution time |
|---|---:|---:|
| One batched provider run | 5.6067 s | 4.5086 s |
| Four independent starts | 20.3657 s | 16.6793 s |
| Avoided by one shared snapshot | 14.7590 s (72.47%) | 12.1707 s (72.97%) |

The four independent wall observations were 5.0341, 5.5451, 4.9104, and
4.8761 seconds; their analyzer observations were 4.1345, 4.5549, 4.0107, and
3.9792 seconds. The analyzer execution dominates each start, so a single
content-addressed D3 snapshot would avoid three analyzer process/JIT starts.
Once the missing facts land, D3 should key that in-memory/on-disk snapshot by
the existing source manifest, tool-package SHA, analyzer/SDK versions, target,
and native options, invoke the producer once for the union of four consumers,
and validate the key independently in every consumer. It must not let one
consumer's judgment or terminal state stand in for another's.

## Deferred proof matrix

No D3 runtime exists to exercise, so the required positive/clean/must-not-fire,
partial/failure, valid -> failed -> valid, copied-closure, final-artifact,
candidate/scout, or preserved-language proofs were not represented as passing.
When the D2 gap is accepted, the D3 fixture and focused test must prove:

- the four existing final artifact schemas exactly as named in the contract
  map, including explanation annotations/sidecars, complexity `latest`, the
  five duplication artifacts, and omnibus candidate/scout lineage;
- exact declaration/body/event spans, source/body/spelling hashes, and every
  candidate's stable lineage into a fixed scout verdict;
- one fixed `confirmed_omnibus` verdict for the four-domain library and one
  fixed `facets_not_domains` verdict for the cohesive control library, with no
  ungraded candidate becoming confirmed;
- positive, clean, excluded-role, strings, private/generated/re-export,
  nested-function, trivial-body, constructor/accessor, formatting, barrel,
  extension/mixin, and file-size-only negatives;
- complete -> failed parse/native gate -> complete and complete -> partial
  missing companion -> complete at each existing destination, with stale
  successes removed atomically;
- copied selected-skill plus sibling `_dart` closure executed from outside the
  repository and host, without ambient imports, network, installs, Pub writes
  in the host, or source mutation; and
- native `dart analyze --fatal-infos --fatal-warnings`, check-only format over
  authored roots, direct dependency-free test, exact smoke stdout, focused D2
  producer tests, and all preserved language-family tests for the four skills.

## Limits and learning

- The stop is a public-contract mismatch, not a Dart/analyzer/tool-acquisition
  failure. The locked analyzer, offline Pub setup, native matrix, and source
  preservation all passed.
- The contract map describes D2's shared syntax snapshot as including direct
  declarations, directives, named bodies, and bounded direct-body syntax, but
  the accepted D2 implementation and learning packet describe and emit only
  the narrower three-consumer facts. Acceptance of prose did not establish the
  future-consumer API.
- A provider seam should be acceptance-tested for every promised public fact
  family, even when its first consumers need only a subset. Alternatively, the
  contract map should label future fields as reserved rather than present.
- The runtime measurement confirms the proposed batching economics before D3
  code exists: analyzer JIT startup is the concrete shared cost. It does not
  justify a cross-language provider, universal syntax schema, persistent daemon,
  or shared consumer judgment.

## Root integration steps

1. Extend and accept the existing D2 provider/tool in its owning lane with only
   the five additive fact groups above; keep public analyzer APIs, the exact
   lock, host-safe offline setup, roles, lifecycle, and native/source proof.
2. Add direct provider tests for the new fact fields, nested-body stopping,
   exact spans/tokens, unsupported syntax, and valid -> failed -> valid
   lifecycle. Record the new tool-package manifest SHA.
3. Rebase/restart D3 from that accepted revision. Implement four consumer-local
   adapters over one content-addressed producer result; do not copy analyzer
   logic or consumer schemas into `_dart`.
4. Replay the deferred proof matrix and the one-versus-four runtime comparison
   in the copied closure. Keep both fixed omnibus scout verdicts and complete
   candidate accounting.
5. Only after those final outcomes pass should root publish the four bounded
   dispositions and update central coverage, projections, routing, catalog,
   profiles, plan, installer, or backlog surfaces serially.
