# C pilot closeout

Status: stopped after a bounded two-skill pilot.

## Accepted capabilities

- `find-comment-drift`: Clang 21 raw-token lexical findings for `.c`/`.i`,
  with headers admitted only through a current, complete C17 compile-command
  dependency closure.
- `map-subsystem`: compiler-attributed translation units, owned headers,
  declarations, public surface, include dependencies, and shared-header edges
  for the exact current C17 compile-command snapshot.

The other 20 language-level skills remain explicitly `c-unsupported`.
`move-path` is not promoted merely because the semantic pilot makes one narrow
fixture experiment possible.

## Reusable lessons

1. A compile database is the project identity for C. File suffixes alone
   cannot establish header ownership, flags, variants, or dependency closure.
2. Lexical and semantic outcomes should share the compile-command gate while
   retaining separate providers. Clang raw tokens are appropriate for exact
   comment spans; compiler dependency output and AST JSON are appropriate for
   a bounded subsystem graph.
3. Headers are ambiguous by default. They become eligible only when a selected
   translation unit proves ownership through compiler dependency output.
4. Tool exit zero is insufficient. Freshness, completeness, C-mode flags,
   selected translation units, artifact replacement, and unchanged source
   fingerprints are part of the final outcome.
5. C and C++ need separate profiles and capability truth even when they reuse
   the same Clang installation.

## Economics and next-language guidance

The lexical copied closure grew 22.65% and the semantic closure is 262,371
bytes. These are useful language-local implementations, not evidence for a new
shared abstraction. The next C++ slice may reuse the compile-database contract
and fixture patterns, but must prove C++ mode, headers, standards, build facts,
and final artifacts independently.

Optional tools such as CMake, clang-tidy, clang-format, IWYU, cppcheck, or Bear
remain backlog inputs. They are not installation prerequisites for the two
published C outcomes.

## Evidence

- Spine: `.claude/tasks/multilanguage-learnings/c-spine.md`
- Lexical: `.claude/tasks/multilanguage-learnings/c-find-comment-drift.md`
- Semantic: `.claude/tasks/multilanguage-learnings/c-map-subsystem.md`
- Capability truth: `.claude/tasks/c-language-coverage.json`
