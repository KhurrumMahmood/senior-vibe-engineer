# Java v1: compiler-attributed dormant review

This is a bounded, read-only review branch, not a deletion engine.

## Evidence model

- Requires a full JDK 17+ and runs the copied `detect_java_dormant.java` source
  launcher with `JavacTask.parse()` then `analyze()`, `--release 17`,
  `-proc:none`, and an empty explicit classpath.
- It infers one conventional source root from a named package declaration and
  path, compiles every eligible Java source below that root, and calls
  `Trees.getElement` only after error-free attribution.
- It reports only selected, non-generated **private methods** whose resolved
  `MethodInvocationTree` and `MemberReferenceTree` use count is zero.
- A matching string literal is `uncertain`, never a review candidate. Every
  candidate is `review_required` / `human_review_only`; `certain_delete` is 0.

## Boundaries and terminal states

- Reflection, `MethodHandles`, `ServiceLoader`, DI, framework callbacks, JNI,
  external consumers, runtime dispatch, generated source, and Kotlin are not
  reachability proof. They remain visible uncertainty boundaries.
- Syntax errors exit 2 and preserve a prior good report. Unresolved Java
  compilation writes a final `partial` report with no semantic candidate facts.
- Missing targets, excluded test/vendor/build targets, symlinked source or
  report paths, default/mismatched packages, no source, old JDK, and missing
  compiler are explicit `unsupported` states when the launcher can run.
- Maven/Gradle, dependency classpaths, module paths, annotation processors,
  Kotlin attribution, and all build variants are intentionally unsupported.

The only writes are `reports/find-dormant/<scan>/findings.json` and
`report.md`; source is fingerprinted by tests and is never edited.
