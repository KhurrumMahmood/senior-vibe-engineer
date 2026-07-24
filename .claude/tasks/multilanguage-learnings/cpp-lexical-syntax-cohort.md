# C++ lexical/filesystem/syntax cohort

## Scope

Implemented bounded C++20 support for `adapt-project`, `explain-code`,
`find-concept-divergence`, `find-duplication`,
`find-folder-topology-drift`, `audit-decisions`,
`find-complexity-hotspots`, `find-omnibus`, and `find-standard-gaps`.

The copied runtime closure is `_cpp/cpp_facts.py` plus
`_cpp/cpp_consumers.py`. Each skill owns only a thin C++ entrypoint. The
provider accepts first-party `.cpp`, `.cc`, and `.cxx` translation units only
when a current, complete Clang++ C++20 compilation database covers them.
Headers (`.h`, `.hpp`, `.hh`, `.hxx`, `.ipp`, `.inl`, `.tpp`) enter the
analysis only through Clang dependency output for an accepted translation
unit; unowned headers remain explicitly ambiguous.

## C++ identity retained

- Recursive Clang AST facts preserve namespace and declaring-class context.
- Overload leads retain their spelled function type, so two `Ledger::total`
  declarations do not collapse.
- Operator spellings and template declaration context are explicit fields.
- Header definitions are deduplicated by source site across translation-unit
  ASTs, rather than being counted as independent copies.
- Every final artifact carries the header-ownership boundary and states that
  ODR, ABI, template-instantiation selection, virtual/dynamic dispatch, macro
  meaning, and runtime behavior are not proven.

## Value proof

The representative C++20 fixture builds and tests natively, then runs a real
executable smoke (`cpp-cohort:10:6`). The nine consumers produce bounded final
artifacts for an overload-aware declaration explanation, strict glossary hit,
exact body-spelling clone, direct-sibling prefix cluster, resolved and orphan
ADR comment references, an eight-branch hotspot, an explicitly scouted
omnibus candidate, and a two-site/one-gap standard census. Tests copy each
skill and the `_cpp` provider closure under a host `.agents/skills` tree and
execute it from outside the repository.

## Verification and limits

- `tests/test_cpp_lexical_syntax_cohort.py`: 12 passed.
- Preserved `tests/test_find_comment_drift_cpp.py` and
  `tests/test_map_subsystem_cpp.py`: 23 passed.
- The separate frozen pilot runtime-manifest assertion is already stale at
  this branch baseline because its listed shared runtime files no longer
  match the frozen digest. This cohort does not edit that baseline or any of
  its listed files.

The provider is intentionally not a general C++ compiler platform. It uses
only the recorded Clang++ command snapshot, raw comment tokens, dependency
output, and recursive AST JSON needed by these nine read-only consumers.
