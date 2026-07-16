# WP5 Slice 5 parser evidence — IM-13 / IM-14

Evidence capture date: 2026-07-16

Implementation base: `c7c2fb858329668b583162509f433ec3d5e1263c`.

Initial parser-member commit: `3525075a9026caa20fdec6310ed08354cdc8d1c2`.
The current content includes the subsequent fresh-context adversarial repair.

Verified WP4 substrate: `d1a6316f0c57abc5e2162c477d6d56f51165cf14`,
tree `0ab795ec7b6b19dfa987393530404f7e17e98bb6`.

This record covers only IM-13 and IM-14. It does not implement or claim the
native-provider runner, sweep CLI, judgment, status/dashboard, packet, harness,
final CI boundary, ADR embodiment, or any complete WP5 acceptance criterion.

## Entry gate

Before any edit, the full committed IM-12 gate ran with the shared explicit
interpreter and passed. `<shared-venv-python>` and `<shared-venv-ruff>` below
denote the main project's explicit `.venv/bin/python` and `.venv/bin/ruff`
executables supplied to this isolated worktree:

```text
<shared-venv-python> \
  scripts/check_wp5_wp4_entry_gate.py
entry_allowed=true
65 passed in 1.50s
live Darwin-arm64 benchmark passed
source_tree_sha256=92aca126917a35a078f4b3d40f72de46c2e707a4580def146094425cd4cc70f0
stable_result_sha256=a8c3596589629e79af1a601ae14c620ddb0d0127887225245c30d543311e7674
```

Two precautionary post-suite reruns later failed only the timing-variance
budget (`external_large warm_cv=0.227929`, then `small warm_cv=0.383611`, both
above `0.2`). The initial mandatory gate and its fact/failure/golden contracts
had already passed before implementation. No WP4 substrate path was edited;
the gate's preflight test remains green. The two later measurements are
recorded rather than presented as passing evidence.

## Delivered boundary

- `scripts/sweep/ecosystem.py` executes the exact recorded argv through the
  standalone `scripts/sweep/provider_process.py` child boundary, never through
  the historical prototype. The parent enforces the declared deadline and
  output ceiling, captures stdout/stderr to files, hashes the actual bytes, and
  emits schema-1 `provider_observation` records plus normalized `FindingInput`
  rows for the single manifest writer.
- Complexity retains the characterized six-pattern bad fixture and clean good
  fixture. Its typed compatibility-tree wrapper parses each file once and
  reuses that tree; malformed or corrupt output becomes a typed failure, not a
  skipped row or second parse.
- Omnibus now consumes verified `analysis.symbols` facts rather than the
  optional legacy `extract_symbols` result. The same library path drives its
  CLI, so each call walks once and the CLI JSONL is byte-equivalent to library
  serialization.
- Python and TypeScript omnibus records preserve adapter/language provenance,
  locations, detector metrics, and raw-output hashes. Eligible Python records
  retain prototype SHA1 IDs only as one-release `legacy_ids`; new TypeScript
  support invents no historical alias. Current identity remains ADR 0040 v2.
- Parser-backed support is closed to exactly Python and TypeScript. Rust and Go
  requests are rejected; mixed-manifest tests retain independent native-shim
  observations for Clippy and Go vet.
- A failed provider observation cannot be published as a complete manifest.
  Fault tests pass the same empty finding tuple through malformed Python and
  prove both parser members return `status=failed`, `tool_failure`, and
  `parse_failure` rather than completed clean zero.
- Missing, escaping, wrong-kind, empty-language, and otherwise ineligible
  scopes fail before detector execution. Timeout and an in-flight overflow kill
  the process group; overflow retains the actual oversized byte counts and
  hashes instead of discarding the artifact provenance.
- The manifest writer now rejects findings outside both declared paths and
  roots, findings under exclusions, out-of-range observation indexes, and
  indexes that do not identify the finding's provider/language in the sorted
  canonical provider array.

No `scripts/sweep/__init__.py` or `scripts/sweep_shims.py` edit was required,
minimizing overlap with native-provider work.

## Fixture and manifest results

| Fixture boundary | Completed parser observations | Manifest findings |
|---|---|---:|
| characterized complexity bad | `cx/python` | 6 |
| characterized complexity good | `cx/python` clean | 0 |
| single Python | `omnibus/python` | 1 |
| single TypeScript | `omnibus/typescript` | 1 |
| mixed Python/TypeScript/Rust/Go source root | `cx/python`, `omnibus/python`, `omnibus/typescript`; native `clippy/rust`, `go-vet/go` retained | 8 parser findings |
| malformed Python | failed `cx/python` and failed `omnibus/python` | 0, unpublishable |
| missing/ineligible scope | typed `schema_mismatch` provider failure | 0, unpublishable |
| forced timeout / 32-byte overflow | typed `timeout` / `output_overflow` with captured hashes | 0, unpublishable |

