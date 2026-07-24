# Kotlin/JVM pinned semantic read-only learning packet

## Bounded compiler-helper probe

The direct probe was feasible on the observed local distribution. Kotlin/JVM
2.4.10 compiled a small helper against the shipped `kotlin-compiler.jar`, and
JDK 17 ran it over the selected manifest. `BindingContext` returned qualified
declaration identities and selected direct references/calls, including a
constructor (`kotlinpilot.Invoice.<init>`) and an extension call
(`kotlin.text.lowercase`). Compound PSI wrapper references remained unresolved
while their callee rows resolved, so the provider consumes only the narrower
callee fact.

The authority is deliberately pinned. The helper uses Kotlin's deprecated K1
compiler API after the same manifest passes the native Kotlin 2.4.10 K2 CLI
with warnings as errors. It is not a general Analysis API implementation.

## Provider gate

- Exact `kotlinc-jvm 2.4.10`, JDK 17, compiler-jar SHA-256, stdlib-jar
  SHA-256, and helper-source SHA-256 are required.
- A project-owned manifest selects unique lowercase `.kt` sources and tests.
  Every input digest and the complete manifest digest enter the fact pack.
- Production and test jars compile independently for JVM 17 with `-Werror`.
  A declared test main and smoke main must return the exact expected stdout.
- The helper is compiled with `-Werror`, run from a temporary directory, and
  accepted only with zero semantic ERROR diagnostics. Selected input hashes
  are checked again after the read.
- Output is atomic and constrained beneath `reports/kotlin-semantic`; all
  build jars are temporary. A copied `_kotlin-semantic` closure plus each thin
  consumer reaches the same final artifact paths.

## Five outcomes

| Skill | Supported bounded value | Final artifact | Still blocked |
|---|---|---|---|
| `find-dormant` | Private selected-source function with no resolved direct call/reference, excluding override, extension, and unresolved same-name boundaries; always review-required | `reports/find-dormant/kotlin/findings.json` | Runtime/framework reachability, callable references, reflection, safe deletion |
| `find-implicit-state` | `String` property named state/status/phase with at least two directly observed literal initializers/writes | `reports/find-implicit-state/kotlin/findings.json` | Closed-world state proof, delegated/custom setters, external/runtime writes |
| `find-incomplete-sweep` | One omitted defaulted constructor parameter among at least three resolved selected-source constructor calls where at least two supply it | `reports/find-incomplete-sweep/kotlin/manifest.json` | Migration trajectory, indirect factories, generated/alternate variants |
| `find-semantic-duplication` | Exactly two non-override/non-extension functions with matching static parameter/return/body spelling and distinct resolved production callers | `reports/semantic-duplication/kotlin/analysis.json` | Behavioral equivalence, side effects, consolidation safety |
| `rename-concept` | Exact source declarations plus resolved old/new reference inventories and unresolved-spelling deferral | `reports/rename-concept/kotlin/assessment.json` | Public binary/API compatibility, reflection/strings, Java callers, loaders, codemod safety |

## Explicit pending facts

Reflection, callable references, delegated properties, generated/KAPT/KSP
sources, compiler plugins, Gradle variants, Java sources, expect/actual,
Kotlin scripts, framework registration, and runtime reachability are not
provided. Resolved overloads retain the selected descriptor signature;
unresolved overloads remain unresolved. Override targets and extension
receivers are present only to exclude unsafe promotion. A compiler version,
jar hash, helper hash, manifest, native diagnostic, test, smoke, lifecycle, or
source-freshness mismatch produces `partial` and clears all claimed findings.
