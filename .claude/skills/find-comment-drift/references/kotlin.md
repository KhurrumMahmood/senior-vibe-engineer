# Kotlin comment-drift provider

Use this provider only for manifest-selected authored `.kt` comments. Keep the
sibling `_kotlin`, read [`../../_kotlin/GUIDE.md`](../../_kotlin/GUIDE.md), and
enter through `scripts/analyze_comments_kotlin.py`.

The provider emits four lexical hygiene bands with exact comment spans and
final advisory/clean artifacts. It does not associate comments with
declarations or prove semantic/runtime drift. Strings, tests,
generated/vendor/build/tooling/symlink inputs, `.kts`, Java, annotations,
plugins, Gradle variants, reflection, frameworks, and behavior remain outside
the claim.
