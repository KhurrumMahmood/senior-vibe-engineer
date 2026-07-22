# Java J4C state-maintenance learning packet

## Outcome

Java 17 now has one bounded, review-first chain across
`find-implicit-state`, `extract-enum`, and `prevent-regression`:

1. The detector uses the JDK compiler tree/type APIs to identify one direct,
   top-level `java.lang.String` field by qualified owner and field name.
2. The extractor consumes one complete accepted finding and its source
   fingerprint, then emits a read-only enum proposal and caller table.
3. The guard stages an exact-authority rule, copied compiler helper, native
   bad/good fixtures, and host-wiring guidance. It never installs host wiring.

The supported host prerequisite is only `java` and `javac` at JDK 17 or newer.
There is no Maven, Gradle, JAR, network download, or repository-wide Java
platform.

## What transfers from Go and TypeScript

- Compiler-resolved identity is evidence of *which field*, not proof that its
  business domain is finite.
- The artifact handoff is one-way: the proposal consumes final detector output
  and the guard consumes the accepted authority; neither re-detects as a
  substitute for review.
- A copied closure is a real product boundary. The guard copies the family
  helper beside its staged rule and fails with exit 2 if the selected
  `find-implicit-state` closure is absent.
- Discovery requires repeated evidence; after human approval, the exact guard
  rejects a single newly introduced bare literal.

## Java-specific contract

The detector promotes only a compiler-attributed direct String field named
`state`, `status`, or `phase` after three direct safe operations with at least
two distinct literals. Direct assignment, `String.equals`, and
`Objects.equals` are supported. `==` and `!=` are emitted as separate
correctness findings and never count as enum evidence.

The staged guard identifies only the accepted `qualified_owner + field`, not
all same-named fields. It recognizes those same direct operations plus unsafe
reference equality while the field is still String. A post-migration enum
fixture and an unrelated `OtherJob.status` prove it becomes clean without a
broad-name false positive.

## Evidence

`tests/test_java_state_chain.py` replays copied skill directories against
native Java before/after fixture hosts. It proves final JSONL/JSON/Markdown
artifacts, generated/test/vendor/low-evidence boundaries, malformed source,
missing and old JDK failures, source fingerprints, proposal refusal of unsafe
or stale evidence, staged-only guard output, native `javac --release 17 -proc:none`
fixture compilation, exact historical guard hits, and clean
post-migration output.

At handoff, the focused Java test has 4 passing tests. Existing state-family
compatibility checks remain green: Go has 5 passing tests and TypeScript has 2.

## Deliberate limits

This is not a general Java refactoring engine. It intentionally excludes
aliases, getters/setters, switches, dataflow, ORM converters, serializers,
reflection, nested owners, Kotlin, build profiles, and framework semantics.
Any compiler diagnostic or unresolved source produces partial/non-actionable
evidence rather than a clean result. The proposal remains `review_required`:
humans must decide persistence, wire values, serialization, migration, rollout,
and rollback.

## Reuse decision

Keep the JDK helper family-local. The only justified reuse is exact copying
from the selected detector closure into the staged guard; no second independent
Java family demonstrates a contract for a shared Java platform. Reconsider
only after another accepted Java workflow needs the same compiler-resolution
surface.
