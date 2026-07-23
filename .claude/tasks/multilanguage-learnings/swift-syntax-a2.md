# Swift A2 syntax-family learning and economics

Base revision: `98dff014d19aaa94c297d67b3f6f2ce444f41e4d`

## Outcome and dispositions

The frozen Swift A2 cohort contains exactly three new read-only consumers.
`find-omnibus` remains the separately implemented compiler-AST consumer and was
preserved, not reimplemented. Root still owns all `SKILL.md`, router, catalog,
coverage, matrix, projection, and release publication.

| Skill | Candidate disposition | Exact bounded outcome |
|---|---|---|
| `audit-decisions` | `swift-supported` for compiler-validated lexical comments | The existing `drift.md`, `raw-drift.json`, `registry-audit.json`, and `link-check.txt` retain real line/doc `decision:0001` references, resolve IDs only against the ADR registry, and surface orphan `decision:9999` plus the old unreferenced ADR. String and excluded-role references do not become evidence. |
| `find-complexity-hotspots` | `swift-supported`, advisory syntax lead | `detections.jsonl`, `findings.json`, `report.md`, `scan.json`, and `latest` report only `routeInvoice` at frozen direct-body token score 11. A branch-heavy closure, local function, protocol requirement, generated/test/vendor/build/report/symlink roles, and a below-threshold target remain clean. |
| `find-standard-gaps` | `swift-supported` for one declared condition | `coverage.json`, `coverage.md`, and `scan.json` report three direct spelled `parseInvoice` sites, two lexically inside `do` bodies followed by `catch`, one gap, and 66.67% coverage. Receiver calls, tear-offs, strings, declarations, nested closures, and excluded roles do not become sites. |

These are final skill outcomes, not a generic “Swift parsed” claim. Audit answers
registry integrity, complexity supplies a measure-first lead, and standards
measures one host-declared syntactic baseline. The shared producer publishes no
skill verdict.

## Reuse decision and interface depth

The completed A1 sibling `.claude/skills/_swift-project-lexical` is the genuine
ownership boundary for A2. The three consumers require the same dependency-free
SwiftPM source inventory, tool preflight, native gates, lexical masks, exact
fingerprints, preservation proof, terminal lifecycle, direct declaration/body
spans, and external copied layout. A separate A2 provider would duplicate that
policy; a cross-language AST would erase Swift-specific syntax and native
boundaries.

A2 adds only language-local facts to that producer:

- direct functions/methods that are not nested in another function body;
- direct-body `if`, `guard`, `for`, `while`, `repeat`, `case`, `catch`, `&&`,
  and `||` token spans and hashes;
- nested callable/declaration brace masking so closures and local functions do
  not inflate their owner;
- direct unqualified call spellings, containing function, exact span/hash, and
  lexical membership in a `do { ... }` body followed by `catch`; and
- explicit `syntax_only`, `call_identity_claimed: false`,
  `runtime_cost_claimed: false`, and `refactor_authority: false` boundaries.

Deletion is fail-closed. A copied selected skill without the sibling producer
writes a `partial/swift-fact-producer-missing` final artifact and exits 2. None
of the three adapters carries a fallback lexer, SwiftPM command matrix, tool
version logic, source-role rules, or function-body matcher. Consumer-specific
ADR interpretation, hotspot threshold/report, standards JSON validation,
coverage calculation, artifact schema, and exit semantics remain local.

## Native and source boundary

Each invocation independently runs the existing A1 native matrix:

1. Swift, `swiftc`, and Swift Format >= 6.0 preflight;
2. restrictive `swift package dump-package` and JSON `describe` with dependency
   resolution/prefetching/keychain/netrc disabled and all state external;
3. external-scratch `swift build` with index-store production;
4. `swiftc -frontend -parse` once per eligible file, never combining the two
   executable `main.swift` files;
5. `swift-format lint --strict --recursive Sources`;
6. the built `swift-a2-check` executable with exact stdout
   `swift-a2-checks-ok`; and
7. the built `swift-a2-smoke` executable with exact stdout `swift-a2:42`.

