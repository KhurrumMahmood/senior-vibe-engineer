# Rust P7 spine learning packet

This spine proves a Cargo-native Rust foundation without publishing a support
claim. Stable Rust and Cargo 1.97.1 resolve through existing rustup proxies;
rust-analyzer 1.97.1, Clippy 0.1.97, and rustfmt 1.9.0-stable are installed
optional components. No package, component, or dependency was installed or
updated, no network was used, and product Python commands use
`/Users/<user>/Projects/engineering-skills-product/.venv/bin/python` 3.11.10.

The copied host is a dependency-free Cargo 2024 virtual workspace with a
library and smoke binary. `cargo metadata --locked --offline --no-deps` proves
both members and its lib, bin, integration-test, example, bench, and custom
build targets. Check, test, Clippy warnings-as-errors, rustfmt check, and the
smoke binary run with all targets/features and `CARGO_TARGET_DIR` outside the
host. A standalone Rust source also passes direct `rustc` test and executable
smoke. Malformed Rust, malformed Cargo metadata, and a stale lock are rejected
without changing source or configuration bytes.

The base inventory owns only `.rs`. It classifies modules as source,
integration tests as test, `build.rs` as executable configuration, examples
and benches as auxiliary target source, and generated code separately. Vendor,
target, and symlink roots are excluded. Cargo manifests and the lock are
project metadata, not `.rs` source. Cargo metadata—not directory naming—is the
authority for workspace members and target kinds.

Stable Cargo JSON and diagnostics are the portable project foundation.
rust-analyzer's LSP can contribute bounded references and types, but its CLI
analysis subcommands explicitly carry no stability guarantee and remain
feasibility probes. Clippy and rustfmt are native optional policy tools. Private
rustc APIs are not a portability dependency.

Rust completeness is variant-sensitive. `macro_rules!`, procedural macros,
build-script output/environment, `OUT_DIR`/`include!`, cfg/features/targets,
workspace inheritance and patches, trait-object dispatch, monomorphization,
unsafe/FFI, optional dependencies, nightly, no_std, cross compilation, and
non-Cargo builds all require explicit evidence. A successful default build or
rust-analyzer exit cannot silently cover those variants.

The frozen cohort order is lexical `find-comment-drift`, semantic
`map-subsystem`, then serial `move-path` after accepted module/reference
lineage. Each contract names positive final outcomes, must-not-fire/refusal
cases, copied-layout and native obligations, fingerprints, stale-output
transitions, and rollback. The fixture is 2,789 bytes; the exercised
profile/doctor/inventory runtime closure is 44,944 bytes.

No skill final artifact or mutation has run. Exactly 22 language-level rows are
`rust-pending-implementation`. Missing optional tools and unfinished work are
not evidence for `rust-unsupported`.
