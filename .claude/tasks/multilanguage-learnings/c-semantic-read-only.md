# C semantic read-only cohort

Base revision: `63e98b47a4ae829e8921febb44217eaa31dbe9b1`

## Bounded outcome

One C-local, standard-library-only fact producer supports five independent
read-only outcomes without changing the accepted C map implementation:

| Skill | Useful final value | Deliberate authority limit |
|---|---|---|
| `find-dormant` | A private `static` definition with zero Clang direct references is a `review_required` lead. | `certain_delete` is always zero; address-taking, function pointers, registration, macros, variants, and external reachability defer. |
| `find-implicit-state` | Three direct assignments of distinct string literals to one resolved `char *` state field produce an `enum_review_only` candidate. | Pointer aliasing, external mutation, closed-domain proof, and automatic migration are withheld; a human verdict is required. |
| `find-incomplete-sweep` | Four resolved compound literals with three newer designated `region` fields and one older omission produce one Git-gated candidate. | Macro-expanded literals are excluded, and a candidate-hash-bound fixed-vocabulary human verdict is required before any completion handoff. |
| `find-semantic-duplication` | Two independently called functions returning the same resolved record/designated-field shape produce a static review lead. | The lead is never behavioral equivalence or consolidation authority; aliasing, UB, side effects, function pointers, and external behavior remain unresolved. |
| `rename-concept` | Old and new compiler-observed typedef declarations produce a read-only half-applied assessment. | Macro/string/inactive-variant residue and external consumers remain explicit; even a clean selected source is only candidate-complete pending external review. |

The provider accepts only a non-empty exact `arguments` compilation database
rooted in the copied host, using the selected Clang 21 executable, explicit
`-std=c17`, and exactly all eligible first-party `.c`/`.i` translation units.
Clang `-MM` owns headers and freshness inputs. Clang AST JSON supplies
declarations, `DeclRefExpr`/`MemberExpr` facts, direct string assignments,
compound literals, and function-pointer boundaries. The consumers never infer
an inactive branch, macro-generated fact, indirect call target, alias target,
external consumer, or runtime behavior.

## Lifecycle and final-boundary proof

The focused fixture has 9 regular files, 5,724 bytes, and manifest SHA-256
`ab5a3490c4214fb77a45034963e890378f758bf6e4d38c40eca384ba870b57d8`.
It includes positive and clean selected surfaces, generated/vendor/test/build
decoys, an untraversed source symlink added by the test, a function-pointer
registry, a macro/string rename residue, and two dated Git commits for the
designated-initializer sweep.

The restrictive native command is `make clean compile-db CC=clang` followed by
`make test CC=clang`; the executable smoke output is exactly
`semantic:running:us:112:1:legacy_status`. The capability test runs that native
boundary before and after all five consumers and compares every non-report
source/configuration byte and symlink target.

Missing and too-old Clang are `partial`; missing, stale, incomplete, mismatched,
or non-C17 databases are `partial`; malformed databases, dependency failures,
malformed/failed AST output, and unexpected source mutation are `failed`.
Every terminal run atomically replaces its destination with empty claim arrays.
The test proves valid → incomplete, valid → malformed, malformed C, and recovery
at reused destinations, plus copied external-library execution of all five
final artifacts.

## Interface depth and reuse decision

- **Deletion test:** removing `_c-semantic` would duplicate compile-database
  trust, Clang versioning, dependency closure, source roles/fingerprints, AST
  traversal, macro/function-pointer boundaries, and terminal policy across five
  consumers.
- **Caller knowledge removed:** consumers only interpret already-attributed C
  facts; they do not know compiler argv rewriting, CDB freshness, header
  ownership, AST file/offset inheritance, or stale-pack checks.
- **Test surface:** the public CLI fact pack and each final consumer artifact
  are exercised from a copied sibling layout; no private helper is imported by
  the capability test.
- **Adapter count:** none. This is one C-local producer, not a port, protocol,
  cache, daemon, package manager, or cross-language semantic platform.
- **Decision:** keep one language-local helper. Its 695 physical lines plus 544
  adapter lines and 311 test lines are 1,550 maintained lines; five literal
  producer copies would require 4,330 lines, so the immediate five-consumer
  design avoids 2,780 lines (64.20%).

Copied helper-plus-consumer byte sizes are 32,837 dormant; 32,614 state;
36,103 sweep; 33,888 duplication; and 33,513 rename. The helper is copied as a
sibling external-library dependency, never imported from a checkout or the
accepted map skill.

## Verification and handoff

Focused verification uses the repository-owner-supplied runtime explicitly:

```text
<product-repo>/.venv/bin/python \
  -m pytest -q tests/test_c_semantic_family.py

<product-repo>/.venv/bin/python \
  -m ruff check <the C provider, five consumers, and focused test>
```

Focused result before packet capture: `4 passed in 5.17s`; Ruff passed. Root
retains all `SKILL.md`, profile, coverage, matrix, catalog, router, shared docs,
plan/ledger, and publication edits. No new tool was installed, no accepted C
map file changed, and this cohort authorizes no proposal, guard, or mutation.
