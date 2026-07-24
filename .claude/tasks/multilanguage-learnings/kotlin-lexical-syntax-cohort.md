# Kotlin lexical/syntax cohort

Date: 2026-07-24
Provider: `.claude/skills/_kotlin/kotlin_facts.py`
Consumers: `adapt-project`, `explain-code`, `find-concept-divergence`,
`find-duplication`, `find-folder-topology-drift`, `audit-decisions`,
`find-complexity-hotspots`, `find-omnibus`, and `find-standard-gaps`

## Accepted boundary

The cohort accepts exact lowercase `.kt` Kotlin/JVM sources only. A strict
`kotlin-project.json` enumerates every eligible first-party source and test.
Tests, generated, vendor, build, tooling, unreadable, and symlink paths remain
visible inventory roles but do not enter source-syntax facts. `.kts`, Gradle
execution, Android, Multiplatform, Kotlin/JS, and Kotlin/Native are outside the
contract.

The provider uses `/opt/homebrew/bin/kotlinc` 2.4.10 with JVM target 17 for a
direct diagnostic compile. It validates the exact tools, commands, input and
output hashes, successful native test, and exact smoke output recorded in
`.native-build/kotlin-build-evidence.json`, then replays the recorded test and
smoke commands. Source bytes are fingerprinted before and after every run.

After the native gates, a Kotlin-local source tokenizer reports comments,
identifier tokens, directly spelled declarations and overload signatures,
data/sealed modifiers, extension-receiver spelling, function-body token
fingerprints, branch-keyword counts, and unresolved direct call spellings with
lexical `if` enclosure. It does not consume compiler IR and does not claim
resolved symbols, call targets, overrides, data flow, reflection behavior,
overload selection, extension dispatch, or runtime equivalence.

## Independent outcomes

Each thin consumer owns and replaces a distinct final artifact:

- `adapt-project` records the exact manifest/build boundary;
- `explain-code` renders overload-aware direct declaration spellings;
- `find-concept-divergence` reports one strict identifier-token drift per
  concept/file/term;
- `find-duplication` groups exact normalized function-body token clones;
- `find-folder-topology-drift` nominates direct-sibling filename-prefix
  clusters without authorizing moves;
- `audit-decisions` resolves decision IDs found only in source comments;
- `find-complexity-hotspots` reports advisory direct-body branch counts;
- `find-omnibus` requires explicit scout evidence before a source-name cluster
  becomes a final finding; and
- `find-standard-gaps` measures unresolved call-spelling/`if` syntax coverage.

The representative dependency-free fixture covers packages, a data class, a
sealed interface, nested data classes, an extension function, overloaded
functions, comments, branch syntax, duplicate bodies, filesystem clusters,
and role/foreign/script/symlink decoys. Its copied-closure test installs only
the selected skill plus `_kotlin`; the wrappers contain no repository-root
reference.

## Terminal behavior

Missing or too-old native tools produce `unsupported` without a clean claim.
An invalid manifest, compiler diagnostic, stale or malformed native evidence,
failed replay, or source mutation produces `failed` and exit 2. Consumers
delete prior artifacts before analysis and write a terminal artifact with no
old findings. The lifecycle fixture proves complete → failed → complete at the
same destination and exact source preservation throughout read-only runs.
