# C++ semantic read-only cohort

## Outcome

Five C++20 semantic jobs now reach useful, conservative final artifacts from a
single current and complete Clang compile-command snapshot:

- `find-dormant` reports only zero-direct-reference internal, non-template,
  non-operator functions as review leads. It never emits deletion authority.
- `find-implicit-state` reports exact resolved string-field writes as an
  `enum class` review lead while leaving constructors, aliases, callbacks,
  variants, storage, wire, layout, and ABI open.
- `find-incomplete-sweep` compares compiler-resolved C++20 designated aggregate
  returns and requires newer Git trajectory plus a content-bound human verdict.
- `find-semantic-duplication` emits static structural leads only when exact
  aggregate snippets and distinct direct caller contexts match. It never claims
  behavioral equivalence or safe consolidation.
- `rename-concept` is assessment-only: namespace-aware declarations and exact
  spellings are separated from macro/string residue and explicit ODR, ABI,
  linkage, overload, template, operator, ADL, and external-consumer review.

## Reusable boundary

C++ semantic analysis must key callable declarations by compiler identity
(mangled name plus resolved type where available), not spelling. Overload sets,
templates, operators, virtual dispatch, callbacks/function pointers, header
definitions observed in multiple translation units, and public-header symbols
remain explicit boundaries. A complete compile database still cannot prove all
specializations, variants, runtime targets, ODR safety, or ABI compatibility.

`.h` and `.inc` remain ambiguous unless the selected C++20 dependency closure
owns them. Generated, vendor, test, build, symlink, Objective-C++, CUDA, module,
and alternate-build inputs do not silently enter the claim.

## Verification shape

The representative fixture contains namespaces, anonymous-namespace linkage,
overloads, a function template and instantiations, an overloaded operator,
virtual dispatch, a callback registry, public-header aliases, designated
aggregates, and role decoys. Verification compiles every recorded translation
unit, builds and executes the native smoke, checks source preservation, rejects
tampered/stale/malformed/incomplete evidence, binds a sweep verdict to the
candidate hash, and runs every consumer from a copied script/provider closure.
