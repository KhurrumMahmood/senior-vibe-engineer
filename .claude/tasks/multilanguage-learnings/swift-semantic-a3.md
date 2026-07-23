# Swift A3 semantic read-only family learning packet

Status: pending and unpublished. No shared skill prose, router, matrix,
catalogue, ledger, profile, or dispatch claim is changed by this lane.

## Cold-run reproducibility correction

The earlier accepted result below is historical warm-run evidence, not a
publishable support claim. With the repository-local Python runtime, a cold
provider run exceeded 360 seconds and a one-query run remained blocked in the
first `textDocument/documentSymbol` request after 137 seconds. A minimal
protocol probe showed that SourceKit-LSP initialized in 0.6--0.9 seconds and
advertised all required capabilities, but neither document-symbol nor
definition returned while the process remained alive and idle. Successfully
running `sourcekit-lsp debug index` over every fixture source in 23.64 seconds,
forcing the SwiftPM workspace type, and waiting 30 seconds after initialize did
not change the first-request timeout.

The original provider compounded that tool failure: each file received an
independent 60-second document-symbol timeout, failures were caught and the
loop continued, and shutdown added another 10 seconds. The archived candidate
now applies one 12-second LSP wall-clock budget, an 8-second per-request cap,
hard file/query/occurrence/request scope limits, a one-second shutdown cap,
and immediate partial termination on the first failed request. A focused fake
client regression proves that a first-file timeout cannot multiply across
subsequent files and that excessive occurrence scope is rejected before an LSP
process starts.

No responsible stable-SourceKit repair was found on this Command Line Tools
environment. This A3 family must remain unpublished until stable requests are
reproducible across cold and repeated runs. The sections below record what the
earlier successful cohort appeared to establish; they do not override this
correction.

## Final outcomes earned

One copied Swift-local semantic fact pack now supports five final, skill-owned
read-only outcomes for a dependency-free SwiftPM target:

- `find-dormant` emits review-required private/fileprivate top-level function
  leads only after every same-named occurrence is resolved to the selected
  declaration; reflection/string-like spellings defer the lead and no output
  ever claims certain deletion.
- `find-implicit-state` emits direct `String` state-field literal operations,
  excludes typed and serialization/wire owners, and promotes nothing without
  a candidate-SHA-bound accepted human review.
- `find-incomplete-sweep` emits one direct top-level defaulted labeled-argument
  omission shape only when at least three uniform present sites, one missing
  site, a 75% majority, and newer Git history all agree. Scout/triage verdicts
  bind the packet SHA and stale terminal Markdown is removed on invalidation.
- `find-semantic-duplication` compares matching constructor-backed return
  shapes, SourceKit-resolved constructor/callee identities, and distinct
  resolved production callers. Lexical clones, direct wrappers, return-shape
  mismatches, and policy-callee mismatches remain rejected or uncertain; a
  candidate-SHA-bound human verdict is required before a capability matrix is
  written.
- `rename-concept` is assessment-only. It identifies the old/new type authority
  through SourceKit definition and prepare-rename evidence, separates exact
  resolved identifier occurrences from comments, strings, homonyms, and
  excluded roles, and applies no source mutation.

The positive disposable host reaches exactly one intended lead in each
candidate-producing workflow: `dormantDiscount`, `Job.state`, `charge`'s
`audit` argument, and `buildStatement` / `summarizeInvoice`; the rename
assessment resolves `LegacyStatus` and `CanonicalStatus`. The clean target
reaches complete empty outcomes for all five consumers.

## Semantic and native contract

The shared fact pack freezes package hash, Swift tools version, selected target
name/type/path/sources, target-graph hash, debug/release configuration, query
plan, source manifest, and toolchain identity. It uses the host Command Line
Tools only:

- `/usr/bin/swift` and `/usr/bin/swiftc`, Apple Swift 6.3.3, with a required
  floor of 6.0.0;
- `/usr/bin/sourcekit-lsp`, whose executable content hash is bound because this
  CLT binary has no supported version command; and
- `/Library/Developer/CommandLineTools/usr/bin/swift-format`.

No network, dependency acquisition, SwiftSyntax package, plugin, or machine
installation was attempted. SwiftPM receives isolated cache, configuration,
security, and scratch paths plus disabled dependency cache, netrc, keychain,
prefetch, automatic resolution, and an explicit fresh index store. Declared
dependencies, target settings/resources, unknown target shapes, non-fresh
state, missing selected source, or unsafe selected symlinks stop the contract.

Every complete pack proves, in order, `dump-package`, `describe`, restrictive
build/index, fresh units for every selected source, compiler parse, strict
Swift format lint, exact check executable output `swift-a3-checks-ok`, exact
smoke output `swift-a3:42`, and stable LSP document-symbol, definition,
reference, hover, prepare-rename, and call-hierarchy requests. Source bytes and
the whole non-artifact source manifest must remain unchanged.

