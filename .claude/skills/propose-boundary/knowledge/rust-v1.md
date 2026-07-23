# Rust boundary proposal v1

Run scripts/propose_rust.py with a Cargo workspace root, one conventional
module file or directory target, final inspection/proposal paths, and optional
exact smoke package/output. The adapter is read-only and requires Rust 1.85+
with Cargo, Clippy, and rustfmt. It uses the copied
rust_project_evidence.py dependency for locked/offline project evidence.

The only positive claim is one named child-module domain with at least three
declarations, bounded first-party path evidence, and clean current-tree native
checks. The proposal remains subject to human review. Macros, build/include
inputs, cfg variants, traits, generics, unsafe/FFI contracts, and public or
semver compatibility are not proved.
