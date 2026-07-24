# Rust subsystem mapping contract (v1)

Use `scripts/map_rust.py` for a Cargo workspace package when a durable Rust
subsystem map is requested. This variant is intentionally useful-but-bounded:
it maps the selected, compiler-clean configuration and marks every wider
semantic claim unresolved.

## Invocation

```bash
python .claude/skills/map-subsystem/scripts/map_rust.py \
  --name billing \
  --target crates/billing-core \
  --project-root . \
  --output .engineering/docs/subsystems/billing.md \
  --evidence reports/map/billing/rust-map.json
```

To verify existing artifacts without re-running Cargo or rust-analyzer:

```bash
python .claude/skills/map-subsystem/scripts/map_rust.py \
  --name billing \
  --target crates/billing-core \
  --project-root . \
  --output .engineering/docs/subsystems/billing.md \
  --evidence reports/map/billing/rust-map.json \
  --verify-artifacts
```

`--target` must be the directory of a workspace package. Outputs are restricted
to `.engineering/docs/subsystems/` and `reports/map/`. For hermetic or concurrent
runs, pass an external `--cargo-target-dir`.

## Stable evidence chain

1. `cargo metadata --format-version 1 --locked --offline --no-deps` establishes
   workspace membership, packages, path dependencies, features, and Cargo
   target provenance.
2. `cargo check --message-format=json --locked --offline --workspace
   --all-targets --all-features` establishes whether the selected host/all-
   features build is compiler-clean. Compiler artifacts, diagnostics, and
   `build-script-executed` messages are retained.
3. `rustc --print cfg` records selected host cfg values.
4. Reachable ordinary `mod name;` declarations establish a bounded production
   module graph only after the Cargo check succeeds. Tests, examples, benches,
   custom build scripts, unreachable source, generated trees, vendor trees,
   target output, and symlinked sources remain outside that graph.
5. rust-analyzer is queried through standard LSP `initialize`,
   `workspace/symbol`, `textDocument/documentSymbol`, and
   `textDocument/definition` methods. The unstable `analysis-stats` CLI and
   private rustc interfaces are forbidden.

The JSON evidence includes source and artifact hashes. Verification checks the
evidence payload, rendered Markdown, schema/status, and current source snapshot.

## Honest partial status

A successful Rust v1 map reports `status: partial` even when the selected Cargo
check is clean. The following are not promoted to resolved facts:

- `macro_rules!` or procedural-macro expansion;
- contents written beneath a build script's `OUT_DIR`;
- `include!` contents;
- unselected cfg, feature, and target-triple variants;
- runtime implementations behind `dyn Trait` dispatch.

Macro definitions/invocations, build-script cfg output, cfg declarations, and
`dyn Trait` spellings are boundary records, not substitutes for those semantics.
Missing rust-analyzer or rustc probing keeps usable Cargo evidence and produces
a recoverable partial map. Missing Cargo also produces a bounded partial
inventory; it must never be reported as permanent Rust-language non-support.

## Lifecycle

- Malformed/stale locked metadata or a compiler failure produces `failed`, exits
  2, and atomically replaces both prior artifacts.
- Missing tools produce `partial` artifacts and exit 0 so later installation can
  recover at the same destinations.
- A later clean run atomically replaces a failed artifact.
- Unsafe paths are rejected before either artifact is touched.
- Mapping must not modify project source. A changed source snapshot is a failed
  terminal state.

The Markdown is the human map. The JSON is the durable evidence boundary; use
it for automation and verification.
