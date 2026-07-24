# Kotlin/JVM comment and subsystem-map learning packet

## What generalized

- The existing project/lexical provider remains the authority for exact
  `kotlin-project.json` coverage, source roles, native test/smoke replay,
  terminal lifecycle, and source preservation. Comment drift consumes only its
  comment tokens; the map uses it as the complete current project gate.
- The pinned semantic provider can serve a second independent outcome without
  becoming a report schema. The map accepts qualified declarations and direct
  resolved calls/references only after both providers describe identical
  source/test paths and hashes.
- Same-destination replacement is part of both outcomes. Unsupported, failed,
  partial, clean, and findings states rewrite the final artifacts, so an old
  complete surface cannot survive a stale manifest, tool, helper, or source.

## What did not generalize

- Lexical comment tokens cannot associate prose with declarations or prove
  semantic or behavior drift. Kotlin comments therefore retain only the narrow
  stale-term, brittle-reference, banner, and narration advisory bands.
- Descriptor visibility is not an external API or JVM binary-compatibility
  model. The map separates `public`, `private`, and other Kotlin visibility and
  states that file facades and external consumers remain unresolved.
- Direct compiler-resolved rows are not a runtime call graph. Overrides,
  reflection, callable references, delegated properties, dynamic/framework
  registration, generated KAPT/KSP sources, compiler plugins, Gradle variants,
  Java callers, expect/actual, Android, and Multiplatform remain explicit limits.

## Tool and closure evidence

- Verified with the product `.venv` Python, Homebrew `kotlinc-jvm 2.4.10`, and
  JDK 17. The semantic gate requires the exact compiler jar, stdlib jar, and
  helper-source SHA-256 values frozen by `_kotlin-semantic`.
- The comment copied closure is the selected skill plus `_kotlin`. The map
  copied closure is the selected skill plus `_kotlin` and `_kotlin-semantic`.
  Neither consumer imports repository scripts, installs tools, runs Gradle, or
  accesses the network.
- The focused overlay reuses the Kotlin lexical fixture and adds one selected
  subpackage with public/private/internal declarations, direct intra/inter-
  package calls, lexical comment leads, quoted decoys, and excluded generated
  and vendor decoys.

## Guidance for the next language

Require a complete project/native gate before semantic mapping, preserve native
qualified identity and unresolved rows, and merge providers only when their
selected source universe and content hashes agree. Keep comment association,
runtime dispatch, public API compatibility, and build-variant completeness out
of a map unless a separate native fixture proves each claim.
