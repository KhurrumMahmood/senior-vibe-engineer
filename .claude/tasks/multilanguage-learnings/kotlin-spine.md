# Kotlin/JVM spine learning packet

## Observed toolchain

- The local system provides Kotlin/JVM 2.4.10 through
  `/opt/homebrew/bin/kotlinc` and `/opt/homebrew/bin/kotlin`.
- The compiler runs on JDK 17.0.12, and `/usr/bin/java` reports the same
  runtime line.
- Gradle 7.5.1 is installed, but the local distribution does not establish a
  Kotlin 2.4 Gradle-plugin compatibility contract or a dependency cache. The
  spine therefore never invokes Gradle and never performs a restore.

## Source and build boundary

- Lowercase `.kt` is the only enabled suffix. Generic inventory keeps `.kts`
  visible as unsupported. The provider recognizes only `build.gradle.kts`
  and `settings.gradle.kts` as configuration context; neither enters a
  compile manifest.
- The copied fixture is dependency-free Kotlin/JVM. A stdlib-only Python
  helper receives absolute `kotlinc` and `java` paths, compiles application
  and test jars for JVM 17 with warnings as errors, runs the test main, and
  executes the application jar.
- Final evidence records exact canonical tools and commands, every compiled
  source/test digest, both jar digests, and terminal test/smoke results. The
  provider rejects missing, malformed, incomplete, wrong-tool, wrong-command,
  stale-input, changed-output, and failed-native-check evidence.

## Syntax and semantic feasibility

- Compiler success and diagnostics are a usable syntax/build boundary for the
  exact source manifest and configuration only.
- Inspection of the shipped `kotlin-compiler.jar` found internal
  `K2JVMCompiler`, `KotlinCoreEnvironment`, PSI (`KtFile`, `KtPsiFactory`),
  and `BindingContext` classes. The distribution ships no standalone Analysis API
  package or jar. CLI `-X` help exposes experimental backend IR dump controls,
  not a stable structured project-analysis contract.
- One direct probe compiled the fixture with `-Xdump-directory` before the
  `JvmUpgradeCallableReferences` backend phase. It emitted textual IR containing
  resolved types plus generated data-class members and fake overrides. The
  phase name, flag, textual format, and synthesis are experimental compiler
  internals rather than a portable structured API, so semantic-project facts
  remain unproven. No skill may claim symbols, resolved calls, overrides, data
  flow, reflection, generated sources, or alternate build variants from this
  spine.

## Transfer decision

Keep all 22 skill rows at `kotlin-pending-implementation`. Promote a row only
after a Kotlin-owned implementation reaches its final artifact, preserves the
copied source closure, and proves the appropriate native boundary. Direct
compiler feasibility is not a completed skill outcome.
