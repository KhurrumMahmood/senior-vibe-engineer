# WP5 Slice 2 evidence — native provider execution

Evidence capture date: 2026-07-16

Work began from committed revision
`eb53bbf172e8a8ad5515c5bdabdf3a65c074d947`. The shared worktree advanced
through unrelated committed WP3/WP5 work during this lane; the final content
snapshot below was captured on descendant `b91a759470cddad5523ecca7efe6e74b5b133028`.
This lane did not create a commit.

Functional implementation revision:
`91fd269bd321b72e7c6c4eadfdc9d36eba5f5ad1`.

This record covers only IM-5 and IM-6. It advances the native-provider portions
of AC-5.2 and AC-5.3, but does not claim either acceptance criterion or WP5 as a
whole complete. It does not implement the public CLI, digest/diff/ratchet,
judgment, status/queue consumers, packets, harness ownership, or parser-backed
ecosystem members.

## Delivered boundary

- The canonical capability registry now authors the complete native provider
  contracts and language-to-provider composition for Ruff, ESLint, TypeScript
  compiler diagnostics, Clippy, and Go vet. Each contract declares executable
  candidates, argv, version probe/pattern, timeout, output format/stream, byte
  ceiling, diagnostic-complete exit codes, and semantic-rule version.
- `scripts/_lib/capability_registry.py` validates those authored contracts and
  rejects unknown/incompatible providers, malformed discovery/argv/version
  declarations, invalid bounds, and overlapping exit classifications.
- `scripts/sweep_shims.py` remains the thin registry facade. It resolves native
  contracts without a local language/tool/support enum and preserves the
  characterized parser-adapter resolution surface.
- `scripts/sweep/native.py` owns the shared subprocess contract: candidate
  discovery, exact version probing, bounded file-backed stdout/stderr capture,
  process-group kill on timeout/overflow, typed schema-valid failures, raw
  hashes/byte counts, and atomic raw-artifact publication after validation.
  Rustup dispatch symlinks are deliberately not dereferenced, because changing
  `cargo`'s argv-0 basename breaks rustup proxy selection. Clippy build output
  is redirected to an isolated temporary `CARGO_TARGET_DIR`, so detection does
  not leave `target/` products in a host.
- `scripts/sweep/_native_parsers.py` strictly normalizes all five native shapes
  to the existing `FindingInput`/provider-observation contracts. Valid JSON or
  text of an unknown shape fails instead of becoming a clean zero; Cargo JSON
  requires a successful `build-finished` sentinel. Native rule/code, native
  severity, repository-relative location, tool version, and raw hashes remain
  present at the shared manifest boundary.
- Saved outputs compose into one schema-1 manifest with five providers and
  native IDs `F401`, `no-unused-vars`, `TS2322`, `clippy::ptr_arg`, and
  `printf`. No second manifest writer or activation-manifest coupling was
  introduced.

## Saved fixtures and fault coverage

`tests/fixtures/sweep/raw/` contains 15 saved native/fault artifacts. Its
path-and-content SHA-256 aggregate is
`c490b95ca9b522b5244b09f860160fd69f8dea895ee31476e15d0b4273117271`.

The focused tests prove completed clean-zero observations separately from all
of these loud failure kinds:

- `missing_executable`
- `unexpected_exit`
- `parse_failure`
- `timeout`
- `truncated_output`
- `output_overflow`
- `output_corruption`
- `schema_mismatch`
- `missing_completion`

Every injected failure exposes a schema-valid failed provider observation and
never returns partial findings as a successful prefix.

`tests/fixtures/sweep/hosts/` contains 36 authored files across Python,
TypeScript/JavaScript, Rust, and Go `before`, `after`, and `clean` roots. Its
path-and-content SHA-256 aggregate is
`49bc398bc4cc6214e11d458f9a85b305c74d8811c65978c287fddb3009c1ca10`.

## Live final-boundary matrix

All five named providers executed against the authored `before` and `clean`
projects; no provider was skipped. The before run retained the native rule and
the clean run completed with zero findings.

| Provider | Probed version | Before | Clean |
|---|---|---:|---:|
| Ruff | `ruff 0.6.9` | 1 × `F401` | 0 |
| ESLint | `v9.38.0` | 1 × `no-unused-vars` | 0 |
| TypeScript compiler | `Version 5.9.3` | 1 × `TS2322` | 0 |
| Clippy | `clippy 0.1.88 (6b00bc3880 2025-06-23)` | 2 occurrences of `clippy::ptr_arg` under `--all-targets` | 0 |
| Go vet | `vet version go1.26.5` | 1 × `printf` | 0 |

The ten atomically published live stdout/stderr artifacts have aggregate
SHA-256
`155fde5a8abadebfd762f7015c793194a7c2d7a63760bda71b777cf9e163de63`.
Individual raw hashes and byte counts were asserted against each observation.

