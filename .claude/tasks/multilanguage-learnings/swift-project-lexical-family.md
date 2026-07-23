# Swift A1 project/lexical family handoff

Base revision: `febc76141feed564de628bde6d99f20f85191ebb`

## Outcome and disposition recommendations

Six independent copied consumers reach their existing final artifact boundaries
over a dependency-free SwiftPM fixture. The accepted facts are project and
lexical evidence only: they do not establish resolved symbol identity,
cross-module semantics, framework ownership, runtime behavior, or safe mutation.

| Skill | Proved value | Final artifacts | Recommended disposition |
|---|---|---|---|
| `adapt-project` | Inventories nine authored Swift files and all observed source roles, records the restrictive native obligations, and describes objective SwiftPM layout without endorsing it as a standard. | `adapter.yml`, `adapter.json`, `report.md`, `evidence.json` | `swift-supported` for objective dependency-free SwiftPM project/layout facts |
| `explain-code` | Explains direct public declarations whose selected files pass compiler parsing, with exact declaration spans and explicit unresolved-semantic annotations. | requested Markdown plus `targets.json`, `scan.json`, `unexplained.txt`, `surprises.txt` | `swift-supported` for direct compiler-validated lexical declaration explanations |
| `find-comment-drift` | Reports a comment's adjacent literal percentage when it contradicts the directly adjacent fixed multiplier. | `detections.jsonl`, `scan.json`, `findings.json`, `report.md` | `swift-supported` only for the bounded adjacent percentage-contradiction rule |
| `find-concept-divergence` | Reports an avoid-term from the supplied glossary at exact lexical occurrences in authored source. | `detections.jsonl`, `scan.json`, `findings.json`, `report.md` | `swift-supported` for strict glossary-backed lexical evidence |
| `find-duplication` | Reports identical normalized direct function bodies of at least five source lines, while explicitly refusing semantic-equivalence or consolidation claims. | `collapsed.json`, `ranked.json`, `triage.md`, `findings.json`, `scan.json` | `swift-supported` for exact normalized direct-body clone evidence |
| `find-folder-topology-drift` | Reports a CamelCase or snake-case filename-prefix cluster of at least three direct siblings and honors the explicit allow-folder boundary. | `detections.jsonl`, `scan.json`, `findings.json`, `report.md` | `swift-supported` for direct-sibling filename topology evidence |

The comment-drift row deliberately stops at one meaningful bounded rule. It
does not infer which declaration a distant comment describes, restate comment
prose semantically, or compare documentation with runtime behavior.

## Shared Swift project-facts contract

`.claude/skills/_swift-project-lexical/swift_project_facts.py` owns only the
identical Swift A1 facts and mechanics used by the six consumers:

- Swift, Swift compiler, and Swift Format path/version preflight;
- restrictive SwiftPM `dump-package`, `describe`, and external-scratch build;
- per-file `swiftc -frontend -parse` and strict recursive Swift Format lint;
- direct executable check and exact smoke-output verification;
- complete Swift-file role inventory and configuration/source fingerprints;
- source and host-state preservation, atomic final writes, stale-artifact
  clearing, symlink/report-path refusal, and terminal status; and
- a Swift lexical masker for ordinary/raw/multiline strings and nested comments,
  plus direct declaration/function-body spans.

Every invocation is self-contained. There is no cache, daemon, network request,
dependency resolution, or hidden persisted snapshot. The provider does not
publish a generic profile, shared matrix, router, or cross-language schema.
Consumer-specific interpretation and final schemas remain in each adapter.

Status is `complete`, `partial`, or `failed`; there is no unsupported-success
state. Missing `Package.swift` is partial project evidence. Missing or old tools
produce a partial final artifact and exit 2; version-command failure, native
command failure, and malformed selected source produce a failed final artifact
and exit 1. A later successful invocation at the same destination replaces the
degraded artifacts rather than inheriting stale findings.

## ML-025 economics

Physical maintained adapter-plus-test LOC is:

