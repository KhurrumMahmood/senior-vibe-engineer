# WP5 Slice 1 evidence — manifest core and identity migration

Evidence capture date: 2026-07-16

Functional implementation revision:
`b93c196954c580b7eee9cb7dfef36ef93739622b`.

This record covers only IM-3 and IM-4. It advances the manifest/identity
portions of AC-5.1 and AC-5.4 but does not claim either acceptance criterion,
or WP5 as a whole, complete. It does not cross the WP4 gate or start CLI,
provider, judgment, consumer, harness, or parser-backed slices.

## Delivered boundary

- `scripts/sweep/manifest.py` is the sole current sweep-manifest producer. It
  assigns ADR 0040 identity-v2 occurrences after deterministic source-order
  sorting, retains the full canonical payload, rejects unequal-payload digest
  collisions, requires an explicit case policy, and emits schema 1 only.
- The producer retains native rule IDs separately from explicit canonical rule
  semantic keys. Tool-version and line-only changes preserve finding identity;
  a semantic-key revision produces fixed plus new.
- Manifest writes are canonical, terminal-newline JSON and atomically replace
  the destination. Semantic and artifact hashes are derived by the producer;
  current-schema reads reject content not bound by those hashes.
- Prototype migration is explicit and closed: the only accepted old shape is
  the unversioned characterized prototype, every provider language and rule
  semantic version must be supplied, failed prototype runs are rejected, and
  each 12-character prototype ID is retained as a one-release `legacy_ids`
  alias. All subsequent writes are schema 1 / finding identity 2.
- Alias-aware set comparison returns deterministic fixed/new/persisting sets.
  A unique path-move alias persists under the new ID. Duplicate, ambiguous,
  current-ID, cyclic (including multi-hop), many-to-one, and cross-payload
  aliases fail rather than deduplicate findings.
- The schema-1 reader repeats the writer's alias uniqueness/current-ID checks,
  so a hand-authored document cannot bypass the canonical producer boundary.

No provider subprocess, CLI, digest presentation, ratchet mutation, judgment,
packet, consumer, harness, network/model, or parser detector behavior was
added.

## Property and adversarial coverage

`tests/test_sweep_manifest.py` covers:

- all 24 input permutations of four equal-anchor anonymous occurrences;
- forced 96-bit public-ID collisions with unequal canonical payloads;
- required case policy and both sensitive/insensitive case-only path changes;
- normalized and renamed paths, with rename continuity only through a unique
  payload-compatible alias;
- tool upgrades/line drift versus semantic-rule revisions;
- duplicate, ambiguous, current-ID, direct-cycle, multi-hop-cycle,
  many-to-one, and cross-payload aliases;
- canonical atomic schema-1 writing and stale semantic-hash rejection;
- synthetic and copied six-finding prototype migration with every v1 alias;
- schema-1 reads, explicit unversioned migration, and future-version failure.

## Verification

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
      tests/test_sweep_manifest.py tests/test_sweep_slice0_characterization.py \
      tests/test_finding_identity.py tests/test_capability_consumers.py
    39 passed in 0.24s

    .venv/bin/ruff check scripts/sweep tests/test_sweep_manifest.py
    All checks passed!

    .venv/bin/python scripts/specs.py inventory-check portable-batch-sweep
    Status: CLEAN

    .venv/bin/python scripts/specs.py coverage portable-batch-sweep
    Summary: 2/28 implemented; 2 implementation-ahead refs (IM-3 and IM-4)

After coordinator review, IM-3 and IM-4 are checked in the controlling spec;
coverage is expected to report 4/28 implemented with no implementation-ahead
references.

## Environment and content addresses

```text
macOS 26.5.1, arm64
Python 3.11.10
Ruff 0.6.9
Model: GPT-5 Codex; model variant and effort setting were not visible.
```

| Owned implementation path | Bytes | SHA-256 |
|---|---:|---|
| `scripts/sweep/__init__.py` | 1,120 | `09c55ecfb112af99a980dc4f97bf56101134b064694a159d7fe2074a03d1d0f7` |
| `scripts/sweep/schemas.py` | 25,933 | `7ba143406f18e9c291b9e5838113a4e42162b33c71e32457f764eed0182fba6f` |
| `scripts/sweep/serialization.py` (unchanged dependency) | 1,119 | `60279b553ed5f78864dfa76a09ad453089174f415da0f7e93e4afceed9e0d950` |
| `scripts/sweep/manifest.py` | 21,643 | `a0296abdd1ce7ba8b039d06a09b189b11efb503089482160ceaa0c0a45c41a8a` |
| `tests/test_sweep_manifest.py` | 14,639 | `683b822379b99bfdd3d7bb44e691dcacb4cb5cd3c924c426c39c3c913cc78ce7` |

At capture time the shared worktree also contained unrelated agent-policy log
changes and WP3 fixture/test work. This lane did not edit or include those
paths. The coordinator verified that the committed implementation at
`b93c196` retains every content hash above.

## Deferred by design

- IM-5 through IM-11 remain open: native provider execution/faults, public
  commands, bounded digests, ratchet/accepts, judgments, consumers, packets,
  and harness-owned verification are not part of this slice.
- IM-12 through IM-16 remain gated by the controlling WP4 verification order.
- The current alias window supports prototype v1 IDs and v2 move aliases; a
  future finding-identity schema requires its own documented migration.
- No master plan/spec checkmark, ADR status/embodiment, WP3/WP4 artifact,
  status/queue consumer, or commit was changed by this lane.

Current action: Slice 1 implementation and focused verification complete;
await coordinator reconciliation. Last fully completed WP5 acceptance
criterion: none (IM-3/IM-4 are implementation items, not standalone ACs).
