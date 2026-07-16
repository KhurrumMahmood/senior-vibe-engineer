# WP3 Slice 4 evidence — binding selection and exemplar

Generated at: `2026-07-16T19:27:01Z`
Working-tree base revision: `b91a759470cddad5523ecca7efe6e74b5b133028`.
Platform: `Darwin-25.5.0-arm64`.
Python: `3.11.10`; pytest: `9.0.3`; Ruff: `0.6.9`.
Lane: `/root/wp3_binding_exemplar` in isolated worktree
`/tmp/engineering-skills-wp3-binding` on `codex/wp3-binding`.
Agent/model visibility: Codex based on GPT-5. No more specific model variant,
reasoning-effort setting, or launcher model selector was exposed.

## Implemented boundary

- IM-7: `scripts/_lib/binding_loader.py` validates the canonical host profile,
  catalog-declared binding IDs, and registry kind/layer/language/framework
  contracts. It evaluates each profile root independently in exact
  `core -> language -> framework -> domain -> host` order. Unknown,
  undeclared, duplicate, incompatible, same-precedence ambiguous, and required
  zero-match selections fail closed. Explicit choices are root-keyed; aggregate
  stack, registry insertion order, and directory order are never tiebreakers.
- The loader reads only the canonical core and declared one-level binding
  documents. It content-deduplicates normalized rendered blocks and returns
  deterministic evidence containing relative root/skill/source identities,
  canonical profile/registry/declaration hashes, ordered overlay hashes,
  deduplicated block hashes, and the rendered hash. No temporary absolute path
  appears in evidence.
- IM-8: `/extract-enum` retains its name and canonical
  `.claude/skills/extract-enum/` root. `SKILL.md`, the profiler brief, and risk
  context now contain only the closed-vocabulary, wire-identity, classification,
  one-target, read-only, and stop invariants. `bindings/python.md` owns Python
  collection mechanics; `bindings/django.md` owns `TextChoices`, migration,
  distinct-value audit, and final renderer mechanics. Inventory metadata is
  honestly `language:any/framework:any` with declared `core,python,django`
  bindings.
- The existing collector route and target grammar are unchanged. Its output is
  additively extended with statically resolved declared choices, and annotated
  function parameters now participate in the existing conservative model
  attribution. The invalid Form-A route still exits 2 before scanning and emits
  the exact prior error.
- IM-9: `scripts/propose.py` renders the final `proposal.md` and a structured
  `semantic.json`, then compares it to the materialized AR-7 oracle. The
  comparator permits only AR-8 temporary-root, timestamp/scan-ID, Markdown
  whitespace, and explicitly irrelevant-table-order normalizations. Dedicated
  negative evidence proves a missing literal and changed wire value remain
  semantic failures.

No skill root moved. No five-surface projection, installer, bundle, portfolio,
ADR status/embodiment, successor-spec checkmark, or master-tracker status was
edited.

## Test-first record

Before the loader existed, this command was run:

```text
.venv/bin/python -m pytest -q \
  tests/test_binding_loader.py tests/test_extract_enum_binding.py
```

Collection failed with
`ModuleNotFoundError: No module named '_lib.binding_loader'`. After the loader,
split, and final renderer landed, the focused acceptance command below passes
33 tests.

## AR-7/AR-8 reconciliation and final boundary

The committed fixture is byte-bound to the authoritative characterization:

| Input | SHA-256 |
|---|---|
| `tests/fixtures/wp3/extract-enum/django/app/models.py` | `abcedb51dab2814f7b8d9b3c99c10d5c9c74efd782f8352397dd25ef5eb1a3bd` |
| `tests/fixtures/wp3/extract-enum/django/app/services.py` | `6bbea6f11b8036fa1730d8c957da195ca374ec2a128b9eef8ea206cb3ef7e93b` |

The service hash resolves to the semantically identical expanded-function
format (one function body per indented line); this is the authoritative digest
recorded by AR-7 rather than the report's compact display formatting.

The characterized compact semantic digest `75feed33...` was recorded without
retaining its source JSON bytes. Slice 4 therefore materializes every pinned
AR-7 fact as the reviewable oracle
`tests/fixtures/wp3/extract-enum/ar7-semantic-oracle.json` instead of claiming a
byte preimage for an unavailable serialization. Both the produced semantics
and that oracle compact to SHA-256
`9e92b4212489e32d94a752e158202ecf129ea19cb12a7ee55c0fbdb32077fb3b`.
The exact semantic equality covers target/path/symbol and kwargs; five literal
identities/counts; four comparisons, one assignment, one caller; confirmed,
case-risk, bridge, assignment, and empty-dynamic classifications; ordered
members/wire values; all three risks; and the closed four-part stop decision.

