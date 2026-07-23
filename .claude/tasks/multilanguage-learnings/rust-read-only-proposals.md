# Rust read-only proposal finish

Base revision: 8bf6a0c. Scope: propose-boundary and
propose-folder-reorganization only.

## Outcome

Both pending language-level skills now have bounded Rust 2024 production
adapters. Each writes its own structured inspection and final Markdown
proposal, preserves the existing human review boundary, and edits no host
source.

propose-boundary can surface one conventional child-module domain backed by
named declarations, bounded sibling/caller path evidence, and a clean current
Cargo tree. It defers cohesive targets and excludes generated/test evidence.

propose-folder-reorganization can describe one three-or-more sibling
prefix_suffix.rs cluster as a prefix/ module, including exact moves, one exact
owner declaration replacement, bounded first-party path-token edits, and the
new mod.rs contents. It requires both an explicit human split judgment and an
explicit project convention. The fixture applies the complete plan in a
disposable host and passes the after-tree native matrix and exact smoke.

## Evidence and failure contract

The dependency-free fixture is a Cargo 2024 virtual workspace with a library,
integration test, and exact smoke binary. Every positive run executes:

- cargo metadata --locked --offline --format-version 1
- cargo check --workspace --all-targets --all-features --locked --offline
- cargo test --workspace --all-targets --all-features --locked --offline
- cargo clippy --workspace --all-targets --all-features --locked --offline --
  -D warnings
- cargo fmt --all -- --check
- cargo run -p billing-smoke --locked --offline --quiet with exact stdout

The environment also sets Cargo offline mode, dead network proxies, and an
external target directory. Source/Cargo fingerprints must match before and
after native evidence.

Relevant cfg/path attributes, include inputs, declarative macro definitions,
unsafe, and FFI evidence stop at partial without candidates or moves.
Malformed Cargo/Rust/native/smoke evidence is failed and returns nonzero.
Reusing an artifact path replaces prior facts atomically, so a stale positive
cannot survive a later partial or failure. Missing/old tools are partial rather
than false-clean.

Both final artifacts explicitly do not claim macro/procedural-macro
expansion, build/generated/include inputs, cfg/feature/target variants, trait
dispatch, generics/monomorphization, unsafe/FFI contracts, external consumers,
or public/semver compatibility.

## Shared-seam economics

One shared module owns only project evidence: safe paths, Rust/Cargo/Clippy/
rustfmt probes, locked/offline metadata and native commands, exact smoke,
source inventory/fingerprints, and atomic artifact replacement. Boundary
selection, folder planning, schemas, Markdown, recommendations, and human
review policy remain family-local.

Interface-depth result:

- Deletion test: deleting the seam forces both adapters to reimplement the
  same tool/version policy, offline environment, Cargo matrix, metadata
  normalization, fingerprints, exact smoke, and artifact safety.
- Caller knowledge removed: neither family needs to know command ordering,
  offline/network isolation, tool thresholds, source-preservation checks, or
  terminal artifact mechanics.
- Test surface: both real production adapters exercise it through positive,
  partial, failed, stale, source-preserving, and copied-layout outcomes.
- Adapter reality: two production consumers, not a speculative port.

Measured Python production size is 1,201 physical / 1,125 nonblank lines:
519/481 shared, 317/297 boundary, and 365/347 folder. Inlining the shared
module twice and deleting the two 19-physical/16-nonblank loaders would be
1,682 physical / 1,574 nonblank lines. The shared shape removes 481 physical
(28.6%) and 449 nonblank (28.5%) lines, clearing the required 25% threshold.

The two focused test modules add 354 physical lines; the 18-file fixture adds
126. The copied-layout contract is explicit: copy the selected skill and copy
rust_proposal_evidence.py beside its propose_rust.py. The adapter first loads
that adjacent dependency and otherwise uses the canonical source-tree common
path.

## Verification and integration

Focused Rust outcome suite: 7 passed in 16.23s. The final combined Rust,
preserved proposal-language, Rust-spine, metadata-job, and taxonomy replay
passed 61 tests in 112.73s. Ruff and the repository diff check also pass.

Root integration owns all intentionally untouched publication surfaces:
SKILL.md files, router/catalog, language coverage/matrix, execution plan, and
installed-router tests. Integration must:

1. Copy the shared evidence file beside each installed Rust adapter.
2. Add the Rust commands and narrow claims from each rust-v1.md resource to
   the corresponding SKILL.md without weakening human review.
3. Publish each disposition only after replaying this commit with root-owned
   matrix/router tests.
4. Keep public compatibility explicitly unproved; do not describe either
   adapter as a mutation engine or general Rust semantic platform.
