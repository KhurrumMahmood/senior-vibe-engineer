# Rust `map-subsystem` P7 learning packet

## Accepted outcome and final boundary

The Rust cohort adds one copied/on-demand command,
`scripts/map_rust.py`, for a Cargo workspace package. It writes the normal
durable map destinations without modifying host source:

- `.claude/docs/subsystems/<name>.md`
- `reports/map/<name>/rust-map.json`

The isolated Cargo 2024 fixture proves the final boundary, not only candidate
discovery. Before and after mapping it passes locked/offline metadata, a
workspace/all-targets/all-features check, tests, Clippy with warnings denied,
rustfmt, and a smoke binary whose exact stdout is `4600`. The resulting map
reports the `billing-core` and `rust-map-smoke` members, the smoke package's
path dependency, the selected library module path
`lib.rs → invoice/mod.rs → invoice/service.rs`, and the public
`InvoiceService` re-export.

## Fact providers and useful partial support

Rust v1 is deliberately `partial` even when diagnostics are clean:

1. `cargo metadata --format-version 1 --locked --offline --no-deps` owns
   workspace/package/dependency/feature/target provenance.
2. `cargo check --message-format=json --locked --offline --workspace
   --all-targets --all-features` owns selected compiler cleanliness, artifacts,
   diagnostics, and build-script execution messages.
3. `rustc --print cfg` records the selected host cfg set.
4. A bounded ordinary-module walk records `mod name;` edges and public
   re-export declarations only after the compiler gate is clean.
5. rust-analyzer contributes workspace/document symbols and compiler-gated
   public-symbol definitions solely through stable LSP. No unstable
   rust-analyzer subcommand or private rustc interface is used.

The map inventories test/example/bench/custom-build sources as provenance but
not production. Unreachable package source, the workspace consumer, generated,
vendor, Cargo target, and symlinked source are also named and excluded. This
makes the partial artifact useful for navigation without laundering auxiliary
or generated code into the production graph.

The following remain explicit unresolved boundaries: `macro_rules!` and
procedural-macro expansion, `include!` contents, build-script `OUT_DIR`
contents, unselected cfg/feature/target-triple variants, and runtime
implementations behind `dyn Trait`. Definitions, invocations, emitted build
cfgs, cfg declarations, and `dyn Trait` spellings are recorded only as boundary
evidence.

Missing Cargo, rustc probing, or rust-analyzer produces a recoverable bounded
`partial` artifact; none is a permanent unsupported-Rust claim. Malformed or
stale locked metadata and compiler failures produce `failed`, exit nonzero, and
replace both artifacts. Valid → failed → valid transitions at the same paths,
tamper/source-staleness verification, unsafe paths, and symlink exclusion are
all exercised.

## Measured closure and economics

Measured after formatting the provider and knowledge file, excluding ignored
`__pycache__` files:

| Metric | Value |
|---|---:|
| Copied `map-subsystem` regular files | 19 |
| Copied closure bytes | 412,889 |
| Closure manifest SHA-256 | `5c261a73bd70cbf74b00068d351dbeadbaa63885cf772b4af5d8a99fb09630ea` |
| Pre-Rust copied closure files / bytes | 17 / 351,267 |
| Rust copied-closure delta | 2 files / 61,622 bytes (17.54%) |
| Rust adapter physical / nonblank LOC | 1,466 / 1,372 |
| Rust final-outcome test physical / nonblank LOC | 447 / 400 |
| Adapter + test physical / nonblank LOC | 1,913 / 1,772 |
| Rust knowledge physical / nonblank LOC | 86 / 70 |
| Isolated fixture files / bytes | 19 / 2,913 |

The adapter is large. Its Rust-specific load-bearing portions are Cargo JSON
normalization, build-script/cfg evidence, selected module/re-export mapping,
source-role classification, and the small stable-LSP client. The other material
is copied-closure lifecycle machinery: path/tool validation, locked/offline
execution, source and artifact hashes, atomic terminal writes, verification,
and rendering. Directly importing a sibling provider would couple Rust to a
different project model and would break standalone copied installation, so no
cross-family extraction belongs in this lane.

## Reuse candidates to compare across the three Rust pilots

Do not extract these from this branch. Root should compare all three Rust pilot
families first and retain only exact common contracts:

- **Cargo discovery/native gate:** executable/version resolution, external
  target-dir and offline environment setup, locked metadata invocation, and
  compiler JSON command/result capture may be duplicated. Share only if all
  pilots agree on workspace scope, features/targets, failure semantics, and
  minimum toolchain handling; do not share their semantic result schemas.
- **Artifact lifecycle:** contained/symlink-safe destinations, atomic writes,
  source snapshots, canonical payload/Markdown hashes, and same-destination
  failed/recovered replacement are candidates. Extraction is justified only if
  all pilots have the same terminal-state and copied-closure contract.
- **Native fixture checks:** locked/offline metadata/check/test/Clippy/rustfmt
  runners and exact smoke assertions may justify a tests-only helper after the
  final commands are compared. Keep fixture topology and expected values local.

The module scanner, cfg interpretation, build-script boundary, LSP request set,
role policy, completeness vocabulary, and Markdown/JSON schema remain
`map-subsystem`-local even if lifecycle helpers are later shared.

## Focused verification at handoff

```text
.venv/bin/python -m pytest -q tests/test_map_subsystem_rust.py
# 6 passed

.venv/bin/ruff check \
  .claude/skills/map-subsystem/scripts/map_rust.py \
  tests/test_map_subsystem_rust.py
# All checks passed

.venv/bin/python -m pytest -q tests/test_rust_pilot_spine.py
# 5 passed

.venv/bin/python -m pytest \
  tests/test_skill_taxonomy.py tests/test_skill_comply.py
# 7 passed

.venv/bin/python -m pytest -q tests/test_map_subsystem_c.py
# 12 passed

.venv/bin/python scripts/lint/run.py --self
# silent-catch and query-mutation passed across 249 ecosystem runtime files
```

The copied-closure test itself runs the real installed script, verifies both
final artifacts, verifies source preservation and hashes, and repeats the full
native check/smoke boundary afterward. The narrow C provider regression proves
that the additive copied closure did not disturb an established map provider;
the full slow language family was intentionally not run.

The generic system `skill-creator` quick validator is not applicable to this
repository's established extended skill frontmatter: it rejects the pre-existing
`argument-hint`, `best_for`, `framework`, `job`, `language`, `not_for`, `scans`,
`tier`, and `user-invocable` keys before inspecting this additive variant. The
shared `SKILL.md` was out of lane and remains unchanged; repository-native
taxonomy/comply tests are the passing structural authority recorded above.
