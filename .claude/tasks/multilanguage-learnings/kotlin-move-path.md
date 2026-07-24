# Kotlin/JVM `move-path` learning packet

Status: bounded implementation complete; publication remains root-owned

## Final value proved

One authored Kotlin/JVM implementation file can move to a different source
directory while retaining its filename, package declaration, source bytes,
and JVM identities. The representative transaction moves
`src/main/kotlin/kotlinpilot/Invoice.kt` to
`src/main/kotlin/kotlinpilot/billing/Invoice.kt`, keeps
`package kotlinpilot`, and changes only the matching `sources` string in the
existing exact `kotlin-project.json` manifest.

Dry-run validates the complete manifest-owned source/test set, Kotlin/JVM
2.4.10, JDK 17, direct test main, and exact smoke stdout. It compiles the
current tree, applies the two reviewed path changes in an isolated tree,
recompiles, reruns test/smoke, and requires byte-identical first-party class
entries, including `kotlinpilot/InvoiceKt.class`. This makes source-directory
location explicitly separate from package and file-facade identity for the
accepted shape.

`evidence.json` content-addresses the plan, standalone adapter, complete host
file/symlink tree, exact changes, selected tools, compiler-produced class
identities, native stdout, and expected after-tree. Apply requires the exact
evidence SHA-256, recomputes preview facts, performs the real move and one
manifest token edit, then reruns native and exact-tree checks. Check validates
the approved after-state. Any postflight failure restores the complete
pre-apply regular-file bytes/modes and symlink targets.

## Honest refusal boundary

This is a source-location move, not a Kotlin package, declaration, or ABI
refactor. It supports exactly one `.kt` implementation file below
`src/main/kotlin`, requires the same basename, and requires the source to be
an exact authored `sources` member of schema-v1 `kotlin-project.json`.

The adapter stops before writes for package/basename identity change,
`@file:` annotations (including `JvmName`/multifile ownership), `.kts`
scripts, generated/vendor/build paths, moved or manifest symlink boundaries,
incomplete/duplicate/stale manifest inputs, resources, active Gradle build
variants, reflection/class loading, path/stack inspection, serialization/DI
framework markers, any other old-source-path occurrence, unsupported tools,
missing or stale approval, compiler/test/smoke failure, class-byte drift, or
exact-tree drift. It does not claim package moves, public identity changes,
multifile facades, Android/Spring/plugin/framework behavior, arbitrary
Gradle/Maven/Bazel builds, resources, external consumers, JVM ABI
compatibility, or dynamic loading completeness.

## Reuse decision

The implementation is one stock-selected Python-standard-library adapter.
Copying only `kotlin_source_move.py` outside the checkout and invoking it with
isolated/no-site Python completes preview and approved apply against a copied
fixture. No generic mutation platform or cross-language adapter abstraction
was introduced.

The transferable lesson is narrow: for a same-package Kotlin source move,
unchanged basename plus unchanged package/source bytes preserves the expected
file facade, but the claim should still be compiler-proved. The exact build
manifest supplies complete input authority; direct `kotlinc` output supplies
class identity; executable test/smoke supplies behavior; everything dynamic
or variant-dependent remains a refusal.

## Verification and limits

The focused suite covers full preview/approve/apply/check, exact manifest and
source changes, package/source-byte preservation, compiler class-byte
identity, direct tests/smoke, eight uncertainty families, stale/missing
authority, exact rollback, and the copied single-file closure. The fixture is
the dependency-free Kotlin pilot using Kotlin/JVM 2.4.10 and JDK 17. The
standalone adapter is 977 lines / 36,922 bytes before final formatting.

Root alone owns capability/matrix/catalogue publication and any later
decision to broaden this cohort.
