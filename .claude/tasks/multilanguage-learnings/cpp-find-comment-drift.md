# C++ `/find-comment-drift` transfer notes

## What generalized

- The C cohort's Clang raw-token, exact-byte-span, atomic artifact, and
  compile-database ownership mechanics transfer directly when the selected
  language and standard remain explicit.
- Translation units are useful without compile commands only when their
  standalone syntax invocation succeeds. Headers stay ambiguous until a
  complete, current dependency closure proves ownership.
- The final artifact needs both per-source hashes and a deterministic manifest
  hash. A copied verifier makes those lineage claims reusable after the scan,
  rather than merely asserting that the analyzer did not mutate sources.
- Same-destination replacement must cover unavailable, failed, malformed, and
  incomplete provider states. Empty detections alone never establish clean.

## Native setup and reusable facts

- Verified on macOS with Apple Clang/clang++ 21 and Make; no dependency or
  network installation is part of the skill.
- C++20 compile commands accept standard and GNU standard spellings. Relevant
  translation-unit roles are `.cpp`, `.cc`, `.cxx`, `.c++`, `.C`, and `.ii`;
  header/template roles include `.h`, `.hpp`, `.hh`, `.hxx`, `.h++`, `.inc`,
  `.ipp`, `.inl`, and `.tpp`. Suffix matching stays case-sensitive so `.C`
  remains meaningful without silently accepting unrelated `.CPP` files.
- Clang raw comment locations plus preserved source bytes provide exact
  half-open spans and spelling hashes. A small C++ literal-aware byte scanner
  is used only to detect truncated compiler output; it never creates findings.
- The realistic fixture compiles and executes a C++20 program, inventories
  multiple source/header suffixes, and proves generated, vendor, build, test,
  foreign-language, and ambiguous-header boundaries.

## Size and reuse decision

At integration, the C++ analyzer is 729 physical lines / 30,826 bytes; the
analyzer plus its focused test is 1,111 lines / 44,762 bytes. The complete
selected `find-comment-drift` directory is 26 files / 282,080 bytes, while the
C++ runtime increment itself is the single 30,826-byte analyzer. This is a
substantial language-local implementation, not evidence that every future
lexical analyzer should be copied at the same size.

The analyzer deliberately leaves the proven C helper unchanged. Its reusable
seam is the same narrow C-family lifecycle noted by the C++ map cohort: atomic
artifacts, containment checks, tool/version execution, compile-database
freshness, and hashing. Extract that seam only in a joint C/C++ change with
both full regressions. Do not share suffix/mode rules, comment-token parsing,
header ownership claims, or completeness semantics merely to reduce LOC.

## What did not generalize and remaining limits

- C and C++ source suffixes, language modes, standards, and unsupported
  constructs cannot be collapsed into a language-neutral claim. The shared
  helper therefore has separately selected contracts and a dedicated copied
  C++ entry point.
- Raw tokens do not establish macro expansion meaning, active preprocessor
  branches, comment-to-symbol attachment, API documentation completeness, or
  semantic drift. Findings remain lexical review leads.
- Objective-C++, CUDA, C++ module interfaces, build-system-specific generated
  source conventions, and framework documentation rules are outside this
  cohort. Add them only with native fixtures and explicit provider facts.
- Compile database freshness uses owned dependency and Makefile mtimes; build
  systems with other authoritative configuration inputs may require a future
  profile-specific freshness adapter.