- shared producer `H`: 848 physical / 767 nonblank lines, 32,558 bytes;
- six skill adapters plus the focused test `C`: 1,621 physical / 1,481
  nonblank lines;
- shared design `C + H`: 2,469 physical / 2,248 nonblank lines;
- duplicated design `C + 6H`: 6,709 physical / 6,083 nonblank lines; and
- deleted maintenance `5H`: 4,240 physical lines, a **63.20%** reduction
  (63.04% nonblank).

This clears ML-025's 25% maintenance gate. The copied external closure for a
consumer still contains exactly one provider and one adapter, identical in
bytes to putting that provider in the consumer's scripts directory, so sharing
adds 0% per-consumer closure size.

The required real native latency replay alternated shared and literal copied
closures across all six consumers for 12 invocations, including repeated
restrictive SwiftPM build/static/direct-check/smoke work:

| Metric | Literal | Shared | Growth |
|---|---:|---:|---:|
| Aggregate wall time | 143.7597 s | 137.2097 s | -4.56% |
| Median consumer wall time | 24.2840 s | 23.1689 s | -4.59% |

Both measurements are below the +10% cap. The result justifies this Swift-local
seam; it does not justify a universal project-facts provider.

## Fixture, roles, and exact provenance

The fixture has 19 regular files, 2,616 bytes, manifest
`1dad07dc3eeaa0c9c79a22aec959cc430d1697c3147362c1172e93eca4abb4b0`
using sorted `path + NUL + file_sha256 + LF` rows. It contains a restrictive
SwiftPM host, seven `BillingCore` sources, separate direct-check and smoke
executables, a glossary, one malformed selected source, and a runtime-created
external symlink.

Positive evidence covers the authored source role. Must-not-fire coverage
preserves and excludes tests, executable products, generated headers/trees,
vendor, `.build`, `build`, reports, malformed unselected input, and symlinks.
Clean coverage includes preferred-only glossary use, no adjacent percentage
contradiction, below-threshold clones and filename clusters, an allowed folder,
and a target without reportable declarations. The host source/configuration
manifest is identical before and after every consumer.

Minimal copied executable closure manifests are:

| Consumer | Files | Bytes | Manifest |
|---|---:|---:|---|
| shared provider | 1 | 32,558 | `9c6edda99bb1617df5d504c565394655846c4206411070fcc98d5cf62ec92532` |
| `adapt-project` | 2 | 36,820 | `f2bd14cdd9dd9748bc00e3bc769bbd5a5e62740af1140a5a3fc71329add4c24b` |
| `explain-code` | 2 | 38,272 | `a366d84a5aa0fef16cb1927c51222e41d68031d51234fec2d8e8347ac4b768ef` |
| `find-comment-drift` | 2 | 38,412 | `bd71e99f20b0455c7ce024ba45c92625262eb25b8027b120efd499ee26df9f8a` |
| `find-concept-divergence` | 2 | 42,018 | `72a45a6cc632ecc79b1d4a687ab54942b0224eec028365fbe046ef1775b08ee8` |
| `find-duplication` | 2 | 38,632 | `8f5a8eee10c6f8e9236fd50fdb55958221c485fb5686508a8a45e75de8762248` |
| `find-folder-topology-drift` | 2 | 37,984 | `58c35112b89fe6bbf59bfad3e832ca3e9201890a2a5a9f1a663a0caee9373407` |

These rows hash the provider under `_swift-project-lexical/` and the adapter
under `scripts/`, relative to the copied selected-skill closure. Root must
recompute whole-skill closure hashes after its required `SKILL.md` edits.

## Native proof and semantic limits

The frozen tools are Apple Swift 6.3.3 (`/usr/bin/swift` and
`/usr/bin/swiftc`) and Command Line Tools Swift Format 6.3.0. No install,
update, dependency resolution, or network access occurred. The representative
fixture passes:

- restrictive external-state `swift build`;
- `swiftc -frontend -parse` independently for every eligible source;
- `swift-format lint --strict --recursive Sources`;
- direct executable check with exact output `swift-lexical-checks-ok`; and
- executable smoke with exact output `swift-lexical:42`.

