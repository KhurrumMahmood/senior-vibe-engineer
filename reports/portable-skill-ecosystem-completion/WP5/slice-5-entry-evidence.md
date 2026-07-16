# WP5 Slice 5 entry evidence — WP4 dependency gate

Evidence capture date: 2026-07-16

Gate execution revision:
`30bc3aca236f1281cfc181fce1e8fb8cc5bf3320`.

Functional implementation revision:
`644b94793f146008bc6b86e0be4df6f5d680ea09`.

Verified WP4 substrate revision:
`d1a6316f0c57abc5e2162c477d6d56f51165cf14`, tree
`0ab795ec7b6b19dfa987393530404f7e17e98bb6`.

This record covers only IM-12. The deterministic gate passed, so the
parser-backed WP5 members are dependency-ready. This record does not implement
or claim IM-13/IM-14, wire either ecosystem detector, promote support, or
complete any WP5 acceptance criterion.

## Machine-checked dependency decision

`scripts/check_wp5_wp4_entry_gate.py` fails closed unless all of these remain
true:

- the single authoritative WP4 tracker row is `verified`, still covers
  AC-4.1–AC-4.6, links the final clean verifier, names the exact clean
  `d1a6316` PASS, and explicitly hands parser-backed WP5 work forward;
- the final verifier is the genericized committed report from
  `f9ef09acb853fa6fcba400d6bd1d3131e04a7f6c`, not a pre-commit workspace
  digest, and its committed bytes and semantic PASS markers are unchanged;
- the exact verified revision/tree exists and is an ancestor of the current
  revision, every substrate/contract path is clean, and no such path changed
  after `d1a6316`;
- the tracker and all bound WP4 evidence paths are committed and clean;
- committed Darwin-arm64 and Linux-x86_64 evidence retains the required
  Python/Tree-sitter/tool matrix, deterministic source/stable hashes, passing
  budgets, and exact artifact hashes; and
- the fact/adapter/failure/golden tests, current-platform live benchmark, and
  executable cross-platform comparison all pass again. A metadata-only
  `--preflight-only` run deliberately returns `entry_allowed: false`.

The gate ignores unrelated dirty paths outside the authoritative WP4
dependency record and substrate contract. This was necessary because the
shared worktree contained active WP3 and WP5 native-provider lanes. It does
not weaken dirty-state protection: relevant dirty, untracked, post-revision,
missing, or hash-mismatched content fails the gate.

## Exact evidence binding

| Evidence | SHA-256 |
|---|---|
| committed genericized final verifier | `2008a818b90c627020de556283ac5e223902628b67f1ad88c0a6c935c9b0817f` |
| committed Darwin-arm64 report bytes | `9ed3d76ee0be2f77873f15ef06f9d6bfb05d98e630aa03596460b2fd94cce039` |
| committed Linux-x86_64 report bytes | `8a903bb629b0c27421362fb00faf4a5bfd97fde438ffcacea5f4194ea67c741d` |
| committed cross-platform matrix bytes | `3d6a39aa395ab4c97d64e69448b986427787547c8f589d23cb160f7f2935ad55` |
| committed adversarial comparison bytes | `732a4c20152f3450c976fb8df3f724e65b09060a23107576193528fd0c7c53ec` |
| fresh exact-revision D3 rerun bound by final verifier | `5c00dfb65530f4682ba038c6cdee59ca230488b9e09f2a25dd22a0225ff3abcd` |
| fresh exact-revision Darwin report bound by final verifier | `43d692aef80842deedbcb943134d0af5b8d93b640245968d66f5741e9a0261b5` |
| fresh exact-revision Linux report bound by final verifier | `20912a253093dfdd4d388f9e4e0b333f2e4bedee36221f51169dc600a7469af1` |
| fresh exact-revision forward/reverse matrix bound by final verifier | `d49b676842e747be253e287cb2b67db19a9cdcb33e7cdd92baae43e8e76c48e5` |
| fresh exact-revision adversarial replay bound by final verifier | `35ac05fd23115279fc8f0bab38a6d34f84dd905e36950d7c5122f44e34056319` |

The committed platform reports were created at `01874df5d8d73b5fc74bf7a6e04fa51936a694ff`.
The final clean verifier independently reran them at `d1a6316` and proved the
complete benchmark source scope did not change. Both old and fresh executions
share source-tree SHA-256
`92aca126917a35a078f4b3d40f72de46c2e707a4580def146094425cd4cc70f0`
and stable-result SHA-256
`a8c3596589629e79af1a601ae14c620ddb0d0127887225245c30d543311e7674`.

The required matrix is:

