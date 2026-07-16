# WP3 Slice 1 evidence — catalog and placement contract

Generated at: `2026-07-16T18:04:05Z`
Implementation revision: `2f9711dd58ab6c64a21e7d7326b797c7f3188640`.
Platform: `macOS-26.5.1-arm64-arm-64bit`
Python: `3.11.10`; pytest: `9.0.3`; Ruff: `0.6.9`
Lane: `/root/wp3_slice1`
Agent/model visibility: Codex based on GPT-5. No more specific model variant
or reasoning-effort setting was exposed.

## Implemented boundary

- IM-1: a 76-row authoritative inventory and strict shared reader validate
  exact immediate-root discovery, canonical registry layer/binding IDs,
  current language/framework frontmatter, one primary layer/binding,
  readiness, rationale shape, concept-plus-binding placement, singleton
  language/framework/host shipping contracts, domain groups of at least three,
  and the explicit 14-row AR-3 de-flavor membership.
- IM-2: `skill_meta.py lint` consumes the inventory for the canonical skills
  root, and `/plan-skill` asks the frozen placement question at the authoring
  decision point. Inventory readiness is explicitly separate from capability
  support; 60 rows remain `deferred-to-wp8` and no row gains inferred
  `capability_contract`, `experimental`, or `verified` status.

No tracked skill root moved. No binding loader, installer, bundle, runtime
discovery, portfolio projection, or framework-leakage migration was started.
The inventory selects no domain layer.

## Test-first record

Before `scripts/_lib/skill_catalog.py` existed, this exact focused command was
run:

```text
.venv/bin/python -m pytest -q tests/test_skill_catalog_layers.py tests/test_skill_meta_jobs.py
```

It exited `2` during collection with two
`ModuleNotFoundError: No module named '_lib.skill_catalog'` errors. After the
implementation, the final focused command below exits cleanly.

## Final commands and output addresses

Each SHA-256 is over concatenated stdout then stderr bytes from the named
command.

| Command | Exit | Output bytes | Output SHA-256 | Result |
|---|---:|---:|---|---|
| `.venv/bin/python -m pytest -q tests/test_skill_catalog_layers.py tests/test_skill_meta_jobs.py tests/test_capability_consumers.py tests/test_skill_activation.py` | 0 | 99 | `c17cdd1fc0c5b21bdbf766ec9dd875b02df8885c8b76787ef41364ba556461dd` | `28 passed in 2.11s` |
| `.venv/bin/python scripts/skill_meta.py lint --strict --quiet` | 0 | 44 | `2badb5016d4f1cd99837de4e36bf24f4756cbbccdf13151085c26ee54427bb6b` | `OK — 76 skills, 76 declaring new contract` |
| `.venv/bin/python scripts/specs.py coverage portable-skill-layer-distribution` | 0 | 3045 | `bd99285e7f0063159e613bbc931fbba550ec09617fde68710fa87d31a1e9a579` | `2/30` implemented; zero checkmark lag, implementation-ahead, or orphan refs |
| `.venv/bin/python scripts/specs.py inventory-check portable-skill-layer-distribution` | 0 | 204 | `9f0a04ef0e2ade22f09025cb2f92bb983d5329e12752435aa9d180e975864965` | `Status: CLEAN`; no stubs |
| `.venv/bin/ruff check scripts/_lib/skill_catalog.py scripts/skill_meta.py tests/test_skill_catalog_layers.py tests/test_skill_meta_jobs.py` | 0 | 19 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` | `All checks passed!` |

## Input and implementation addresses

| Path | Bytes | SHA-256 |
|---|---:|---|
| `.claude/skills/_common/skill-catalog-inventory.yml` | 26,808 | `3c093210d9ee4c9c43677285238a01085a2489c8bfa6f4e5869d704ae4b31c7f` |
| `scripts/_lib/skill_catalog.py` | 16,977 | `3298148787b824deb04a0987960a1a96b4a913ad75a1aafd10a7270538f3f91f` |
| `tests/test_skill_catalog_layers.py` | 9,317 | `5da3a9481d438df145efe4121e98ea1e7b75b8d6fbe0246b6b951365b60f3dc5` |

The inventory result is 76 rows: 74 `core`, one `language`, one `framework`,
zero `domain`, and zero `host-overlay`; readiness is 15
`foundation-ready`, one `exemplar-ready`, 60 `deferred-to-wp8`, and zero
`inventory-only`.

## Remaining gaps

- The coordinator marked only IM-1 and IM-2 complete after the implementation
  commit and retained every later item as pending.
- The coordinator's integrated suite passed 549 tests after Slice 1 and WP5
  Slice 0 were present. Leakage-lint, move-gate, binding-selection, installer,
  and runtime-discovery acceptance still belong to later WP3 slices.