The TypeScript fixture uses ordinary exported ESM functions and typed const
arrows. Both single-language fixtures produce four genuine responsibility
clusters and `and_count=3`.

## Verification

```text
<shared-venv-python> \
  .claude/skills/find-complexity-hotspots/scripts/smoke.py
OK - 6 bad fixture findings, good fixture clean

<shared-venv-python> -m pytest \
  --override-ini addopts= -q -p no:cacheprovider \
  tests/test_analysis_facts.py tests/test_lang_adapter.py \
  tests/test_omnibus_language_adapters.py tests/test_sweep_manifest.py \
  tests/test_sweep_slice0_characterization.py \
  tests/test_sweep_ecosystem_members.py tests/test_wp5_wp4_entry_gate.py
114 passed in 4.64s

PYTHONDONTWRITEBYTECODE=1 \
<shared-venv-python> -m pytest \
  --override-ini addopts= -q -p no:cacheprovider
613 passed in 38.10s

<shared-venv-ruff> check \
  scripts/sweep/ecosystem.py \
  scripts/sweep/provider_process.py \
  scripts/sweep/schemas.py \
  .claude/skills/find-complexity-hotspots/scripts/detect.py \
  .claude/skills/find-omnibus/scripts/detect.py \
  tests/test_sweep_slice0_characterization.py \
  tests/test_sweep_ecosystem_members.py
All checks passed!

git diff --check
exit 0
```

The focused fault suite replays the recorded command and binds its exit code,
stdout/stderr bytes, lengths, and SHA-256 values to the observation. It also
forces deadline and byte-ceiling failures, attacks scope and provenance-index
binding, and counts exactly one Python parse per file. The network-denial test
replaces socket creation, DNS lookup, and
`urllib.request.urlopen` with raising functions while complexity plus Python
and TypeScript omnibus members complete deterministically. A bounded static
scan found no network or model import/call in the provider or detectors; the
only match is a literal omnibus risk-term list used to inspect source text.

`scripts/specs.py coverage portable-batch-sweep` reports IM-13 and IM-14 as
the expected two implementation-ahead items because this lane was explicitly
forbidden from editing the specification. Strict inventory remains `CLEAN`.

## Environment and content hashes

```text
macOS 26.5.1 / Darwin 25.5.0 arm64
Python 3.11.10
pytest 9.0.3
Tree-sitter 0.26.0
tree-sitter-language-pack 1.12.5
Runtime identity: Codex, GPT-5 based; exact deployed model variant and
reasoning-effort setting were not exposed. No Luna identity was shown or
claimed.
```

| Owned path | SHA-256 |
|---|---|
| `.claude/skills/find-complexity-hotspots/scripts/detect.py` | `994da1fbeeae9ae4acbdbff38d9eed38944baeda22aa09f45a2702682a1f99e5` |
| `.claude/skills/find-omnibus/scripts/detect.py` | `9b958bd4be514b69b19fbd53c7a37f7b1d85abde2639d9c8b3be0e96da6d457e` |
| `scripts/sweep/ecosystem.py` | `a2941acdd1305cb55afb4126c4a000b99f7e34f7461a5c3bac1f399b98f4332c` |
| `scripts/sweep/provider_process.py` | `14627da476bf0e07e42ce751d56fcd72fa577d94acaea147e0a145283c614a05` |
| `scripts/sweep/schemas.py` | `128c16cc2d846938c43a249fca33cf529338d0bbe4bde595ec5f302ae8a60e31` |
| `tests/fixtures/sweep/ecosystem/python/complexity.py` | `1ff81dc5c445dcc81069fbfd4ea434d4022a93bed2a276a00b9fb2293c1179ca` |
| `tests/fixtures/sweep/ecosystem/python/omnibus.py` | `7f3de5d357c01c55f550b3bfbf120f6447f12a71a3a1bb19c97540a361f2bb7b` |
| `tests/fixtures/sweep/ecosystem/typescript/omnibus.ts` | `a7553cf5473d399c8b4b1083f4d8025b5dc2ee9c9a9f3eb2e3ac3a43eb7df76a` |
| `tests/fixtures/sweep/ecosystem/rust/main.rs` | `16b6d261b88c5e3c4934f941ff87a9cd8ec03d690724e5c0d42c7c283a267461` |
| `tests/fixtures/sweep/ecosystem/go/main.go` | `98f8c8362a4725755100e40ff437f9c2c37aeabae8c58b3ae1d53ca502bf517b` |
| `tests/test_sweep_slice0_characterization.py` | `18c8c225d166131974f651cf5bc33307e21f2647e08b64a469c955e2b18bb572` |
| `tests/test_sweep_ecosystem_members.py` | `bce494379cf0e8be18834b6ab989644bb125b3403a145838b2a9d9def83ffef0` |

Current action: IM-13 and IM-14 are implementation-complete and ready for
coordinator integration. Last fully completed WP5 acceptance criterion: none.
