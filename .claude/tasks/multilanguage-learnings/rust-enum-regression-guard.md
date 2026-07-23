# Rust enum proposal and regression guard — learning/economics packet

## Outcome and disposition

- `extract-enum`: recommend `rust-supported` for one complete
  `rust-implicit-state-v1` direct `String` field candidate. The final outcome
  is a source-preserving, `review_required` proposal with exact SHA-256
  authority, caller inventory, literal-to-variant draft, and a separate human
  acceptance gate. It never applies the proposal.
- `prevent-regression`: recommend `rust-supported` for the exact accepted
  public-field branch only. The final output is a project-owned Cargo
  integration test that asserts `Job.state: JobState` at compile time. The
  verifier proves a field-type regression still builds without the guard and
  fails because of the guard after installation.

Both recommendations are bounded outcome claims, not general Rust coverage.
The guard branch abstains on private fields rather than pretending an external
integration test can access them.

## Reuse and closure

The proposal collector consumes the accepted Rust semantic provider's existing
detector schema and source manifest. It does not copy or reinterpret
rust-analyzer, invent an AST, or scan source for candidates. Fresh evidence is
still produced by `find-implicit-state` plus its accepted `map-subsystem` Rust
semantic closure; copied proposal execution itself is standalone once that
artifact exists.

Guard generation requires two colocated inputs under `reports/extract-enum/`:
the read-only `targets.json` and a separately authored, SHA-256-bound
`rust-enum-review-v1` artifact with `status: accepted`. The generated guard and
verifier are self-contained within `prevent-regression`. Host integration is a
reviewed copy into `<package>/tests/`, followed by locked/offline Cargo check,
test, Clippy, and rustfmt. No script mutates production Rust.

## Explicit non-claims

No result covers macro expansions, build-script or `include!` output,
unselected cfg/target variants, trait dispatch, generic owners, unsafe/FFI
behavior, serialization/wire compatibility, or public API compatibility. The
native guard protects one accepted field type; it is not a custom Clippy lint
and does not police unrelated state fields or enum semantics.

## Value proof

`tests/test_rust_enum_guard_finish.py` covers positive, clean, must-not-fire,
partial, failed, stale, source-preservation, copied-layout, and same-destination
lifecycle outcomes. The Cargo 2024 fixture contains a separate `OtherJob.status:
String`; all clean native checks pass with it present. For the must-fire proof,
verification changes only the copied `Job.state` type from `JobState` back to
`String`: `cargo check --locked --offline` passes before the guard is installed,
then `cargo test --no-run --locked --offline` fails at the generated type
assertion.

Preserved evidence: the focused Rust suite passed 4 tests, the existing Go and
Java state families passed 17 tests, and the accepted Rust semantic-family
handoff test passed. Ruff and `git diff --check` are required at closeout.

## LOC economics

Implementation is 1,000 lines across the proposal collector, guard generator,
and native verifier. Test/fixture proof is 549 lines across one pytest module
and two dependency-free Cargo 2024 states (1,549 lines before this packet).
That cost buys stale-input rejection, atomic artifact lifecycle, copied-skill
closure, an explicit acceptance boundary, and a real native regression oracle.

The rejected alternative was a universal Rust parsing/lint platform. The
accepted provider already owns compiler/LSP evidence, while the smallest
durable prevention is a roughly ten-line project-owned compile-time assertion.
Keep this family-local until a second accepted Rust guard shape demonstrates a
shared runtime need.

## Root integration

Root should document the two commands and acceptance artifact in the owned
`SKILL.md` surfaces, update router/catalog/coverage publication metadata, and
declare the upstream `find-implicit-state`/`map-subsystem` closure for fresh
proposal evidence. Do not publish a source-apply phase for `extract-enum`, and
do not describe the generated assertion as a general Clippy or Rust semantic
lint.
