# Java J5 read-only proposal learning packet

Revisions: `c87d2ff` (`rename-concept`) and `be3ebc7`
(`propose-folder-reorganization`). Evidence date: 2026-07-21.

## Invariants that transferred

- Both skills remain read-only and emit final Markdown plus structured JSON.
- JDK compiler/tree/type evidence is authoritative only inside the explicitly
  supported Java boundary; lexical similarity never becomes a resolved fact.
- `java` and `javac` must come from `PATH` and be JDK 17 or newer. Missing or
  old tools produce honest terminal artifacts rather than false-clean output.
- Each copied skill carries its complete family-local runtime. No Maven,
  Gradle, JAR, network, language-server, annotation-processor, or shared Java
  platform dependency is required.
- Locked fixtures prove native `javac --release 17 -proc:none` compilation,
  source fingerprints before/after analysis, copied-skill replay, excluded
  tree handling, malformed input, ambiguous paths, and terminal artifacts.

## Family-specific authority

`rename-concept` grants rename authority only to compiler-resolved public
top-level Java types matching the requested old/new identity. It combines that
evidence with the installed `find-concept-divergence` strict-text scanner; the
coupled skill is an explicit copied dependency, not forked logic. Internal,
unresolved, string/reflection-like, generated, test, vendor, and build matches
remain blockers or deferrals rather than symbol evidence.

`propose-folder-reorganization` requires explicit human judgments that a
three-or-more-file prefix cluster should split and that the project permits
the resulting subpackage. The compiler enumerates package declarations,
imports, static imports, wildcard review, fully-qualified uses, and same-
package references that cross the proposed boundary. Package-private access,
excluded identity matches, symlinks, an existing destination, or unresolved
current-source-root compilation block the plan. No framework convention is
inferred.

## What did not generalize

- The two Java analyzers stay family-local. Their terminal facts differ:
  concept identity/lifecycle evidence versus a package move graph. Similar JDK
  launch, path, and JSON plumbing is not enough to justify coupling them.
- Rename evidence does not prove reflection, serialization names, framework
  metadata, dynamic loading, behavior, or non-public concept contracts.
- The folder proposal covers one conventional, internally resolvable current
  source root. It does not model external modules, extra source sets,
  dependency classpaths, build plugins, or framework/build-system conventions.
- Java support does not imply Kotlin, Groovy, Android, JPMS, or arbitrary JVM
  ecosystem support.

## Locked verification

- `rename-concept`: 4 Java tests; 16 Java/TypeScript/Go preserved-language
  tests; repository smoke 11 tests; focused metadata/taxonomy 16 tests; ruff,
  diff checks, and commit hooks passed.
- `propose-folder-reorganization`: 5 Java test groups and 21 total
  Java/TypeScript/Go preserved-language tests; ruff, diff checks, and commit
  hooks passed. Its `SKILL.md` is 499 lines.

The system `quick_validate.py` rejects this repository's intentional extended
frontmatter schema, so repository hooks are the applicable validator. The
broader `test_skill_detector_reads.py` still has six unrelated pre-existing
offenders; neither modified skill is one of them. These are validation-context
limitations, not waived Java failures.

## Next-language guidance

Start with the exact terminal claim a skill needs, use the host language's
native resolver for only that claim, and lock unsupported/ambiguous outcomes
before adding a positive path. Revisit shared JDK plumbing only after an
accepted maintenance case demonstrates lower total complexity while
preserving copied/on-demand closure and family-specific semantics.