| Platform | Python | Tree-sitter | Language pack | Result |
|---|---:|---:|---:|---|
| Darwin-arm64 | 3.11.10 | 0.26.0 | 1.12.5 | PASS |
| Linux-x86_64 | 3.11.15 | 0.26.0 | 1.12.5 | PASS |

## Contract rerun

The full gate ran with the required explicit interpreter:

```text
.venv/bin/python scripts/check_wp5_wp4_entry_gate.py \
  > /tmp/wp5-wp4-entry-gate-final.json
exit 0; entry_allowed=true
```

The gate executed these three child contracts:

```text
.venv/bin/python -m pytest --override-ini addopts= -q \
  -p no:cacheprovider tests/test_analysis_facts.py \
  tests/test_lang_adapter.py tests/test_omnibus_language_adapters.py
65 passed in 1.61s; exit 0

.venv/bin/python scripts/analysis_fact_benchmark.py \
  --source-revision 30bc3aca236f1281cfc181fce1e8fb8cc5bf3320 \
  --output <temporary-live-platform-report>
{"passed": true, "violations": []}; exit 0

.venv/bin/python scripts/analysis_fact_benchmark.py \
  --compare-platform-reports \
  reports/portable-skill-ecosystem-completion/WP4/darwin-arm64.json \
  reports/portable-skill-ecosystem-completion/WP4/linux-x86_64.json \
  --output <temporary-rebuilt-matrix>
{"passed": true, "violations": []}; exit 0
```

The 65-test suite reran the versioned fact interface, Python/JavaScript/
TypeScript/Rust/Go adapters, all typed malformed/missing/broken/timeout/
unsupported failure paths, deterministic full-shape golden files, precise
locations, D3 outcome binding, and budget/comparator attacks. The current
Darwin-arm64 live report passed every budget and reproduced the verified
source-tree and stable-result hashes. The recomputed committed-platform matrix
was byte-identical to `platform-matrix.json`.

The original gate JSON SHA-256 was
`ec5857b0ad6a0ecf89dcecc64a18e819cd20a8f99e7dd1c8167197130f106a7b`.
Its live report was intentionally temporary because timing fields are
machine/run provenance; its SHA-256 was
`eb7db2b64a05b6940c64999571afb0946d40aa87289397c437a4d572251b4f03`.

## Gate implementation verification

```text
.venv/bin/python -m pytest --override-ini addopts= -q \
  -p no:cacheprovider tests/test_wp5_wp4_entry_gate.py
9 passed in 0.15s; exit 0

.venv/bin/ruff check \
  scripts/check_wp5_wp4_entry_gate.py tests/test_wp5_wp4_entry_gate.py
All checks passed!; exit 0
```

The fault tests reject a non-verified or weaker tracker handoff, changed final
report/fresh-artifact hashes, a missing platform, downgraded tool version,
stale stable-result hash, and any preflight-only attempt to claim entry.

## Environment and owned content

```text
macOS 26.5.1 (Darwin 25.5.0), arm64
Python 3.11.10
pytest 9.0.3
PyYAML 6.0.3
Tree-sitter 0.26.0
tree-sitter-language-pack 1.12.5
Runtime identity: Codex, GPT-5 based; exact deployed model variant and
reasoning-effort setting were not exposed. No Luna identity was shown or
claimed.
```

| Owned path | SHA-256 |
|---|---|
| `scripts/check_wp5_wp4_entry_gate.py` | `457b242c3542b15d58c096e9e5a5a2e3e9460af4106921a2e3e7826ff6f9d43b` |
| `tests/test_wp5_wp4_entry_gate.py` | `f6b36b4427d2aa4e2fd5bd7c62ceeebf90e7f941a4b537b3ca781c66a5160132` |

At capture, the shared worktree also contained unrelated agent-policy logs,
WP3 core-leakage fixtures/tests, and WP5 native registry/shim/adapters/fixtures
owned by other active lanes. This lane did not edit, remove, stage, or include
them. The gate itself proved the bounded tracker, WP4 evidence, substrate,
tests, fixtures, and WP4 spec scopes were clean.

Current action: IM-12 is complete and IM-13/IM-14 may now begin against only
the verified WP4 interface. Last fully completed WP5 acceptance criterion:
none.

## Shared-worktree interpreter repair

An isolated parser-member worktree exposed that the first gate revision
required a checkout-local `.venv`, contradicting the repository contract that
sub-agents may use an explicit shared virtualenv. Commits `5c9de34` and
`644b947` changed the check to require a real `pyvenv.cfg`-backed interpreter
without resolving its Python symlink to the base interpreter. The clean
committed `644b947` gate then reran all 65 contracts, the live Darwin budget,
and the deterministic matrix successfully; its JSON SHA-256 is
`aae1124495b44dcff6d20e4e20af01f29b3d89a4ba325e6830d45fd8b575d9a4`.
