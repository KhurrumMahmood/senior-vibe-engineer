# C P7 spine learning packet

The bounded spine uses the installed Apple Clang/clangd 21 and GNU Make 3.81.
No package was installed and no network access was used. Required dependencies
are `clang`, `clangd`, and `make`; CMake, capture tools, clang-tidy, formatting,
IWYU, cppcheck, and framework/build-system adapters remain optional and absent.

The transferable mechanism is deliberately small: a strict `.c`/`.i` profile,
generic tool/marker doctor, generic role inventory, source preservation, and a
Make target that materializes absolute `arguments` entries after the fixture is
copied. A compile database is trustworthy only after content, C-mode,
completeness, copied-root, and freshness checks. File presence and clangd exit
zero are insufficient.

C-specific truth did not generalize into the shared inventory. `.h` and `.inc`
remain ambiguous until a trustworthy C compile command's dependency closure
owns them. Objective-C, C++, CUDA, OpenCL, and assembly are excluded. Macro
branches, file-local linkage, function pointers, ABI/layout, targets, sysroots,
defines, and include order remain semantic limits.

Next cohorts should run in order: `find-comment-drift` from version-gated raw
tokens and exact spans; `map-subsystem` only after rejecting missing,
malformed, stale, incomplete, non-C, and fallback databases; `move-path` only
after accepted semantic lineage, then with preview, bounded diff, rollback,
and native build/test. The spine earns no C skill support: all 22 dispositions
remain `c-unsupported`.
