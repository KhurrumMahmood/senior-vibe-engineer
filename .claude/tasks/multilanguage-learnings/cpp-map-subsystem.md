# C++ map-subsystem transfer notes

## Outcome and fact boundary

The useful semantic unit is one exact, current, complete C++20 compile-command
snapshot. Clang++ dependency output owns header/include facts; Clang JSON AST
owns namespace-qualified declarations, overload signatures, template
declarations, and direct declaration/member references; clangd independently
proves that every translation unit used the compilation database. Make's
read-only database adds project-local target prerequisites without pretending
that compile commands describe link targets.

This produced a useful map for a realistic library plus app: two selected
library translation units, an external app translation unit for inbound
references, public/private/template headers, overloaded methods, a class
template and function template, virtual policy boundary, static library and
executable target relationships, a native test, and generated/vendor/build/C
and orphan-header decoys.

## What transferred

- The C map's fail-closed compilation-database shape transferred: exact keys,
  exact eligible-TU coverage, one current language mode, the gated compiler
  executable, compiler dependency replay, no clangd fallback, atomic terminal
  artifacts, and before/after source fingerprints.
- The Java map's rule transferred: semantic facts exist only after native
  attribution succeeds; unresolved compiler runs do not leave a lexical map.
- The Go/Java copied-layout rule transferred: the selected skill uses only its
  family-local helper, Python's standard library, and host-owned native tools.
- Separate coverage and cleanliness states matter. `complete` is not a synonym
  for `clean`; the JSON/Markdown record `status` and `diagnostic_state`
  independently.
- Final artifacts need replayable freshness, not only generation-time source
  equality. Canonical JSON-payload, Markdown, and source-snapshot hashes make a
  later `--verify-artifacts` run reject tampering or source drift.

## What did not transfer cleanly

- C's flat top-level declaration walk is not sufficient. C++ requires nested
  namespace/class scope, access changes, out-of-line definitions linked through
  prior declarations, overload signatures, and suppression of compiler-created
  template specialization noise.
- Compile commands describe object compilation, not the library/executable
  graph. A bounded Make database query was necessary for target relationships;
  this fact tier is explicitly unavailable for non-Make hosts in v1.
- AST references are direct static references, not a call graph. Member and
  declaration IDs license overload-aware edges, but virtual dispatch,
  reflection/runtime registration, macro branches, and the open set of
  template instantiations remain unavailable.
- Public surface cannot be inferred from filename alone. It combines
  compiler-owned `include/` headers, nested access, declaration kind, qualified
  identity, and signature-aware deduplication.

## Size and smallest-responsible-fix assessment

At implementation closeout, `map_cpp.py` is 719 maintained lines / 38,290
bytes. The C++ knowledge file is 58 lines / 3,253 bytes. The entire existing
selected `map-subsystem` directory copied by the conformance test is 16 files /
377,313 bytes; the C++-specific runtime files plus the shared `SKILL.md` are
about 71 KiB. The isolated fixture is 14 files / 6,544 bytes; its compact
Makefile still materializes a complete three-translation-unit database and
native library/executable/test graph.

The 719-line mapper is the smallest responsible implementation **within this
lane's ownership and compatibility constraints**, but it is not an ideal final
minimum. Roughly the first third repeats proven C-family lifecycle mechanics
(atomic writes, path/tool validation, compile-database parsing, dependency
replay, freshness, clangd attribution). Extracting those now would require
changing the established C mapper and its copied closure, outside this lane's
safe surface, while a direct import from `map_c.py` would couple C++ behavior to
C-only suffix/mode/limitation rules. The retained C++-specific bulk is
load-bearing: nested AST attribution/reference identity, templates/overloads,
build graph, artifact verification, terminal rendering, and explicit semantic
boundaries. Dead constants were removed and template-instantiation/local-
variable noise was filtered rather than accepted as useful surface.

The reusable seam is a small copied-safe C-family lifecycle module containing
only atomic artifact I/O, containment/symlink checks, tool/version execution,
compile-command argument sanitation, manifest hashing, and terminal-state
writing. Promote it only when C and C++ can migrate together with their full
family regressions. Do not share suffix classification, language-mode gates,
AST schemas, declaration/public-surface rules, or semantic completeness claims.

## Guidance for the next native semantic language

1. Prove the native metadata gate before parsing symbols; missing/stale/
   incomplete project metadata must terminate before semantic analysis.
2. Analyze the complete project graph when inbound references are a claimed
   output, even if the durable map selects only one subsystem.
3. Preserve native identity in the artifact: qualified name plus overload/type
   signature, not display name alone.
4. Treat build graph and source graph as different fact providers and name the
   unavailable boundary when the host build system cannot be queried.
5. Add a post-generation verifier keyed to source and artifact hashes; a clean
   generation transcript does not prove an artifact is still current.
6. Measure the copied closure and maintained adapter together. Share lifecycle
   code only after two consumers migrate without normalizing away language
   semantics or weakening terminal states.