The active Command Line Tools environment cannot provide the fixture a native
XCTest or Swift Testing module. The direct executable is a bounded substitute
for this fixture only, is reported separately, and is not mislabeled as a
formal test. A successful build/parse/format/direct/smoke matrix does not
resolve overloads, extensions across files/modules, protocol conformances,
macros, generated declarations, conditional compilation semantics, operator
meaning, dynamic dispatch, reflection, framework conventions, SwiftUI view
identity, or runtime equivalence. No SwiftSyntax dependency or resolved-symbol
provider is used. None of these read-only outcomes authorizes a rename, move,
consolidation, or other source mutation.

## Verification evidence

Focused evidence before the final consolidated replay:

- positive six-consumer copied outcomes: 1 passed in 140.02 s;
- clean and below-threshold outcomes: 1 passed in 139.96 s;
- tool/source-role and shared-contract matrix: 25 passed in 17.18 s;
- malformed selected source: 6 passed in 131.24 s;
- missing `Package.swift` partial outcome: 6 passed in 1.71 s;
- six valid -> failed -> valid same-destination lifecycles: 6 passed in
  280.89 s; and
- real alternating ML-025 latency replay: 1 passed in 281.64 s.

The focused test also exercises raw and multiline strings, nested comments,
copied external closure import, source/config preservation, stale final
replacement, and tool missing/old/version-failed/command-failed states.
An adversarial regression proves that a bodyless protocol method requirement
followed by a non-function declaration cannot absorb the later declaration's
body into comment-drift or duplicate-body evidence. Targeted Ruff and the
independent fixture native commands passed.

One preserved-spine aggregate attempt stopped after `1 failed, 10 passed in
39.82s`: the only observed failure is a frozen-runtime closure hash already
stale at the exact required base (`7e793b...` recorded versus `d6abf8...`
actual). None of that closure's six files changed in this lane. This is a
root-owned baseline/reference repair, not permission for this lane to edit the
forbidden baseline. Final consolidated replay results are recorded in the
handoff commit message/status. Root subsequently repaired that pre-existing
baseline on its own branch, so this lane remained unchanged as required.

The final post-adversarial consolidated replay covered the entire focused A1
module plus preserved Swift spine, `find-omnibus`, and `move-path`: **71 passed,
1 intentionally deselected in 1102.00s**. The deselected case was only the
base-stale manifest assertion that root had already repaired separately. The
post-fix replay includes a fresh successful ML-025 threshold check.

## Root publication instructions

1. Copy `_swift-project-lexical/swift_project_facts.py` beside every selected
   A1 consumer. Treat the sibling as external-library-only closure: a stock
   individually installed skill must not advertise Swift until the sibling is
   included.
2. Update exactly the six shared `SKILL.md` files with the copied Swift command,
   final artifacts/statuses, role exclusions, native obligations, stale
   lifecycle, and the limits above. Preserve all existing language commands.
3. Change exactly the six accepted Swift coverage rows from pending to the
   recommended `swift-supported` dispositions, citing this packet and the
   integrated revision. Do not broaden comment drift or describe lexical
   evidence as semantic identity.
4. Regenerate the root-owned coverage/matrix/router/catalog projections and
   installed-closure manifests only after the skill contracts are edited.
   Recompute whole selected-skill closure hashes then; the minimal executable
   hashes above are the frozen lane inputs.
5. Replay every copied consumer from outside the repository through positive,
   clean, degraded, and valid -> failed -> valid cases. Rerun preserved Swift
   `find-omnibus`, `map-subsystem`, and `move-path` evidence plus the spine.
6. Repair or explicitly adjudicate the pre-existing frozen Swift spine closure
   hash drift at root. Do not silently bless it from this feature lane.
7. Update the execution ledger A1 row only after commands, coverage,
   projections, copied closure, and verification agree at one root commit.
8. Preserve the three previously supported Swift outcomes. Do not fold later
   syntax, semantic, mutation, or framework cohorts into this A1 provider.
