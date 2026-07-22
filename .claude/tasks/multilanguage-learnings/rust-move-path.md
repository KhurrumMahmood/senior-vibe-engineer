# Rust `move-path` final-value learning

## Outcome and user value

The frozen Rust mutation cohort now proves one useful end-to-end outcome: move
the conventional module file
`crates/billing-core/src/invoice/service.rs` to `invoice_service.rs`, update the
parent `mod` declaration and every statically resolved first-party Rust path,
and preserve the public `invoice::InvoiceService` re-export. It also proves the
equivalent leaf-directory representation (`service/mod.rs`). Preview is
source-preserving, apply is fingerprint-authorized and transactional, and
check proves the completed state.

The value is narrower and stronger than a text rename: Cargo check/test across
all workspace targets and features, Clippy with warnings denied, rustfmt, an
executable smoke, and an exact whole-host after-tree oracle all must agree.
Failure after the move restores the complete pre-apply snapshot, including an
injected out-of-plan mutation.

## Toolchain and acquisition

- Python: the explicitly supplied engineering-skills-product virtualenv,
  Python 3.11; every Python command used its absolute interpreter path
- Cargo and rustc: 1.97.1
- cargo-clippy: 0.1.97
- rustfmt: 1.9.0-stable
- Dependency or tool installation: none
- Network: disabled by `--offline`, `CARGO_NET_OFFLINE`, and dead proxy values

The fixture is a dependency-free Cargo 2024 virtual workspace with a library,
smoke binary, integration test, example, bench, and custom build target. Native
output is isolated outside the copied host.

## Contract and evidence

`complete` requires one regular-library leaf module, a conventional file or
directory representation, an exact parent declaration, provable token-path
references, the preserved public re-export, clean native preflight/postflight,
and an exact expected after tree. Reports contain the review diff, exact edits,
tool probes, source fingerprints, native results, and rollback state. Reusing
the same report path across complete -> failed -> complete clears stale facts.

`partial` is the honest boundary for missing/old/broken tools and for shapes
whose full meaning is not statically proven: `#[path]`, relevant cfg, include,
macro-generated modules, reflective text, build output, excluded roots,
symlinks, multiple moves, or ambiguous Cargo/module topology. Apply is blocked.
Malformed Cargo/Rust, stale locks or source fingerprints, postflight failures,
and unexpected mutation are `failed`; none is mislabeled permanent
unsupported.

Focused tests cover file and directory moves, dry-run/apply/check, exact edits,
public API preservation, all native commands, lifecycle recovery, each refusal
class, missing/old/broken tools, malformed inputs, stale locks/fingerprints,
rollback, exact-diff mutation detection, excluded decoys, and a copied
single-file adapter invoked outside the repository.

## Local mechanics and extraction seams

Rust-local policy belongs in `rust_module_move.py`: Cargo target/module
derivation, Rust lexical masking and token-path resolution, module declaration
proof, cfg/macro/include/build-script refusal, and the exact native command
matrix. No shared mutation executor or router was added.

Root should compare all three Rust pilot families before extracting anything.
The duplicated candidates are deliberately only seams today:

- Cargo/rustc/Clippy/rustfmt tool discovery, version probes, and pending-tool
  classification;
- isolated offline Cargo environment and Cargo metadata/check/test/Clippy/fmt
  command assembly;
- report lifecycle replacement, atomic JSON/Markdown writes, source snapshot
  fingerprints, exact-after-tree comparison, and rollback;
- Cargo workspace/package/target normalization used to establish project
  context.

Extraction is justified only if root finds the policies and report schemas
identical across all three completed Rust families. The module resolver,
rewrite planner, refusal semantics, and smoke expectation remain mutation-local.

## Size and economics

The focused implementation is intentionally substantial because it carries a
standalone copied boundary and transaction oracle. The adapter and focused test
contain 2,027 physical / 1,852 nonblank lines and 78,016 bytes: 1,460 lines in
the adapter and 567 in the test. The 20-file fixture adds 120 physical / 102
nonblank lines and 2,759 bytes. With the 66-line knowledge guide and this
115-line learning packet, the owned diff is 2,328 added lines / 89,861 bytes;
there are no removals or shared-file edits.

The copied `move-path` closure is 12 intended files / 268,279 bytes with
manifest SHA-256
`a8276666cda9c97888caf77882dc7ae477baaec542b7613d014d344a21ae7d33`,
using sorted `relative-path + NUL + file-SHA-256 + LF` rows. Rust adds 59,178
bytes to the prior 209,101-byte closure, a 28.3% increase. The fixture manifest
uses the same row format and is
`587836447bdb6f8042c9af3ea765548dd7516b8e0cfebb9c2eab231a445f963e`.

The final focused replay passed 18 tests in 139.19 seconds (139.39 seconds
wall). Rust spine, existing `move-path`, and skill conformance checks passed 28
with one environment-expected skip in 29.07 seconds. This cohort should not be
promoted as general Rust mutation support on LOC alone: the earned user value
is the single frozen module move, and the maintenance cost is acceptable only
because every unsafe neighboring shape stops before writes.

## Limits and root integration

This does not rename crates/packages, change Cargo dependencies, move arbitrary
Rust files, reason through inline/procedural macro expansion, rewrite strings,
support non-Cargo/nightly/no_std/cross targets, or certify untested cfg/feature
variants. Broader support needs a new cohort and evidence.

Root integration owns shared `SKILL.md`/router/matrix/plan publication and the
serial family replay. The minimal integration is to route Rust v1 plans to the
standalone adapter, link the knowledge guide, publish only the frozen module
move capability, and retain every partial/failed boundary above.