Final replay output:

```text
[collect_extract_enum] wrote /tmp/wp3-binding-replay/targets.json: Job.status —
5 literals (1 case-variants) across 1 files (4 comparisons, 1 assignments)
semantic equivalence: clean
```

| Final artifact | SHA-256 |
|---|---|
| `targets.json` | `b06dc1aa55565e19ebf08ef300a07fa4bd4c2368a807107aa1befbaab9a59244` |
| `proposal.md` | `0556104e4822a9332855f9876a23fcdc75ee98c8a15cdfc8a14f2e8ccf996d47` |
| `semantic.json` | `4efb8c70dabedd06ea2bcec734451b79f0923d246474fcffbbae50d21b93ceee` |
| `normalization.json` | `52291b6e0c9c5ab96bfaa7c02b4d87f33da74cddda1282f51d2f2b684128b7f3` |

`normalization.json` records the four allowed categories, `applied: []`, and
`equivalent: true`.

## Final verification

Each output SHA-256 is over concatenated stdout then stderr bytes.

| Command | Exit | Output SHA-256 | Result |
|---|---:|---|---|
| focused binding/exemplar/leakage suite | 0 | `8c55a65fe547c46b5bd20a19c302955042153b267141db03959a42b6b909abce` | `33 passed in 2.12s` |
| full indexed top-level test half 1 | 0 | `b247148f5ead5369fafa4b76e6bff4492d8f7031f98bf65a9542812468b73429` | `284 passed in 9.15s` |
| full indexed top-level test half 2 | 0 | `223a7a5969a68249552a5a2ea09b0ca53be2db8b07d5883fdbcd7005c0b7a0c5` | `297 passed in 24.33s` |
| nested test modules | 0 | `e20ab3c005e6265f5cfdf8d458441e6320feee9db143a6f1e498786e2eaa7eec` | `33 passed in 3.23s` |
| Ruff on every changed Python path | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` | `All checks passed!` |
| `scripts/lint/no_core_framework_leakage.py --all` | 0 | `6df16c0b74d1f968af620b51b591d947d64f292fd9a2694388ee10fcd95d245a` | 16 migrated core skills clean, including the exemplar |
| `scripts/skill_meta.py lint --strict --quiet` | 0 | `2badb5016d4f1cd99837de4e36bf24f4756cbbccdf13151085c26ee54427bb6b` | 76/76 contracts clean |
| `scripts/specs.py inventory-check portable-skill-layer-distribution` | 0 | `9f0a04ef0e2ade22f09025cb2f92bb983d5329e12752435aa9d180e975864965` | clean; no stubs |

The three test partitions cover all 614 collected tests exactly once: 581
indexed top-level tests (including 14 new Slice 4 tests) and 33 nested tests. The direct
one-shot suite exceeded the app command's bounded execution window, so it was
replayed in deterministic tracked-file partitions rather than treated as
unverified.

## Principal content addresses

| Path | SHA-256 |
|---|---|
| `scripts/_lib/binding_loader.py` | `ac0afacb775c7d62a9b1eac45b8cdbfb68adec6c50e02801d5b1877d754cd509` |
| `.claude/skills/extract-enum/SKILL.md` | `3119909025d8d6fe5e9d4284622c9d71b38ca7dc74e4c5eec391db24f15a1d14` |
| `.claude/skills/extract-enum/bindings/python.md` | `b26c1fc1e2747b3689693fb7ca5510e240d823903e532dd3f8a8c0cd1fc0e4bb` |
| `.claude/skills/extract-enum/bindings/django.md` | `c203cb19981e75525bf1026277f837887045cf6566662c59768de198335d4594` |
| `.claude/skills/extract-enum/scripts/collect.py` | `8d9e4964879b2ef0ca9f17dce44484c99490cb630908aad04dc2be8062653730` |
| `.claude/skills/extract-enum/scripts/propose.py` | `b967e57d5987ec121e8a031a555ac7a0abcf556a2509e9a16a5a1f4adb8343c1` |
| `tests/test_binding_loader.py` | `35a90d6f45c3861b5a250d31483a0050b23b25457446d315eb9785038199190c` |
| `tests/test_extract_enum_binding.py` | `80bb3610da81d16d5e509d3111577ad47238e30012b69468c4998ed221e1b248` |
| `tests/fixtures/wp3/extract-enum/ar7-semantic-oracle.json` | `1c9963e77b7733159c2da610f23c72f137ef113fc08fe786772dd75eb73a3efd` |

The hashes above were captured after implementation and test finalization; the
self-referential evidence report is intentionally not content-addressed here.