The dependency-free fixture has a library, a below-threshold library, and two
executable targets. XCTest/Testing remains unavailable under the active Command
Line Tools, so the direct executable owns the fixture's native oracle. Passing
native commands validate this fixture/package boundary only; they do not prove
runtime behavior in another target, package, framework, or Xcode project.

The inventory analyzes only selected, declared, authored SwiftPM source.
Configuration, tests/fixtures, generated trees/markers, vendor, `.build`/build,
reports, non-source roots, and symlinks are inventoried but excluded. Source and
`Package.swift` hashes are checked after the native matrix. Every positive,
clean, malformed, copied, lifecycle, and preserved-A1 path leaves host source
bytes unchanged.

## Artifact lifecycle and failure states

All three adapters delete their prior artifact set before analysis, atomically
write complete/partial/failed replacements, and pass valid -> failed -> valid
at one destination. Old references, findings, and scanned coverage rows cannot
survive a failed rerun.

Tool and input states are explicit for every consumer:

- missing Swift and Swift 5.10 are `partial` with exit 2;
- failed or unrecognized version output is `failed` with exit 1;
- a version-valid Swift wrapper whose package command fails is `failed` with
  exit 1;
- malformed selected Swift is `failed` after native build/parse evidence and
  remains byte-preserved; and
- invalid standards JSON is `failed/invalid-standards` before tool probing and
  replaces prior coverage.

A clean complete audit has no drift after `0002` replaces the orphan reference.
A clean complexity target emits no findings. Moving the uncovered call into a
second direct `do`/`catch` yields three sites, zero gaps, and 100% coverage.
Incomplete evidence never becomes a clean result.

## ML-025 economics

Physical maintained adapter-plus-test LOC at this revision is:

- shared Swift producer `H`: 991 physical / 896 nonblank lines, 38,149 bytes;
- three adapters plus the focused A2 test `C`: 1,380 physical / 1,223
  nonblank lines, 49,186 bytes;
- shared design `C + H`: 2,371 physical / 2,119 nonblank lines; and
- literal per-skill ownership `C + 3H`: 4,353 physical / 3,911 nonblank lines.

Sharing removes 1,982 physical lines, a **45.53%** reduction (45.82% nonblank),
clearing ML-025's 25% maintenance gate. A selected consumer still carries one
adapter plus exactly one producer copy, so moving that identical producer from
the consumer's `scripts/` directory to the sibling `_swift-project-lexical`
directory adds **0%** copied-closure bytes. The installed three-skill union
stores the producer once: 440,072 bytes rather than the 520,900-byte sum of
three literal closures, a 15.52% reduction.

The final alternating real native replay compared shared and literal copied
closures across all three consumers:

| Metric | Literal | Shared | Growth |
|---|---:|---:|---:|
| Aggregate wall time | 64.0342 s | 65.8342 s | +2.81% |
| Median consumer wall time | 21.5435 s | 21.3810 s | -0.75% |

Both are inside the +10% cap. This justifies the existing Swift-local seam. It
does not justify request-level caching or batching; every consumer still runs
its own content-fresh native matrix.

## Exact copied closures and fixture

Hashes use sorted repository-relative `path + NUL + file-SHA-256 + LF` rows and
exclude `__pycache__`/`.pyc` development artifacts.

| Closure | Files | Bytes | Manifest SHA-256 |
|---|---:|---:|---|
| `audit-decisions` + `_swift-project-lexical` | 10 | 140,158 | `56f1785510e7cf6c49022b9005500e186d019d2d4910265ce7356191aeb00936` |
| `find-complexity-hotspots` + `_swift-project-lexical` | 16 | 162,350 | `f996b9075dd634c52823507876880c5ca830a70ffa4a7d780165ac06050f33e8` |
| `find-standard-gaps` + `_swift-project-lexical` | 15 | 218,392 | `0d26433d26cdb80c61ad9efdccbaf040dab98599b47573b4a699d871664c2d70` |
| three-skill union + one producer | 37 | 440,072 | `5e0e4a7ee162fb673574c13b695f3e2cdb8188a7b726842474bab1acac6ac7e5` |

