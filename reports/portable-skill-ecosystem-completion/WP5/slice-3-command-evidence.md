# WP5 Slice 3 evidence — public commands, digest, diff, and ratchet

Evidence capture date: 2026-07-16

Functional implementation revision:
`d2654f3f1183f2679d66dc0dc35833c654e690c7`.

This record covers only IM-7 and IM-8. It advances AC-5.1, AC-5.3, AC-5.4,
and the bounded-artifact part of AC-5.5, but it does not claim any master WP5
acceptance criterion complete. Judgment gates, status/queue consumers, packet
creation, harness-owned verification, the final five-host CI boundary, and ADR
embodiment remain later slices.

## Delivered boundary

- `scripts/sweep/commands.py` provides deterministic library services for a
  registry-selected native scan, bounded digest rendering, canonical diffing,
  and a non-mutating ratchet decision.
- `scripts/sweep/__main__.py` supplies public `scan`, `digest`, `diff`, and
  `ratchet` help and typed exit behavior. Both `python -m sweep` with the
  bundled `scripts` root and `python -m scripts.sweep` from a bundle root are
  exercised.
- Scan requires an explicit language set, case policy, source-state envelope,
  and an exact absolute executable for every registry-selected provider.
  Registry order, current working directory, activated-shell state, and
  machine `PATH` order cannot silently select a different provider binary.
- A provider failure returns the typed provider exit and canonical failure
  envelope without publishing a manifest. A successful empty scan contains a
  completed provider observation and is distinct from that failure.
- Digest selection is deterministic, contains addressable `f2_` IDs, copies at
  most 50 findings, and never exceeds 65,536 bytes. Smaller requested byte
  ceilings remove whole rows rather than truncating UTF-8 or identities.
- Diff output is the canonical `build_diff` artifact. CLI and library bytes are
  equal, including from a working directory outside the repository.
- Ratchet rejects new findings and increased numeric metrics without changing
  the baseline. Fixed findings and metric decreases tighten automatically.
  A deliberate increase requires a current finding ID, reason, operator,
  exact current revision, and timezone-bearing timestamp; the complete record
  is retained in the diff artifact before the baseline is atomically replaced.
  Unknown, stale, duplicate, malformed, or irrelevant accepts fail.
- Complete-manifest validation happens before any ratchet output or baseline
  update, so failed/partial/corrupt current input cannot tighten the baseline.
- Runtime package sources contain no prototype evidence path or import.

## Verification

```text
.venv/bin/python -m pytest --override-ini addopts= -q -p no:cacheprovider \
  tests/test_sweep_cli.py
10 passed

.venv/bin/python -m pytest --override-ini addopts= -q -p no:cacheprovider \
  tests/test_sweep_cli.py tests/test_sweep_manifest.py \
  tests/test_sweep_native_shims.py tests/test_sweep_slice0_characterization.py
51 passed, 5 skipped
```

The five skips are the separately provisioned live native-provider cases from
Slice 2. This command slice invokes a deterministic fake Ruff executable for
its executable-selection and clean-zero/failure final-boundary tests; the real
five-provider live matrix remains recorded by Slice 2 and will run together in
IM-15.

```text
.venv/bin/ruff check scripts/sweep tests/test_sweep_cli.py \
  tests/test_sweep_manifest.py tests/test_sweep_native_shims.py \
  tests/test_sweep_slice0_characterization.py
All checks passed!

.venv/bin/python scripts/specs.py inventory-check portable-batch-sweep --strict
Status: CLEAN

.venv/bin/python scripts/specs.py coverage portable-batch-sweep
Summary: 7/28 implemented, 2 implementation-ahead refs (IM-7 and IM-8)

git diff --check
clean

git commit -m 'Add deterministic sweep command pipeline'
all configured commit hooks passed
```

The controlling spec checkboxes are intentionally not edited in this isolated
functional lane; the coordinator owns reconciliation after review. No master
tracker or ADR status/embodiment field changed here.

## Content addresses and environment

```text
macOS 26.5.1 (25F80), arm64
Python 3.11.10
Runtime identity: GPT-5 Codex. Model variant and effort setting were not exposed.
```

| Owned path | Bytes | SHA-256 |
|---|---:|---|
| `scripts/sweep/__init__.py` | 2,224 | `57a2be119632424bb99144922134899e1f661c74055762bf518d498a746f115d` |
| `scripts/sweep/__main__.py` | 6,497 | `0ff70a581cb640b5f1b77f160167ca63ea2f3694db16d9b89800f38c2e09e252` |
| `scripts/sweep/commands.py` | 10,168 | `81e00e3aaaafe8d71b402dc9b3577c0dc2b34dffb3b67078cbb978ced29196a4` |
| `tests/test_sweep_cli.py` | 12,134 | `0f00bafe3d1488197ff0dbb4d1a5d04feec4b7ae6e58e7d74e701f7685f2924d` |

Any subsequent content change invalidates the hashes in this record.

## Deferred by design

- IM-9 through IM-11 still own mandatory judgments, migrated consumers,
  packets, and harness verification. Slice 3's ordinary digest is an
  intermediate command contract and must be judgment-gated before WP5 can
  satisfy AC-5.5 or AC-5.7.
- Parser-backed providers are a separate IM-13/IM-14 lane and are not claimed
  by the native-only `scan_native` entry point here. The integrated scanner in
  IM-15 must compose native and ecosystem observations through the same
  manifest writer.
- IM-15 still owns the live Python/TypeScript/Rust/Go/mixed before/after,
  judgment, packet, rescan, diff, and ratchet CI proof.
- IM-16 still owns the accurate final ADR 0036/0040 embodiment update.

Current action: coordinator review, spec reconciliation, and integration with
the parser-backed lane. Last fully completed WP5 acceptance criterion: none.