SourceKit-LSP advertised every required stable capability but returned neither
compiler USRs nor useful call-hierarchy items for this fixture. The cohort did
not invent USRs. Instead, each lexical occurrence must resolve through
`textDocument/definition` to one canonical internal declaration location; a
content-bound `sourcekit-definition:<sha256>` identifier names that equivalent
semantic identity. This distinction is part of the output limits and is the
portable lesson from the preflight.

## Degraded, lifecycle, and copied-closure proof

Focused tests cover missing SourceKit, old Swift, version-valid build failure,
malformed tool JSON, zero-exit missing index, non-fresh state, malformed
SwiftPM configuration, malformed fact JSON, clean/deferred outcomes, generated
and test decoys, a copied vendor library, string/comment/reflection decoys, and
exact native check/smoke results. Partial evidence is never relabeled clean;
concrete build/parse/config failures remain failed.

The positive test copies only the provider and seven Swift-named consumers to
an on-demand tree outside the checkout and executes them with isolated/no-site
Python. No copied runtime contains a checkout path. Candidate and packet hash
mismatches fail before promotion. Modified or newly added sources invalidate a
fact pack; restoring the exact source manifest permits a fresh consumer run.
Valid -> invalid -> valid transitions remove stale capability matrices and
sweep triage artifacts. Final source fingerprints equal the pre-run manifest.

## Exact closure and ML-025 economics

The copied runtime closure contains 8 files, 132,985 bytes, 3,336 physical LOC
(3,130 nonblank), with manifest SHA-256
`ba9b883423d65aa4a835886a98ceaf59f5780e7d938afdd2d8dcbe99d0cc9fee`.
The manifest hash uses sorted skill-relative paths followed by
`path + NUL + content_sha256 + LF`.

| Surface | Files | Bytes | Physical / nonblank LOC |
|---|---:|---:|---:|
| Shared Swift semantic provider | 1 | 49,487 | 1,223 / 1,141 |
| Seven workflow consumers | 7 | 83,498 | 2,113 / 1,989 |
| Final-outcome test | 1 | 27,525 | 828 / 777 |
| SwiftPM fixture | 15 | 4,703 | 214 / 173 |

Under the focused test's maintained-LOC model, five literal providers would
cost 9,056 LOC versus 4,164 LOC for one provider plus consumers/tests: 4,892
LOC saved, or 54.02%. The required alternating-order, three-trial serial native
benchmark measured:

- union pack: 38.661, 28.441, and 26.351 seconds; median 28.441 seconds;
- five separate packs: 131.886, 133.067, and 169.440 seconds; median 133.067
  seconds; and
- median latency saving: 78.63%.

This clears ML-025's >=25% maintenance saving and <=10% latency-growth gates.
It justifies this one Swift-local union pack because package identity, native
preflight, index freshness, role inventory, source preservation, and stable LSP
facts are identical for all five consumers. Candidate selection, terminal
status, output schemas, reviews, and lifecycle artifacts remain consumer-owned.

## Verification evidence

- Final focused non-slow suite: 4 passed, 1 deselected in 60.68 seconds.
- Focused three-trial latency proof: 1 passed in 527.94 seconds; exact economics
  above.
- Preserved Swift pilot, project-lexical A1, syntax A2, `find-omnibus`,
  `map-subsystem`, and `move-path`: 109 passed; one pre-existing A1 aggregate
  timing assertion missed after 36 minutes of sustained native load (12.25%
  aggregate growth while median growth was 3.05%). Its unchanged isolated
  replay passed in 281.47 seconds with 1.61% aggregate and 2.19% median growth.
- Python byte compilation, Ruff lint, and Ruff format check pass for the
  provider, seven consumers, and focused test. Fixture `Sources/` passes strict
  native `swift-format` through every complete provider run.

## Honest limits and reusable guidance

This is one selected dependency-free SwiftPM library/executable target in one
debug or release configuration. It does not expand conditional compilation,
macros, plugins, generated code, reflection, Objective-C/dynamic dispatch,
selectors, protocol/existential runtime dispatch, overload behavior, runtime
reachability, side effects, deletion safety, behavioral equivalence, or
refactor safety. Xcode projects/workspaces/schemes, Apple frameworks,
resources, package dependencies, mixed-language targets, and Unicode
identifier queries remain outside the contract. Native XCTest/Testing is not
available under the active CLT, so fixture-owned exact check and smoke
executables are mandatory.

For another semantic language cohort, probe the real compiler/LSP protocol
before choosing an identity model. An advertised reference or call-hierarchy
capability is not evidence that a particular declaration receives a USR or
edge. A stable definition request can supply an honest equivalent identity,
but only when every promoted occurrence resolves to the same content-bound
declaration and all unresolved/dynamic surfaces remain deferred. Share native
facts only after measured maintenance and latency economics pass; never share
consumer verdicts or inflate a location identity into whole-program semantics.
