# Swift `find-omnibus` compiler cohort learning

Status: bounded cohort evidence for root integration; no router, matrix, or
22-skill coverage claim is published by this lane

## Final outcome earned

The copied `find-omnibus` closure now reaches its existing detector JSONL,
candidate JSONL, Markdown report, and `findings.json` boundary for a narrow
SwiftPM-only Swift source selection. The provider uses only successful Swift
6+ `swiftc -typecheck` and `swiftc -dump-ast` facts. A positive disposable
copy of `tests/fixtures/swift-pilot` reports one four-domain candidate, while
the unchanged `BillingCore.swift` reports `clean-within-complete` inside a
`complete` run.

The terminal contract is explicit:

- `complete`: every eligible source independently typechecked and its compiler
  AST matched the bounded declaration grammar; zero findings may then be
  `clean-within-complete`;
- `partial`: compiler parsing succeeded but standalone typechecking did not,
  so useful facts remain visible without a clean or project-complete claim;
- `unsupported`: the Swift compiler is missing/older than 6.0, `Package.swift`
  is absent, the target is unsafe, or no eligible source exists; and
- `failed`: version execution, compiler execution/timeout, malformed syntax,
  source reads, or unrecognized compiler AST evidence failed concretely.

## Native tool and setup evidence

- Platform: macOS arm64, active Command Line Tools developer directory.
- Tool: `/usr/bin/swiftc`, Apple Swift 6.3.3; required floor 6.0.0.
- Acquisition: none. No package, SwiftSyntax dependency, network access, or
  machine/project tool installation was attempted.
- Native proof: the positive disposable `BillingCore.swift` passes
  `/usr/bin/swiftc -typecheck` before the skill pipeline runs.
- Process boundary: every compiler subprocess has a 30-second timeout; the
  copied helper invocation has a 120-second outer timeout.

## Exact closure, LOC, and timing

At the lane base, the complete `find-omnibus` skill tree contained 9 files and
101,015 bytes. This cohort adds one closure file; the candidate copied tree is
10 files and 126,627 bytes, a 25,612-byte / 25.35% increase. The copied-closure
test compares every relative file and SHA-256 digest before running under
isolated/no-site Python.

Maintained implementation delta before this packet is 646 net lines: the new
Swift helper is 307 lines; `detect.py` is +307/-4; and language-neutral report
status rendering is +46/-10. Focused outcome coverage is 435 lines. The closure
growth is material, so this is family-local evidence, not a reason to promote a
new shared provider or universal compiler schema.

Focused Swift verification completed 6 tests in 4.59 seconds of pytest time
(4.91 seconds wall, 3.30 user, 1.10 system). The slowest cases were lifecycle
transitions at 1.41 seconds, positive-plus-clean at 1.21 seconds, partial role
inventory at 0.89 seconds, and copied closure at 0.61 seconds.

## Boundaries proved

- Positive and clean reports preserve source bytes and carry SHA-256 source
  fingerprints into `scan.json`/`findings.json`.
- `Clock`, `FixedClock`, `Invoice`, `InvoiceFormatter`, and `InvoiceService`
  are present as compiler-derived nominal declarations; the disposable
  positive addition contributes the repeated domain methods needed by the
  existing omnibus threshold.
- Tests, generated source, vendor source, `.build` source, source-file
  symlinks, and a directory symlink are excluded without traversal.
- A parse-valid file whose module import cannot typecheck independently makes
  the final result partial. A syntactically malformed file makes it failed.
- Missing and old compilers reach unsupported final reports rather than clean
  empty results.
- Valid-to-failed and failed-to-valid reruns at one destination remove stale
  candidates, scouts, reports, and findings before writing the next terminal
  evidence.

## Facts that did not generalize

Compiler `-dump-ast` is textual and version-coupled. The helper accepts only a
small validated grammar for top-level protocol/struct/class/enum/actor
declarations and their direct functions/initializers. Unknown AST shape fails;
it is never treated as an empty successful result. These records are compiler
AST facts, not SwiftSyntax nodes.

Standalone typechecking is deliberately weaker than a SwiftPM build graph.
This cohort does not resolve references, imports, overloads, protocols,
extensions, conditional compilation, macros, reflection, dynamic dispatch, or
cross-target semantics. It does not support Xcode projects/workspaces, Apple
framework/app lifecycle, Objective-C/C-family mixing, resources, plugins, or
remote dependencies. Those need separate project-semantic evidence and must
not be inferred from this syntax cohort.

## Reusable guidance

For a compiler-backed syntax lane, first require successful typecheck for every
fact-bearing source, then parse only a fail-closed compiler output subset. A
separate compiler parse pass can distinguish malformed syntax from a
parse-valid source whose standalone typecheck lacks project context; this is a
useful complete/partial/failed boundary without pretending diagnostics are
resolved semantic facts. Always carry that terminal status through the
skill-owned final report, because candidate count alone cannot distinguish a
clean run from missing evidence.

For the next language, keep inventory/tool/lifecycle evidence adjacent to the
consumer, copy the exact closure, fingerprint sources, and prove both
same-destination transitions. Promote shared mechanics only after a second
real consumer shows the same contract and the measured closure/LOC economics
pass; this Swift slice does not pass that promotion argument by itself.
