# Rust folder reorganization proposal v1

Run scripts/propose_rust.py with a Cargo workspace root, a direct source
parent, filename prefix, explicit human split judgment, explicit
allow-module-group project convention, final artifact paths, and optional
exact smoke package/output. The adapter is read-only and requires Rust 1.85+
with Cargo, Clippy, and rustfmt. It uses the copied
rust_project_evidence.py dependency for locked/offline project evidence.

The proposal covers three or more conventional prefix_suffix.rs siblings, one
contiguous owner-module declaration block, exact first-party path tokens, and
one new prefix/mod.rs. Human review remains mandatory. Macros, build/include
inputs, cfg variants, traits, generics, unsafe/FFI contracts, external
consumers, and public or semver compatibility are not proved.
