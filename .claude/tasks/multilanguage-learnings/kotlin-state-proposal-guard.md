# Kotlin/JVM accepted state proposal and guard

## Bounded outcomes

`extract-enum` consumes the existing pinned Kotlin/JVM 2.4.10 semantic fact
pack, its `find-implicit-state` artifact, and a separately content-addressed
human acceptance. It selects one exact direct `String` property and emits a
read-only proposal containing the compiler-resolved declaration, every
accepted direct literal write, resolved reference and caller context, and a
wire-preserving enum draft. It never invokes the producer or mutates Kotlin.

The acceptance must close the state domain and approve the exact serialization
strings and JVM ABI change. It must also attest that Java and external callers,
framework registration, reflection, delegated properties, generated/KAPT/KSP
sources, Gradle variants, and overload ambiguity are absent for the selected
authority. An unknown or changed verdict is a refusal, not a partial proposal.

`prevent-regression` consumes the ready proposal plus a second accepted
migration artifact. It stages, but does not install, one project-owned Kotlin
compile-time assertion that the reviewed property retains the reviewed enum
type. The acceptance binds the complete migrated source/test inventory and the
exact edits that form the reviewed String-state reversion.

## Native proof and lifecycle

The representative migration changes only the fixture's state declaration,
three direct writes, test assertion, and smoke serialization. The verifier
uses the pinned compiler and JDK to prove:

1. the migrated source and tests compile with warnings as errors;
2. the exact native test and smoke output pass;
3. the staged type guard compiles against the migrated tree;
4. the human-accepted String reversion still compiles and passes the same
   native test/smoke without the guard; and
5. that buildable reversion fails compilation when the guard is present.

All migration and reversion work occurs in disposable copies. Source hashes
are checked before acceptance and after verification. The focused test runs
both consumers from a copied two-script plus one-helper closure, exercises
complete/refused/recovered replacement at the same destinations, rejects
stale source facts and proposal hashes, and confirms the host source tree is
unchanged by proposal and guard staging.

## Non-claims

The proposal does not establish runtime closure or behavioral equivalence.
The guard protects one property type only; it does not protect enum membership,
wire strings, serializer configuration, reflection names, delegated/custom
setter behavior, generated code, alternate Gradle/Android/Multiplatform
variants, Java/framework/external callers, or JVM binary compatibility. Those
remain human gates for implementation and release even when proposal drafting
and exact-type guard staging are accepted.

No shared Kotlin parser, detector, mutation platform, router, matrix, or skill
publication surface was added. The existing semantic producer remains the only
authority for declarations, writes, references, callers, and native baseline
evidence.
