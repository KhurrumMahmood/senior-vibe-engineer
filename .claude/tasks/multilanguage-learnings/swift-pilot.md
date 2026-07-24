# Swift P7 pilot and full-publication closeout

## Current publication outcome

Swift now reaches 22 of 22 bounded language-level outcomes under Apple Swift
6.3.3. The original three pilot outcomes remain valid. Nine project/lexical and
syntax outcomes use their established family-local evidence; five read-only
semantic outcomes use the reproducible `swiftc -typecheck -dump-ast`
`swift-semantic-facts-v2` boundary; accepted evidence feeds enum, guard,
boundary, folder, and shadow proposals without redetection. Nineteen outcomes
require the external on-demand library, including the declared sibling
`_swift-semantic-readonly` helpers. `find-omnibus`, `map-subsystem`, and
`move-path` retain their stock-selected-install closures.

The supported claim remains selected and static. Conditional compilation,
macros/plugins, generated inputs, reflection, Objective-C/dynamic or protocol
runtime dispatch, external callers, Xcode projects/workspaces, Apple
frameworks, resources, arbitrary dependencies, mixed-language targets,
behavior, ABI/release compatibility, and broader mutation authority are not
established.

## Historical pilot outcome (superseded)

## Outcome

The dependency-free SwiftPM pilot supports three representative final outcomes:

- `find-omnibus`: bounded compiler-AST syntax report;
- `map-subsystem`: SwiftPM/build/SourceKit/symbol-graph project map; and
- `move-path`: one target-directory move that retains module identity.

At the time of the initial pilot, the other 19 language-level skills remained
explicitly `swift-unsupported`. That stop decision was later superseded by the
full-language pending-work rule and the accepted compiler-AST cohorts. Detailed
pilot evidence lives in
`swift-find-omnibus.md`, `swift-map-subsystem.md`, and `swift-move-path.md`.

## Setup and tools

The current Command Line Tools installation provides Swift/SwiftPM/`swiftc`
6.3.3 and `sourcekit-lsp`. That is enough for the accepted dependency-free
SwiftPM fixture, compiler AST, restrictive build, executable smoke, index, and
symbol-graph boundaries. The pilot installs nothing and performs no dependency
resolution or network access.

SwiftSyntax, native XCTest/Testing modules under the active developer
directory, and full Xcode project/framework behavior are unavailable. Optional
SwiftLint, Periphery, SourceKitten, and full-Xcode work remain tracked in the
language-toolchain dependency register rather than silently becoming product
requirements.

## Reusable lessons

- Reuse terminal states, lifecycle replacement, source fingerprints, copied
  closure proof, and native final-output verification across languages.
- Keep compiler output parsing fail-closed and local to the language family.
- Treat process exit as necessary but insufficient when a tool can report
  mixed target outcomes; inspect every selected target.
- Reuse the preview/authority/rollback vocabulary for mutations, but do not
  generalize SwiftPM manifest edits into a universal project model.
- Separate source-role inventory from semantic completeness. Seeing every
  `.swift` file does not prove resolved references, calls, or framework behavior.

## Limits and framework follow-ups

The accepted outcomes do not cover dependencies, Xcode projects/workspaces,
schemes, Apple frameworks, resources, macros/plugins, mixed-language targets,
conditional-compilation completeness, reflection, or dynamic dispatch. Those
need explicit framework/tool profiles and representative hosts before any
router claim. Full Xcode should be evaluated only when a user-valued outcome
requires it.

## Economics and decision

Each cohort produced a correct bounded result, but the copied closures are
large: `find-omnibus` 126,627 bytes, `move-path` 206,776 bytes, and
`map-subsystem` 234,637 bytes. Syntax grew 25.35% over its frozen closure;
mutation is 11.3% larger than the PHP comparison closure; the semantic map adds
851 adapter/test lines and takes about 404 seconds for five focused native
tests. These results do not justify a new shared abstraction or broad Swift
conversion now. Retain the three useful family-local outcomes and stop after
the pilot.

## Guidance for the next language

Start C and C++ as separate compile-database-gated profiles. Freeze one small
native fixture and three representative final outcomes before adding shared
code. Require a trustworthy `compile_commands.json`; do not infer build flags
from extensions. Reuse the acceptance questions above, run native cohorts in
isolated worktrees, and integrate shared router/matrix truth serially.
