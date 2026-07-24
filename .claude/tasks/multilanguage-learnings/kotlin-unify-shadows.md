# Kotlin/JVM accepted shadow proposal

`unify-shadows` consumes the existing pinned Kotlin semantic fact pack and
accepted `find-semantic-duplication` artifact. It does not run detection. One
content-addressed reviewer acceptance selects a single lead and one of four
dispositions: keep separate with rationale, share utilities, complete a
migration, or merge at the workflow boundary.

The consumer revalidates exactly two production definitions by fully rendered
signature, source location, and normalized body hash. It then requires the
producer's caller rows to equal the pinned resolved calls and requires the two
definitions to have distinct production callers. The output is always
read-only: `proposal.md`, `evidence.json`, and `scope.json` preserve the exact
definitions, callers, current source hashes, acceptance, and native test/smoke
baseline.

Acceptance must explicitly exclude overload ambiguity, reflection/callable
references, delegates, generated/KAPT/KSP sources, Gradle variants, and
Java/external callers. Runtime and behavioral equivalence remain unestablished,
JVM ABI approval remains separate, and none of the proposal shapes grants
source-mutation authority. `keep_separate_document_why` is a complete durable
outcome rather than a failed consolidation.

The focused test runs a copied one-helper/one-script closure through proposal,
keep-separate, refusal, and recovery at one destination. It proves stale source
rejection, exact artifact replacement, source preservation, and retention of
the pinned Kotlin native test/smoke results. No shared parser, detector,
mutation platform, or publication surface was added.
