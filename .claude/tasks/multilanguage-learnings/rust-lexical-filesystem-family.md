# Rust lexical/filesystem family learning

## Outcome and earned dispositions

Five independent read-only Rust consumers now reach their own final artifact
boundaries from copied/on-demand closures. Each uses the same accepted Rust
1.85+ source-role, tool, Cargo, syntax, manifest, and lifecycle contract while
retaining a consumer-owned interpretation and schema.

| Skill | Positive value proved | Final artifacts | Earned disposition |
|---|---|---|---|
| `adapt-project` | Counts four authored Rust modules, identifies Cargo, and emits locked/offline check/test/format commands without standardizing observed layout. | `adapter.yml`, `adapter.json`, `report.md`, `evidence.json` | `rust-supported` for objective Cargo/Rust adaptation facts |
| `explain-code` | Inventories and annotates direct public `Invoice`, `InvoiceState`, and `normalize_invoice` declarations while keeping a private alias out and a `pub use` re-export unexplained. | target-keyed explanation Markdown, `targets.json`, `scan.json`, per-symbol annotations, `unexplained.txt`, `surprises.txt` | `rust-supported` for direct lexical public declarations |
| `find-concept-divergence` | Finds the glossary avoid term `cancelled_order` in authored source with an exact span/hash while excluding generated, vendor, target, test, and symlink decoys. | `findings.jsonl`, `report.md`, `findings.json`, `scan.json` | `rust-supported` for glossary-backed strict-text Rust evidence |
| `find-duplication` | Finds exactly the two seven-line fixed-total functions with identical normalized bodies and excludes the behaviorally different function. | `collapsed.json`, `ranked.json`, `triage.md`, `findings.json`, `scan.json` | `rust-supported` for exact normalized function-body evidence |
| `find-folder-topology-drift` | Finds one three-file `billing_*` direct-sibling cluster while excluding `lib.rs` and all non-authored roles. | `detections.jsonl`, `report.md`, `findings.json`, `scan.json` | `rust-supported` for explicit-root filename clusters |

These dispositions are deliberately bounded. They do not imply semantic Rust,
safe consolidation, import-safe moves, macro-expanded declarations, or runtime
behavior.

## Shared fact contract

`.claude/skills/_rust/rust_lexical_facts.py` is the only shared implementation.
It owns facts and mechanics that all five consumers immediately use:

- full pre-eligibility `.rs` inventory with source, test, generated marker/tree,
  vendor, build/target, auxiliary example/bench, `build.rs` configuration, and
  symlink roles;
- Rust 1.85+ `rustc`/Cargo and rustfmt 1.8+ resolution/version evidence;
- `cargo metadata --format-version 1 --locked --offline --no-deps` and
  `cargo check --locked --offline --workspace --all-targets --all-features` with
  selected `RUSTC`, `CARGO_HOME`, and `CARGO_TARGET_DIR` outside audited source;
- per-selected-file rustfmt parsing without writes;
- Rust-aware masks for nested block comments, line comments, raw/byte/ordinary
  strings, character literals, and lifetimes;
- direct declaration/function spans, source/spelling/body hashes, content-derived
  source manifests, atomic writes, stale-artifact removal, preservation checks,
  and terminal return policy.

Consumers still own what those facts mean. Adaptation counts/commands,
explanation annotations, glossary bands, clone ranking/triage, and topology
thresholds do not enter the helper.

## Interface-depth and deletion evidence

Two designs were considered:

1. five standalone Rust scripts, each embedding role discovery, tool probes,
   Cargo state, manifests, lexical masks, and lifecycle; or
2. one Rust-only fact module plus five final-artifact consumers.

The second design passed the interface-depth checks:

- **Deletion test:** deleting the helper forces all five consumers to recover
  Cargo environment isolation, version/failure policy, source roles, manifest
  construction, syntax gates, and preservation checks. The focused test asserts
  that every consumer imports `collect_snapshot` and that none contains
  `CARGO_TARGET_DIR`, `cargo metadata`, `generated-marker`, or
  `auxiliary-target` policy.
