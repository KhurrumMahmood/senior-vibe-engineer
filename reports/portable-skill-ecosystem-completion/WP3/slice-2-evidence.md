# WP3 Slice 2 evidence — early-move safety gate

Generated at: `2026-07-16T18:32:48Z`
Working-tree base revision: `f9ef09acb853fa6fcba400d6bd1d3131e04a7f6c`.
Functional implementation revision: `a0d9fa9785e12186c95bd676126a5eb51342f608`.
Platform: `Darwin-25.5.0-arm64`
Python: `3.11.10`; pytest: `9.0.3`; Ruff: `0.6.9`
Lane: `/root/wp3_move_gate`
Agent/model visibility: Codex based on GPT-5. No more specific model variant
or reasoning-effort setting was exposed.

## Implemented boundary

- IM-3: `scripts/wp3_move_gate.py` is a blocking, safety-only validator. It
  derives tracked renames and the complete non-deleted diff from Git; invokes
  the existing concept-divergence scanner over explicit bounded roots; records
  the exact command, stdout, stderr, exit, and both required bands; validates
  scoped glossary `avoid:` phrases and substantive per-file prose review; and
  requires complete pre/post self-anchor inventory, target pins, file/directory
  types, and tractable rewrite or unhandled reviewer notes.
- The same gate runs one import-and-typed-asset smoke per declared move batch,
  then independently scans every changed Python file for self-anchors and
  missing or wrong-type disk targets. A hashed acknowledgment binds review to
  the move tool's ambiguous-prose/unsupported-import non-rewrite list and
  explicitly acknowledges its undocumented/unrewritten self-anchor gap.
- Fired primary rules must exactly match structured
  `[wp3-move-gate:<rule>] Cause: ... How: ...` entries in the declared running
  lessons log before a failing evidence packet is complete.
- IM-4: the dedicated fixture moves `foundation/runner.py` one level deeper.
  The good variant re-derives the parent walk. The blocking variant retains
  `legacy worker` prose and leaves the old parent walk, so the exact
  `avoid_term_hit`, target-mismatch, and missing-disk-target rules fire.
  Separate tests prove identifier-only cleanup and an `exists()`-only
  directory-for-file smoke cannot pass. A reviewed computed-segment fixture
  proves explicitly pinned unhandled shapes remain tractable to the process.

No skill path was moved. No ADR, master plan, successor spec, status, or
`embodied_by` field was changed. This slice does not claim WP5/WP7 embodiment
or formal ADR disposition.

## Test-first record

Before `scripts/wp3_move_gate.py` existed, this focused command was run:

```text
.venv/bin/python -m pytest -q tests/test_wp3_move_gate.py
```

It failed `8/8`; seven failures were `FileNotFoundError` while importing the
absent gate and the CLI case exited `2` because the script did not exist. After
implementation and the reviewed-unhandled/direct-expression cases were added, all ten dedicated
tests pass.

## Final commands and output addresses

Each SHA-256 is over the command's combined captured stdout/stderr bytes.

| Command | Exit | Output bytes | Output SHA-256 | Result |
|---|---:|---:|---|---|
| `.venv/bin/python -m pytest -q tests/test_wp3_move_gate.py tests/test_move_path.py` | 0 | 99 | `a937c1cbd8890700708808c66dfe15d563d0d9898a70872c4af067e7bd5b8a70` | `21 passed in 2.39s` |
| `.venv/bin/ruff check scripts/wp3_move_gate.py tests/test_wp3_move_gate.py` | 0 | 19 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` | `All checks passed!` |
| `.venv/bin/python scripts/specs.py inventory-check portable-skill-layer-distribution` | 0 | 204 | `9f0a04ef0e2ade22f09025cb2f92bb983d5329e12752435aa9d180e975864965` | `Status: CLEAN`; no stubs |

## Input and implementation addresses

| Path | Bytes | SHA-256 |
|---|---:|---|
| `scripts/wp3_move_gate.py` | 37,958 | `c2dd5e98aec04ef580924384db756001d6f3988c476743e6273bd3d5f8a04936` |
| `tests/test_wp3_move_gate.py` | 12,476 | `f9c60cdf3a668c7f066037ce44a7a2f7a49b9d182cb54b92be1052ece032c504` |
| `tests/fixtures/wp3/move_gate/common/.claude/contracts/concepts.yaml` | 228 | `f7fca26b24a5c4a2c808b64d86e5eb39be149108dc768929e86532d343710385` |
| `tests/fixtures/wp3/move_gate/common/.claude/skills/move-path/SKILL.md` | 227 | `fac3c7a6bb707daf85b501ff1c506eb91efa9d2465289dbce5410ce4161313ba` |
| `tests/fixtures/wp3/move_gate/common/foundation/assets/prompt.txt` | 16 | `8bc94a9ac44d3f93c6b9e2ac2a102cab0fb5631033335abac8116da3bb4f2a55` |
| `tests/fixtures/wp3/move_gate/before/foundation/runner.py` | 226 | `790ad85805a2e5dac17615bffbc9c1af31b8f7fe14d8861fb4ec11acd6040a66` |
| `tests/fixtures/wp3/move_gate/good/foundation/scripts/runner.py` | 236 | `6a9ee0f72cf92795747b066c3120f05d4c4fc5f34e67953eb3fe1d2767389d97` |
| `tests/fixtures/wp3/move_gate/bad/foundation/scripts/runner.py` | 226 | `bda366efe19948bcb1bdfbedec2372e6d8d2e9adecb700d8956cd7f91fdd0a19` |

After coordinator review, IM-3 and IM-4 are checked in the controlling spec.
The master ledger remains coordinator-owned.
