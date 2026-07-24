# C++ state proposal, guard, and shadow-unification cohort

## Outcomes

Three C++20 jobs now consume the compiler-backed semantic artifacts without
turning review evidence into source authority:

- `extract-enum` selects one exact namespace-qualified string field, renders a
  content-addressed `enum class` migration plan, and applies it only to a
  disposable project copy. The copied project must regenerate compile commands,
  pass native tests, and preserve executable smoke output. The host remains
  unchanged and ABI, ODR, storage, wire, external, and mutation approvals remain
  explicit gates.
- `prevent-regression` requires a fresh accepted-migration artifact, all five
  approvals, the exact proposal hash, and the exact migrated-source census. It
  stages a `std::is_same_v` guard beneath `reports/`, proves the guard accepts the
  current migrated project, and proves a disposable field-type regression is
  rejected. It does not install the guard into host source.
- `unify-shadows` binds one structural lead to the fact pack, analysis bytes,
  source census, compiler-resolved symbol identities and caller contexts. It
  renders a read-only option plus characterization checklist and stop conditions;
  matching structure is never promoted to behavioral equivalence.

## Reusable boundary

A successful disposable compile is compatibility evidence for the exact fixture,
not general C++ migration proof. Enum extraction can change layout, mangled names,
overload resolution, template specialization, serialization, RTTI, exceptions,
and external binary behavior. A type guard protects only the exact selected field
type. Shadow consolidation must stop on overload/template/operator/ADL/virtual or
callback ambiguity, and on any ODR, ABI, lifetime, side-effect, concurrency, or
undefined-behavior uncertainty.

## Verification shape

Focused tests cover positive native proposal and executable-smoke preservation,
tampered fact binding, atomic content-addressed bundles, source preservation,
accepted-migration and stale-source refusal, current-guard success, seeded
regression failure, and all three consumers from one copied helper/provider
closure. No new platform or dependency is introduced.