- **Caller knowledge removed:** callers supply root, targets, and selected tool
  paths; they do not know role order, version thresholds, temporary native state,
  metadata/check commands, syntax parsing, status mapping, or source-manifest
  construction.
- **Test surface:** 17 focused tests exercise all five consumers through their
  copied public command and final artifacts. They do not call private helper
  functions.
- **Adapter reality:** five production consumers use the same snapshot contract.
  The variation is real and sits after fact production, not inside a hypothetical
  universal AST.
- **Decision:** the Rust-only module is deep enough to keep. A general
  cross-language provider or universal declaration schema remains rejected.

The helper lives under `_rust`, not `_common`. This preserves legacy skill
closure tests that intentionally prove their non-Rust commands have no common
runtime dependency. A Rust installed closure must copy both the selected skill
and `_rust/rust_lexical_facts.py` at sibling paths.

## Lifecycle and failure honesty

Every consumer is tested at the same destination through valid → missing tool →
valid recovery. Prior positive artifacts are removed before partial evidence is
published, and recovery replaces the partial state. Each consumer also proves:

- Cargo below 1.85 is `partial`, not `unsupported`;
- a missing required tool is `partial`, not `unsupported`;
- failed version/native metadata/check execution is `failed`;
- an unreferenced malformed selected `.rs` file is
  `partial`/incomplete while valid facts remain useful;
- source bytes are unchanged across positive and malformed runs; and
- a zero-finding partial/failed run never becomes a clean conclusion.

No Rust path emits `unsupported`. Missing implementation or host tooling is
pending/partial evidence, as required.

## Native verification and acquisition

No compiler/component/dependency was installed or updated, no network was used,
and no mutation was performed. Verification used:

- `/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python` <!-- # host-ref-allow: required frozen P7 runtime -->
  3.11.10 for the stdlib-only helper, adapters, Ruff, and pytest;
- `/Users/khurrummahmood/.local/bin/rustc` <!-- # host-ref-allow: required frozen P7 runtime -->
  1.97.1 and Cargo 1.97.1; and
- `/Users/khurrummahmood/.local/bin/rustfmt` <!-- # host-ref-allow: required frozen P7 runtime -->
  1.9.0-stable.

The fixture independently passes locked/offline Cargo metadata, check, and test
over the workspace/all targets/all features plus `cargo fmt --all -- --check`.
The focused Rust cohort passed 17 tests in 33.58 seconds. A positive-only replay
including the independent native suite and all five copied final outcomes passed
in 8.58 seconds. The first narrow family replay passed 119 tests and exposed two
packaging regressions; after moving the helper from `_common` to `_rust` and
removing generated bytecode, the two regressions plus all 17 focused tests passed
as 19/19. The final narrow replay across all five affected skill families passed
121 tests in 188.27 seconds.

## Exact closure economics

Closure manifests use sorted `path + NUL + file_sha256 + LF` rows. Every Rust
closure includes its complete existing skill directory plus the selected Rust
adapter and `_rust/rust_lexical_facts.py`.

