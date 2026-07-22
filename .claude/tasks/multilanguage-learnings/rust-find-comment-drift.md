# Rust find-comment-drift learning

## Outcome

The copied `find-comment-drift` closure now contains one self-contained Rust
lexical/syntax producer, `scripts/analyze_comments_rust.py`. A Rust-aware byte
lexer identifies exact line, block, outer-doc, and inner-doc comment spans while
excluding comment-looking text in ordinary, byte, raw, and character literals.
Host-owned `cargo check --locked --offline --workspace --all-targets
--all-features` gates the selected workspace snapshot, and `rustfmt --emit
stdout --config skip_children=true` parses each eligible source without writing
it.

On the frozen Rust fixture, the analyzer emits exactly one
`behavior_drift_comment` for
`crates/billing-core/src/invoice/service.rs`: the outer doc comment claims that
`fee_cents` calculates a percentage from the invoice amount, but the complete
adjacent function body returns the fixed literal `125`. The finding records
exact comment and function byte/line/column spans, both spelling hashes, the
parameter spelling, returned literal, full-source hash, detection hash, and
source-manifest hash. The accurate `render` doc comment stays clean.

The terminal evidence states keep coverage separate from result:
`complete/advisory-findings` and `complete/clean-within-complete` are successful;
a malformed eligible source is `partial/incomplete`; missing or old Rust tools
are also `partial/incomplete`, never `unsupported`; and broken version probes,
Cargo checks, or native providers become `failed`. Same-destination runs remove
all four prior artifacts before atomically publishing `detections.jsonl`,
`scan.json`, `findings.json`, and `report.md`. Valid-to-failed,
failed-to-valid, and changed-source tests prove stale findings and hashes do not
survive.

## Source, lexical, and native boundary

Ordinary `.rs` files are inventoried before eligibility. Test trees, generated
trees/markers, `vendor`, `target` and other build trees, examples, benches,
`build.rs`, and symlinks are recorded with explicit exclusion reasons and are
not analyzed. Cargo manifests and locks are project metadata, not Rust-source
inventory rows. The helper preserves every inventoried source byte.

The byte lexer handles nested block comments, raw strings with arbitrary hash
delimiters, ordinary/byte strings, escaped character literals, and lifetimes.
Rust attributes such as `#[doc = "..."]` are not comment evidence. A local
`#[cfg]`/`#[cfg_attr]` before a doc comment or adjacent function suppresses the
behavior rule because the helper has no item-level selection proof. The Cargo
gate selects the frozen all-feature/all-target workspace, but the analyzer does
not project that fact onto unenumerated target triples, profiles, or orphan
source.

The behavior rule is intentionally narrow: a real comment must claim a
percentage/rate derived from an amount/subtotal/total; the adjacent Rust item
must be a function; and its entire masked body must be one fixed numeric literal
with an optional `return` and semicolon. The helper also preserves the family's
existing lexical stale-term, brittle Rust line-reference, and detached-banner
bands. This is useful bounded evidence, not natural-language or runtime proof.

## What generalized

- The family-local inventory, four artifacts, JSONL finding shape, exact source
  fingerprints, content-derived manifest, atomic replacement, copied-layout
  replay, and source-preservation checks transferred directly.
- Clean remains a result only inside complete evidence. Empty partial or failed
  evidence never becomes clean, and absent/old tooling stays pending/partial
  rather than being mislabeled permanently unsupported.
- Each eligible file needs its own syntax evidence even after a successful
  workspace check: Cargo proves the selected target graph; rustfmt supplies a
  bounded parser gate for discovered `.rs` files that are not Cargo targets.
- Native state must live outside the audited tree. Cargo home and target output
  use temporary directories, offline mode, and a locked workspace.

## What stayed Rust/family-local

Rust raw-string/hash delimiters, nested block comments, doc-comment kinds,
attribute/cfg adjacency, function modifiers, numeric suffixes, and
Cargo/rustfmt commands remain in the copied skill helper. No universal AST,
comment-to-code schema, source-role router, or shared natural-language behavior
engine was introduced.

