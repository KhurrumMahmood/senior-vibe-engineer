# Swift `map-subsystem` P7 learning packet

## Accepted outcome

The Swift cohort earns one bounded, copied/on-demand map for a production
target in a dependency-free SwiftPM package. It writes the final Markdown and
JSON pair without changing manifest or source bytes:

- `.claude/docs/subsystems/<name>.md`
- `reports/map/<name>/swift-map.json`

The pilot maps `Sources/BillingCore`. SwiftPM `dump-package` and `describe`
establish the manifest, target membership, source lists, and declared target
dependencies. A restrictive full-package `swift build --enable-index-store`
must pass. A forced-clean `sourcekit-lsp debug index` must then show every
declared target preparing and every declared Swift source being indexed with
no target-level nonzero exit. Only after both boundaries pass does the compiler
symbol graph supply the selected target's public declarations.

The accepted fixture reports `Clock`, `FixedClock`, `Invoice`,
`InvoiceFormatter`, and `InvoiceService` plus their public members. It reports
`BillingCore -> SwiftPilotSmoke` only because the manifest declares the target
dependency, `main.swift` imports `BillingCore`, and the complete package build
and SourceKit index succeed. This is not a call graph or runtime-dispatch claim.

## Tool, closure, and lifecycle decision

Selected provider: `scripts/map_swift.py`, a single stdlib-only Python file
orchestrating host-owned `/usr/bin/swift` 6.0+ and `sourcekit-lsp`. It never
installs a package, invokes the network, imports SwiftSyntax, reads another
skill, or uses a private compiler API. SwiftPM receives isolated cache,
configuration, security, and scratch paths under the map report plus disabled
dependency cache, netrc, keychain, prefetch, and automatic resolution flags.
Packages with any declared dependency stop as unsupported before `describe` or
build, so the pilot does not test or resolve remote dependency availability.

SourceKit-LSP has no usable version probe in this toolchain. Availability alone
therefore earns nothing. The provider removes only `.build/index-build`, runs
the public `debug index --project` surface, parses target-level preparation and
index process results, verifies each manifest source appeared in an index
operation, and removes that disposable index artifact afterward. A zero
SourceKit process exit with one failed target writes `failed`, while a zero
exit without complete target evidence writes `partial`. This guards the mixed
success behavior observed in preflight.

Terminal Markdown and JSON are replaced atomically at the same destinations.
The focused test proves complete -> malformed/failed -> clean/complete
transitions, so an old successful map never survives a failed run. Missing or
old Swift, missing SourceKit, excluded targets, dependencies, unsafe symlinks,
and unsupported package shapes remain explicit. Source fingerprints cover the
manifest and non-artifact project files before and after native analysis.

## Honest semantic boundary

Supported facts are deliberately narrow:

- exact SwiftPM package/target/source/product membership from public manifest
  JSON;
- declared target dependency plus matching direct module import, licensed as a
  resolved target edge only after a successful complete build/index snapshot;
- compiler symbol-graph public declarations for the selected library target;
- source roles for production, test, generated, vendor, build, configuration,
  and symlink paths; and
- per-target SourceKit preparation/index completeness.

The provider does not claim SwiftSyntax, arbitrary reference identity, resolved
calls, types beyond compiler-public declarations, exhaustive conditional
branches, or whole-program runtime behavior. Conditional compilation, macros,
plugins, reflection, dynamic dispatch, Xcode projects/workspaces/schemes,
Apple frameworks, resources, arbitrary dependencies, generated-source
pipelines, and mixed-language targets are unsupported. Executable/test target
public-surface behavior is not generalized from the library pilot. If these
facts become necessary, stop or publish partial/unsupported rather than using
syntax-only evidence as resolved semantics.

## Native and copied-closure proof

The positive final map's own restrictive build produces
`debug/swift-pilot-smoke`; executing it prints
`invoice:INV-42:fixed-2026`. The focused suite also proves public-surface and
target-edge output, clean output, malformed Swift, generated/test/vendor/build
exclusions, malformed manifest, missing/old/limited tools, a zero-process-exit
failed target, dependency refusal, source/artifact symlink refusal, unsafe
artifact containment, stale transitions, source preservation, and a copied
single-file provider outside the checkout.

Measured after the provider and focused tests:

| Metric | Value |
|---|---:|
| Copied `map-subsystem` regular files | 12 |
| Copied closure bytes | 234,637 |
| Closure manifest SHA-256 | `f051c4295810cabbb41abdf4fd372171c8f4fc06b38118ab3d2188bcc80bbe1d` |
| Swift adapter physical / nonblank LOC | 560 / 499 |
| Swift final-outcome test physical / nonblank LOC | 291 / 251 |
| Adapter + test physical / nonblank LOC | 851 / 750 |
| First full focused run | 353.52 s; 4 passed, 1 failed from one renderer branch defect |
| Corrected failing-case replay | 43.67 s; 1 passed |
| Final focused run | 403.82 s; 5 passed |

The closure hash uses sorted regular-file paths relative to the selected skill,
then `path + NUL + content_sha256 + LF`; `__pycache__` is excluded. The copied
execution proof itself needs only `map_swift.py`, the external-library Python
runtime, and host-owned Swift/SourceKit executables. The whole-skill closure is
reported because that is what the on-demand skill selection copies.

## What generalized and what stayed Swift-local

Generalized mechanics are atomic paired final artifacts, explicit terminal
states, stale-output replacement, root-relative role classification, symlink
and artifact containment, source fingerprints, copied-closure replay, and
native final-output verification.

Swift-local mechanics are SwiftPM's manifest/target graph, restrictive flag
set, target import matching, SourceKit's misleading mixed-target process exit,
its `.build/index-build` lifecycle, and compiler symbol-graph shape. These do
not justify a shared semantic graph or universal symbol schema. A later
language should reuse the final-outcome questions, not these facts or parsers.

## Verification command

The lane uses the repository-owner supplied runtime explicitly:

```text
<product-repo>/.venv/bin/python \
  -m pytest -q tests/test_map_subsystem_swift.py
```

Preserved TypeScript, Go, Java, and PHP `map-subsystem` regressions are reserved
for the root coordinator's serial integration run so concurrent native lanes
do not contend for toolchain resources.