| Skill | Base closure | Rust copied closure |
|---|---|---|
| `adapt-project` | 4 files, 47,739 bytes, `34f174730285a327bdcf6232530260d23f5886d4854fd2dc1128cc5179a8ac7e` | 6 files, 76,140 bytes, `ac42dfdd5e9e08640c64f9cb20ec43001c6f0aaf20356d4f8b69db505ea0c39b` |
| `explain-code` | 7 files, 129,147 bytes, `d173340f48b1f4d06537fb7cfdd64b90ca25a5866a1628adecf3c96e641e6000` | 9 files, 159,345 bytes, `fd8af26e75a89a982aae8ed739cba6ba7bb4e7fbab4e8775ae973c7928e060cd` |
| `find-concept-divergence` | 3 files, 54,471 bytes, `c53bdcf8ba083181f4280b8dc7fbbe068c33925c7da24813d683209231312108` | 5 files, 89,324 bytes, `ff3f96f8d7d87cf80324f4eaf9889db8829b3b75db47f125e8ad622edbdb2943` |
| `find-duplication` | 18 files, 178,704 bytes, `223abad15cf2a508600c50848e08e2218a2ab70fbcdff32ea7fbd96b306c79ef` | 20 files, 209,173 bytes, `057be1c9dd2193ea1c161c55606135e27418f7a76c00e21ae5478d2d33920637` |
| `find-folder-topology-drift` | 5 files, 78,462 bytes, `a45b9c6666628bd6de235cc85e6083f168a7ddca6d6c1d3932b79dc43d8c0aed` | 7 files, 107,719 bytes, `e114201ff4cfe1e13aaa103414c0f3e16d95d4205d5aedab978131526e550d74` |

The maintained helper is 696 physical/629 nonblank lines. Consumer wrappers are
832 physical lines total, and the shared focused test is 390 lines. Current
adapter-plus-test cost is therefore 1,918 physical lines. Literal helper
duplication across five consumers would be 4,702 lines; sharing deletes 2,784
maintained lines, a measured **59.21% reduction**, well above the 25% promotion
gate. The seven maintained Python files total 69,488 bytes. The 16-file fixture
is 2,258 bytes.

Per-consumer copied closure size is the helper plus one consumer, the same
content an inline standalone implementation would require; the extra cost is a
single local stdlib import. Each invocation performs one snapshot collection
and the same Cargo/rustfmt processes the duplicated design requires. No cache,
network, daemon, or second native pass was introduced by the seam.

## Limits and must-not-fire boundaries

- `adapt-project` reports objective authored-file/Cargo facts only. It does not
  infer frameworks or endorse the observed layout.
- `explain-code` covers direct public lexical declarations. Re-exports, aliases,
  resolved types/callers, inherited/generated members, pre/postconditions, and
  function behavior stay unexplained.
- `find-concept-divergence` is strict glossary text evidence, not symbol
  identity. It does not infer conceptual equivalence from spelling.
- `find-duplication` fingerprints whitespace-normalized lexical bodies of named
  functions spanning at least five lines. Exact bodies are review leads, never
  safe-consolidation proof.
- `find-folder-topology-drift` groups direct `.rs` siblings by their first `_`
  or `-` token at the ≥3 threshold. It proves no module ownership, import safety,
  or move plan.
- All five exclude test, generated, vendor, target/build, auxiliary, config, and
  symlink sources from findings. Attributes and strings cannot become
  declaration/function evidence through the lexical mask.
- Macro expansion/hygiene, procedural macros, build-script output/environment,
  `OUT_DIR`, `include!`, unselected cfg/feature/target/profile variants, name and
  type resolution, traits, generics, unsafe/FFI, and runtime dispatch remain
  explicit non-claims.

## Root integration instructions

Root should publish serially after accepting the cohort:

1. Install `_rust/rust_lexical_facts.py` alongside any selected Rust consumer;
   copied closure verification must reject a consumer-only install.
2. Add the Rust command, copied two-file closure, artifacts, statuses, role
   exclusions, native obligations, and non-claims to each of the five shared
   `SKILL.md` files. Do not change non-Rust commands or their standalone closure.
3. Change exactly the five Rust coverage rows from
   `rust-pending-implementation` to the accepted supported disposition, citing
   this packet, the integrated revision, exact artifacts, and native checks.
4. Regenerate matrix/projection artifacts through their existing builder.
   Update router/catalog prose only after the five integrated commands and
   copied closures pass.
5. Preserve the consumer schemas and resist moving interpretation into the
   helper. Promote a broader provider only after a different language proves an
   identical contract and the same economics gate.

This lane intentionally edits no shared skill prose, central coverage, matrix,
router, catalog, plan, or mutation surface.
