# C++20 `move-path` learning packet

Status: isolated implementation candidate; root publication remains pending

## Final value proved

One authored C++20 implementation unit can move inside a closed Make-built
executable without changing its namespace, symbols, public headers, or global
defined-symbol surface. The representative transaction moves
`src/invoice.cpp` to `src/billing/invoice.cpp`, rewrites its one
location-sensitive include to `../invoice_internal.hpp`, and updates the exact
Makefile path tokens that own compilation. The public include spelling and all
other source/header bytes remain unchanged.

Dry-run requires a current, complete, single-variant C++20 compilation
database for every implementation unit beneath the declared source and test
roots. Clang dependency output owns the exact first-party source/header impact
map. The preview also executes the current native test and exact smoke, applies
the reviewed changes in an isolated copy, regenerates its compile database,
reruns the native boundary, compares dependency ownership and `nm` global
defined symbols, and proves the virtual after-tree before emitting authority.

`evidence.json` binds the plan, adapter, source tree, compile database, compiler
impacts, exact edit spans, tool binaries, symbol set, and expected after-tree.
Apply requires the reviewed evidence SHA-256, repeats the analysis, regenerates
the real compile database, runs native test/smoke, and checks the exact tree.
Check proves the same completed state. A failed postflight restores regular
file bytes/modes and symlink targets from the complete pre-apply snapshot.

## Honest refusal boundary

This is deliberately a source-location move, not a C++ identity refactor. It
requires the same filename and rejects namespace/symbol/scope configuration,
non-closed artifacts, or undeclared external-consumer scope. Exact pre/post
global symbol equality is the ABI identity oracle for the moved object; owned
`extern "C"` or visibility boundaries remain outside the cohort.

The adapter stops before writes for reachable `.h`/`.inc` ambiguity, owned
templates or explicit instantiations, conditional/macro-computed includes,
compile-command macro/module/PCH variants, source-file includes and their ODR
risk, external or excluded old-path consumers, incomplete/stale/multi-command
compile evidence, path/symlink boundaries, generated/vendor/build ownership,
header-lineage changes, or native/symbol/exact-tree drift. It neither infers
inactive preprocessing variants nor claims header-only, template-library,
shared-library, plugin, public-header, cross-build, or external-consumer
completeness.

## Reuse decision

The implementation is one standalone stock-selected script with only the
Python standard library. A copied `cpp_source_move.py` runs outside the source
checkout under isolated/no-site Python and completes the real preview and
approved apply journey. No generic mutation platform or C/C++ shared adapter
was introduced: compilation-database completeness, Clang dependency lineage,
C++ uncertainty refusals, and global-symbol proof remain local to this one
language/build profile.

The reusable product lesson is narrower than the implementation: source path
is not C++ symbol identity. A safe useful move can preserve identity when a
compiler owns the complete source/header graph, the build owns the exact path
edits, a closed native outcome is executable, and the adapter refuses rather
than extrapolates across preprocessing, templates, ODR, ABI, or consumers it
cannot observe.

## Verification and limits

The focused suite proves 14 outcomes: full preview/approve/apply/check,
compiler-owned impacts, current complete compile evidence, nine identity and
uncertainty refusals, stale/missing authority, exact rollback, and a copied
single-file closure. The fixture is a dependency-free Make project using
Apple Clang++ 21 in strict C++20 mode, GNU Make 3.81, and `/usr/bin/nm`.

This is not CMake/Bazel/Meson support, a header move, namespace or class rename,
template migration, ABI compatibility certification, ODR analysis, macro
configuration matrix, library packaging operation, or general C++ refactoring
engine. Root alone owns capability/matrix/catalogue publication after merge and
preserved-family replay.
