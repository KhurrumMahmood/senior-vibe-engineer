# Java semantic relationships — bounded JDK 17 cohort

Evidence date: 2026-07-21. Implementation revisions: `0f6ffcb`
(`find-incomplete-sweep`), `38572fa` (`find-semantic-duplication`), and
`c7942fc` (`unify-shadows`).

## Outcome

Three selected skills now have honest Java 17 outcomes without Maven, Gradle,
downloaded JARs, or a shared Java platform:

| Skill | Accepted outcome |
|---|---|
| `find-incomplete-sweep` | A JDK compiler-resolved three-to-one record-constructor option divergence reaches the existing scout packet, fixed human verdict, and forgotten-first `triaged.md` only when every majority line is newer in Git. |
| `find-semantic-duplication` | Two directly called static methods that each return one canonical construction of the same project record become a conservative static lead with returned-component and direct-caller evidence. |
| `unify-shadows` | One complete accepted Java finding and capability matrix become a cited read-only proposal/evidence/scope bundle; no detection is rerun and human approval remains mandatory. |

Each executable is family-local. The producer detectors use the JDK compiler
tree/type APIs through bundled `.java` helpers and stdlib Python launchers. The
consumer is stdlib Python only because running a compiler there would violate
its consume-don't-redetect contract. Copied-install replays run Python with
`-I -S`, fingerprint their exact local runtime, compile fixtures natively with
JDK 17, and preserve every `.java` source hash.

## Precision boundaries

- Incomplete sweep supports only a project record whose one-argument-shorter
  constructor delegates to the canonical constructor with a literal default
  for the final component. Builders, setters, non-literals, multiple omissions,
  framework binding, and missing Git evidence do not become findings.
- Semantic duplication supports direct static methods with exactly one direct
  canonical record return and at least one resolved eligible-production caller.
  Instance methods, indirect returns, callerless methods, generated/test/vendor
  source, reflection, and dynamic/framework behavior remain unavailable.
- A `confirmed` semantic record means only that bounded static facts passed. It
  is never behavioral equivalence, workflow identity, or refactor authority.
- The proposal consumer validates current members, direct callers, matrix rows,
  accepted status, and fingerprints. It still requires a full reference and
  behavioral review before any implementation authorization.

## Verification

- All three Java cohort suites: 12 passed. Preserved incomplete-sweep behavior
  also passed in eight Go and six TypeScript tests; their two updated metadata
  assertions passed in a focused recheck.
- Semantic producer cohort: 13 passed across Java, Go, TypeScript, and retained
  Python coverage.
- Proposal consumer: 14 passed across Java+Go and 13 passed for TypeScript.
- Ruff, `git diff --check`, and the full commit hook set passed for all three
  implementation commits. Every `SKILL.md` remains below 500 lines.

## Reuse decision and limitation

Keep the Java implementations family-local. The compiler mechanics differ in
candidate shape, and the proposal consumer must not acquire detector machinery.
There is no demonstrated second consumer for a shared Java runtime, so a common
platform would add installation and abstraction cost without improving these
accepted outcomes.

The honest remaining limitation is source-only compilation: hosts that require
external dependencies or generated build classpaths can fail with unavailable
type facts. Supporting such hosts later requires a bounded host-provided
classpath contract; it does not justify Maven/Gradle/JAR/network integration in
this cohort.
