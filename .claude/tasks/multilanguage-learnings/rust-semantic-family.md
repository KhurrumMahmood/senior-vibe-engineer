# Rust semantic read-only family learning and economics packet

## Five accepted outcomes

This batch keeps five different user contracts over one bounded evidence seam:

- `find-dormant` writes review-required private-function candidates and always
  keeps `certain_delete` at zero.
- `find-implicit-state` writes string-state operation candidates for a human
  extract-enum verdict; it never claims that the domain is closed.
- `find-incomplete-sweep` writes a compiler-resolved omission manifest, then
  preserves the existing scout-packet and fixed human-verdict triage boundary.
- `find-semantic-duplication` writes function capability leads and per-lead
  matrices; it never claims behavioral equivalence or a safe refactor.
- `rename-concept` adds Rust identifier authority to the existing lifecycle and
  strict-text assessment; it remains assess-only and never applies a rename.

The isolated Cargo 2024 workspace exercises a positive for each outcome plus
used-function, typed-state, insufficient-state, direct-wrapper, policy-shape,
generated, vendor, target-output, build, test, example, bench, macro, string,
and symlink must-not-fire/deferred surfaces. Locked/offline metadata, check,
test, Clippy with warnings denied, rustfmt, and an exact `33` smoke value pass
before and after all reports. Source/configuration hashes are unchanged.

## Shared seam and explicit limits

`map-subsystem/scripts/rust_semantic_facts.py` is a narrow fact producer rather than a
universal AST. It reuses the accepted mapper's Cargo metadata/compiler JSON,
selected module graph, roles, cfg/build boundaries, hashes, and minimal LSP
client. Each consumer supplies only the names it needs; the fact pack then asks
stable `workspace/symbol`, `documentSymbol`, and `definition` requests. The
five consumer schemas, candidate gates, reports, and human verdicts are
independent. The copied-layout test invokes the shared CLI once with the union
of bounded queries and passes that content-addressed artifact to all four
standalone detectors; rename assessment can invoke the same provider through
its evidence runner.

The pack also inventories lexical unsafe/FFI regions, `macro_rules!` regions,
and attributes without expanding or interpreting them. Consumers refuse to
promote candidates through those regions, generic/trait owners, impl methods,
or selected cfg/unknown-attribute boundaries.

No result infers runtime reachability, macro/procedural-macro expansion, build
or `include!` output, unselected cfg/feature/target variants, trait/generic
runtime behavior, unsafe/FFI behavior, reflection-string linkage, external API
behavior, deletion safety, behavioral equivalence, or rename safety. Missing
Cargo/rustc/rust-analyzer, Rust older than 1.85, incomplete locked projects,
metadata failures, and compiler failures produce `partial` or `failed` facts;
unfinished Rust support is never recorded as permanently unsupported.

## Copied closure and deletion/caller-knowledge proof

The exact assembled Rust closure for each consumer is its own skill plus the
`map-subsystem` skill, which owns both `rust_semantic_facts.py` and
`map_rust.py`. `find-incomplete-sweep` additionally retains its
language-neutral `scout.py` and `triage.py`; `rename-concept` retains its
existing `assess.py` and installed `find-concept-divergence` companion.
Copied-layout tests run all adapters from `.agents/skills`, run a standalone
fact-producing consumer without repository imports, and remove the shared fact
pack to prove the dependency fails visibly. Consumer code contains no Cargo
metadata or LSP transport knowledge.

The promotion economics test measures the actual files on every run. Let `H`
be shared fact-pack LOC and `C` total consumer LOC. Five duplicated providers
cost `C + 5H`; the accepted layout costs `C + H`. The asserted saving is at
least 25% and neither final schemas nor reports are shared. This is a better
trade than five copies of compiler/LSP lifecycle logic while keeping the seam
deletable and consumer knowledge small.

Measured after formatting:

| Surface | Physical LOC | Bytes |
|---|---:|---:|
| Shared fact pack (`H`) | 622 | 25,232 |
| Five consumer adapters (`C`) | 1,517 | 58,894 |
| Existing accepted map runtime reused by assembly | 1,466 | 57,907 |
| Hypothetical five duplicated fact providers (`C + 5H`) | 4,627 | — |
| Accepted shared-provider source (`C + H`) | 2,139 | — |
| Provider-source LOC saving | 2,488 / 53.77% | — |
| Isolated fixture | 27 files | 5,288 |

The existing map runtime is present once in the source ecosystem and installed
once as the `map-subsystem` companion for independently runnable consumers; it
is excluded from the comparison because both designs need the same accepted
Cargo/LSP primitives. The test enforces the 53.77% comparison dynamically, so drift that
drops the saving below 25% fails.

## Root integration

Root should publish serially by installing each consumer together with
`map-subsystem`, plus the listed per-skill companions. No central support
matrix, router, catalogue, plan, or shared `SKILL.md` prose is introduced here.
The root branch can later replace the two-skill assembly with an equivalent
publisher-owned mechanism only if the copied closure tests remain true and
closure size/latency do not regress by more than the established 10% gate.