The four runtime files (producer plus three adapters) are 65,723 bytes with
manifest `4a4b5d056a6cf3b50dd2586281a9a1d73f628ad00d3e84518662858dc913272f`.
The A2 fixture is 16 files, 243 physical / 220 nonblank lines, 5,436 bytes,
manifest `a8ec64d8280dd1822b94f1efc9b0725098270534766a29bbcdf770e1410efda6`.

Each selected skill plus sibling provider was copied under
`.agents/skills/`, invoked with isolated Python from a working directory
outside both source checkout and host, and reached its real final artifacts.
No installed closure embeds the source checkout path.

## Tools and verification

- Python: explicitly supplied product virtualenv, 3.11.10.
- Swift / `swiftc`: `/usr/bin`, 6.3.3.
- Swift Format: Command Line Tools, 6.3.0.
- Tools installed or updated: none.
- Network/dependency acquisition: none; the fixture is dependency-free and
  automatic resolution/prefetching are disabled.

Focused A2 verification is split to avoid redundant concurrent Swift builds:

- 20 fast tool/deletion/regression/economics cases passed in 9.78s;
- 12 serial final-outcome, clean, lifecycle, malformed, invalid, and copied
  cases passed in 424.02s;
- the post-cleanup copied-closure replay passed 3 cases in 63.77s; and
- the final alternating ML-025 replay passed in 130.10s.

Preserved Swift verification passed the six-consumer A1 final outcome plus its
raw-string/nested-comment and bodyless-protocol regressions (3 tests in
131.03s). The unchanged independent `find-omnibus` Swift suite passed 6 tests
in 4.73s. Ruff, `py_compile`, strict Swift Format, final artifact assertions,
host-source fingerprints, restrictive SwiftPM/compiler checks, direct check,
and executable smoke are clean. Unrelated slow native language families and
the redundant full Swift A1 lifecycle/latency suite were intentionally not run.

## Explicit limitations

- The provider is a compiler-validated lexical/delimiter parser, not
  SwiftSyntax or SourceKit semantic indexing.
- A direct call spelling does not establish callee/import/alias/receiver/type,
  overload, protocol witness, extension, dispatch, or cross-target identity.
- `do` followed by `catch` is lexical enclosure evidence only; it does not
  establish throw propagation, reachability, handler equivalence, or runtime
  protection.
- Complexity is a frozen direct-body token count. It is not cyclomatic/CFG
  complexity, cognitive cost, runtime frequency/cost, equivalence, or refactor
  authority. Nested callable/declaration brace bodies are excluded.
- Audit resolves the numeric token against the ADR registry only; it does not
  establish that the ADR applies to the declaration, target, or runtime path.
- Conditional-compilation projection, macros/plugins, reflection, dynamic
  dispatch, dependencies, workspaces, Xcode projects, Apple frameworks,
  Objective-C/C-family interop, resources, and SwiftUI behavior are outside A2.
- The standards consumer supports only direct unqualified spelling plus
  `enclosed_by: "do-catch"`; it is not a general Swift lint replacement.

## Root integration instructions

Root should integrate this commit serially and then:

1. Add Swift commands and exact bounded descriptions to only
   `audit-decisions`, `find-complexity-hotspots`, and `find-standard-gaps`.
   Preserve their distinct artifacts and exit semantics.
2. Include sibling `.agents/skills/_swift-project-lexical` whenever any of the
   three Swift adapters is projected into the external on-demand library.
   Consumer-only installation must remain partial, never silently clean.
3. Publish Swift support for exactly these A2 rows in language coverage,
   catalog, matrix, and execution ledger. Preserve the existing independent
   `find-omnibus` Swift disposition and implementation.
4. Keep the simple three-router ambient installation unchanged except for the
   normal external-library closure projection; do not add caching, batching,
   framework/Xcode claims, or UX/performance work in this publication.
5. Recompute whole selected-skill projection manifests after root's required
   `SKILL.md` edits, then replay the copied commands from outside repository and
   host, the focused A2 suite, preserved A1/omnibus checks, metadata/host guards,
   and router/catalog/projection tests.