The producer makes no claims about `macro_rules!` expansion/hygiene,
procedural-macro host execution, `build.rs` output or environment, `OUT_DIR`,
`include!`, unselected cfg/feature/target/profile variants, name or type
resolution, traits, generics/monomorphization, unsafe/FFI, or runtime dispatch.
It does not treat examples or benches as production modules, and it does not
claim that doc syntax proves behavior.

## Native verification and acquisition

No tool or dependency was installed or updated, no network was used, and no
source mutation was performed. Verification selected:

- `/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python` <!-- # host-ref-allow: required frozen P7 runtime -->
  3.11.10 for the isolated stdlib-only producer, Ruff, and pytest;
- `/Users/khurrummahmood/.local/bin/rustc` <!-- # host-ref-allow: required frozen P7 runtime -->
  1.97.1 and Cargo 1.97.1 for the native workspace; and
- `/Users/khurrummahmood/.local/bin/rustfmt` <!-- # host-ref-allow: required frozen P7 runtime -->
  1.9.0-stable for per-file parse evidence and the native format check.

The copied fixture passed locked/offline Cargo check and test across the
workspace, all targets, and all features; `cargo fmt --all -- --check`; and the
`rust-pilot-smoke` executable (`invoice:INV-42:125`). The malformed fixture was
rejected by rustfmt and remained `partial/incomplete`. Focused Rust verification
passed 6 tests in 16.40 seconds; the narrow complete comment-drift family passed
49 tests in 64.97 seconds; Ruff passed both owned Python files. One standalone
complete analyzer observation took 2.64 seconds wall time. These are local
single observations, not performance thresholds.

## Closure, LOC, bytes, and economics

Closure is every regular non-`.pyc` file below
`.claude/skills/find-comment-drift`, excluding `__pycache__`, with manifest
SHA-256 over sorted `path + NUL + file_sha256 + LF` rows.

- Branch base: 21 files, 174,037 bytes,
  `manifest_sha256=86aa0d794fd0e922aa0f330f1fa3a41204d346c59c92cfa4d7e52ce63b153e1d`.
- Rust result: 22 files, 203,947 bytes,
  `manifest_sha256=762a2328342d909e1c79d6a6abfe3001b8caf6218ee93f168d6e8582079ec9e1`.
- Delta: one copied-runtime file and 29,910 bytes (17.19% selected-skill
  closure growth).

Adapter-plus-test code is 1,200 physical lines and 1,070 nonblank lines:
809/733 in `analyze_comments_rust.py` and 391/337 in
`tests/test_find_comment_drift_rust.py`. Their combined size is 44,653 bytes;
the pre-existing frozen Rust fixture and this learning packet are excluded from
LOC.

The direct value is a durable, copied, source-preserving Rust result with native
failure recovery and exact evidence. The cost is substantial local lifecycle
and native-gate code around a deliberately tiny detection rule. That is
acceptable for this frozen pilot, but it is a warning against multiplying
language adapters without cohort-level comparison.

## Transfer seams for root comparison

This lane deliberately performs no extraction. Once the lexical, semantic, and
mutation Rust pilots are all present, root should compare their concrete code
before deciding whether any seam is truly stable. Expected duplicated candidates
are `.rs` discovery and role labels, Rust/Cargo/rustfmt version probes, temporary
offline Cargo state, locked all-target/all-feature commands, source and manifest
hashing, atomic JSON/text publication, stale-destination clearing, and terminal
status summaries. Extraction is warranted only if all three implementations
share the same semantics; tool commands, cfg selection, source ownership, and
final artifact schemas may differ enough to remain family-local.

## Root integration needs

Root should make only shared publication changes after this cohort is accepted:

1. Add the Rust copied-helper command, four-artifact contract, Rust >= 1.85
   boundary, role exclusions, Cargo/rustfmt gates, and semantic non-claims to
   `find-comment-drift/SKILL.md`.
2. Change only the `find-comment-drift` row in Rust coverage from
   `rust-pending-implementation` to the accepted supported disposition, citing
   this learning packet, integrated revision, native checks, and bounded rule.
3. Regenerate shared projections through their existing builder and update any
   router/catalog description only after integration verification. Do not call
   absent/old tooling unsupported, and do not publish semantic or mutation Rust
   support from this lexical result.

Those shared surfaces remain root-owned; this lane edits none of them.
