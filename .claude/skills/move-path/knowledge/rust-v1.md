# Rust module move v1

Load this guide only for a Cargo-backed Rust project and only for one
conventional leaf module move.

## Earned contract

The standalone `scripts/rust_module_move.py` adapter accepts exactly one move
from either `name.rs` to `new_name.rs` or a leaf `name/mod.rs` directory to
`new_name/mod.rs`. Cargo metadata must prove the source belongs to one regular
library target. The adapter derives the module path from that target, then
rewrites only exact Rust token paths that resolve to the moved module and its
parent `mod name;` declaration. A public type re-export remains public; the
frozen proof preserves `InvoiceService` at the parent-module API.

Run a dry-run first and authorize apply with its
`source_manifest.before_fingerprint`:

```bash
<product-venv>/bin/python -I -S \
  .claude/skills/move-path/scripts/rust_module_move.py \
  --plan <absolute-plan.json> \
  --project-root <absolute-project-root> \
  --report-dir <absolute-project-root>/reports/move-path \
  --dry-run --json

<product-venv>/bin/python -I -S \
  .claude/skills/move-path/scripts/rust_module_move.py \
  --plan <absolute-plan.json> \
  --project-root <absolute-project-root> \
  --report-dir <absolute-project-root>/reports/move-path \
  --apply --expected-source-sha256 <dry-run-fingerprint> --json
```

The version-1 plan has one `moves` row, `rewrite.code_imports` equal to
`update-rust`, explicit Cargo/Rust tool paths, and a smoke package plus exact
expected stdout. Apply is transactional: any native or exact-after-tree failure
restores the complete pre-apply source snapshot. `--check` proves the new module
identity and native boundary after a completed move.

## Native and report boundary

The adapter requires Cargo and rustc 1.85+ and probes Clippy and rustfmt. It
runs Cargo metadata, check, test, and Clippy with `--locked --offline
--workspace --all-targets --all-features`, runs `cargo fmt --all -- --check`,
and executes the named smoke package. Cargo home and target output are isolated
outside the reviewed project snapshot. The report records exact token edits,
the file rename, before/expected/actual fingerprints, native preflight and
postflight, rollback, and the final `complete`, `partial`, or `failed` state.

## Refusal boundary

Return `partial` without applying when exact resolution is not provable:

- `#[path]`, relevant `cfg`/feature variants, `include!`, macro-generated
  modules, old module identities in strings, or build-script output;
- generated, vendor, target, build, dist, or out paths; symlink boundaries;
- multiple moves, cross-package moves, non-library targets, or non-leaf module
  directory shapes;
- missing, old, or broken tools, including missing optional Clippy/rustfmt.

Malformed Cargo/Rust, stale locks, stale source fingerprints, native failures,
or an after-tree differing from the reviewed diff are `failed`, never
permanent unsupported. This v1 does not cover crate/package renames, arbitrary
file moves, inline modules, procedural macros, dependency changes, non-Cargo
builds, nightly/no_std/cross-compilation variants, or reflective identities.
