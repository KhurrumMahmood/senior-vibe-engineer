# C++20 accepted-evidence structure proposals

## Outcome

`propose-boundary` and `propose-folder-reorganization` now consume already
accepted C++ omnibus/topology findings plus the current complete C++ map. They
never rerun detection and never mutate host source. Each terminal run atomically
replaces three distinct artifacts beneath its own report root:

- `proposal.md` is the human review narrative;
- `evidence.json` binds acceptance hashes, native proof, source preservation,
  and explicit non-claims; and
- `scope.json` carries the exact replayable plan while setting
  `mutation_authorized` to false.

The boundary consumer accepts only a private, compiler-owned free-function seam.
It keys declarations by namespace-qualified name plus exact signature, requires
the complete selected overload set, binds every compiler-observed caller edge,
and accounts separately for source, private-header, Make, tests, created files,
and the after-tree translation-unit census. A human-reviewed cohesive result is
a complete deferral.

The folder consumer accepts only one three-or-more-member direct-sibling C++
prefix cluster under the explicit
`group-three-private-cpp-translation-units` convention. It accounts for every
translation-unit move, compiler-owned private auxiliary header, include edit,
namespace-qualified declaration and overload, compiler-observed caller, Make
edit, test surface, and after-tree translation-unit census. Human `keep_flat`
and absent-convention decisions are complete deferrals.

## C++ refusal boundary

The compile database and Clang map provide exact C++20 declarations, private
header ownership, static references, dependencies, and the observed Make graph.
They do not resolve the open-world parts of C++. Both consumers therefore require
a hash-bound human acceptance envelope with an explicit resolution and basis for
templates/specializations, virtual/dynamic dispatch, function pointers/callbacks,
header exposure, ODR/ABI, external consumers, and build variants. Any missing or
unresolved item refuses before plan validation.

Mechanically, the accepted path also refuses incomplete overload inventories,
template-marked selected declarations, public or ambiguous headers, callable
definitions in a moved header, caller mismatch, stale artifact/source hashes,
and incomplete source/header/build accounting. Human review cannot turn a
public-header or compiler-ambiguous path into an accepted private seam.

## Native and preservation proof

The focused fixture contains a namespace-qualified omnibus translation unit with
an overloaded `render_export`, a three-file `billing_*` topology cluster, private
compiler-owned headers, two known caller translation units, a Make-generated
C++20 compilation database, native test, and executable smoke.

For each accepted proposal the consumer:

1. regenerates the current-tree C++20 compile database and runs the native test
   and smoke obligations;
2. verifies that no audited C++ source, header, or Makefile byte changed;
3. applies only the accepted exact plan in a disposable copy;
4. repeats compile-database, test, and smoke proof against the exact after-tree
   translation-unit census; and
5. leaves the host source byte-identical.

The capability test independently replays each emitted `scope.json` in another
copy, exercises all seven uncertainty refusals plus human/convention refusal,
and runs each single-file consumer from a copied installation layout. The
preserved C++ omnibus/topology and map final-outcome tests remain green.

## Reusable lesson

C++ proposal consumers should not flatten compiler identity back to spelling.
The minimum safe key is qualified name plus exact signature, and the selected
overload inventory must equal the compiler-observed inventory in both definition
and declaration locations. Read-only proposal value comes from combining that
closed static evidence with explicit open-world human resolutions, not from
claiming the compilation database proves ABI, ODR, runtime dispatch, external
consumers, or all variants.