The non-system Node, Rust, and Go tools used only for this live proof were
resolved under `/tmp`; no system package installation or repository-local
tool cache was retained.

## Verification

```text
.venv/bin/python -m pytest -q -m 'not sweep_live' \
  tests/test_sweep_native_shims.py tests/test_sweep_manifest.py \
  tests/test_sweep_slice0_characterization.py \
  tests/test_capability_consumers.py tests/test_capability_registry.py
72 passed, 5 deselected

PATH=<temporary Node/Go/Rust tool bins> \
RUSTUP_HOME=/tmp/wp5-rustup2 CARGO_HOME=/tmp/wp5-cargo2 \
  .venv/bin/python -m pytest -q -rs -m sweep_live \
  tests/test_sweep_native_shims.py
5 passed, 13 deselected

.venv/bin/ruff check scripts/sweep scripts/sweep_shims.py \
  scripts/_lib/capability_registry.py tests/test_sweep_native_shims.py
All checks passed!

.venv/bin/python scripts/check_capability_registry_consumers.py
OK — 7 consumers use the canonical capability registry

.venv/bin/python scripts/specs.py inventory-check portable-batch-sweep --strict
Status: CLEAN

.venv/bin/python scripts/specs.py coverage portable-batch-sweep
Summary: 5/28 implemented, 2 implementation-ahead refs (IM-5 and IM-6)
```

The controlling spec checkboxes were intentionally not edited in this lane;
the coordinator owns reconciliation after review. The full suite was not run
because this is a scoped shared-worktree slice and unrelated WP3 work was
active; the native, manifest, characterization, registry-consumer, and registry
contract surfaces are the narrow shared regression set.

## Environment and content addresses

```text
macOS 26.5.1 (25F80), arm64
Python 3.11.10
Node 22.21.1; npm 11.12.1
Ruff 0.6.9; ESLint 9.38.0; TypeScript 5.9.3
Cargo 1.88.0; Clippy 0.1.88; Go/Go-vet 1.26.5
Runtime identity: GPT-5 Codex. Model variant and effort setting were not visible.
```

| Owned implementation/test path | Bytes | SHA-256 |
|---|---:|---|
| `.claude/skills/_common/capability-registry.yml` | 14,780 | `41264885eb68ae22bb17642df037f6b762ae2747c76b580ef0afffe8a01e0cce` |
| `pyproject.toml` | 1,429 | `f7936bc06f7d3542f438e428b97d9b46e890735e1b74a4b68169df7c95e7a26c` |
| `scripts/_lib/capability_registry.py` | 31,479 | `18fefdeb7bef2bf87c02ae27dd44f4ebecbfcf98ec73f81e96dc76eeec69102e` |
| `scripts/sweep/__init__.py` | 1,530 | `3e78b0f6399f9a350a29f50d71a0794883fbbf0b364c664a68c90635cf908e20` |
| `scripts/sweep/_native_parsers.py` | 14,518 | `3923844b7f64ecc7466cba4b3a1d935dad09a4cd184b526875a1e753994dc411` |
| `scripts/sweep/native.py` | 18,969 | `6f17f02ab1e61d46e94dd3f13ddf1b7f4c00f2de6c00312b57c71ae22db4025e` |
| `scripts/sweep_shims.py` | 2,777 | `9a1485b9a90c131e6e1cd0a75cbfd9cd05dcb7aedb1ab00cb3a228039443458c` |
| `tests/test_sweep_native_shims.py` | 12,100 | `71e84b2cc67a63f57e3a1c1bd5cbd7f0ac9c5d655eb1531464f0846dfe666f95` |

At capture time the shared worktree also contained unrelated WP3 rule/skill,
workflow, agent-policy log, and WP5 parser-entry work. Those paths were neither
edited nor included in this scoped content snapshot. Any subsequent content
change invalidates the hashes in this record.

## Deferred by design

- IM-7 through IM-11 remain open; no CLI, digest, ratchet, judgment, consumer,
  packet, or harness behavior was added.
- Parser-backed ecosystem members and their fixture promotion are not part of
  this native-provider slice, irrespective of separate IM-12 work in the shared
  worktree.
- IM-15 remains the final CI/mixed-host proof. This slice proves each native
  provider and saved cross-provider manifest composition, not the future public
  scan/diff CLI boundary.
- No master tracker, controlling spec checkbox, ADR status/embodiment,
  status/queue file, or commit was changed by this lane.

Current action: Slice 2 implementation and focused verification complete;
await coordinator reconciliation. Last fully completed WP5 acceptance
criterion: none (IM-5/IM-6 are implementation items, not standalone ACs).

Coordinator reconciliation also excluded `tests/fixtures/sweep/hosts/` from
the repository's auto-fixing Ruff pre-commit hook. This prevents the hook from
deleting intentional diagnostics; each live host retains its own local native
tool configuration, and the full repository `ruff check scripts tests` remains
clean.
