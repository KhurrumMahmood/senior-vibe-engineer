# WP5 Slice 5 parser evidence — IM-13 / IM-14

Evidence capture date: 2026-07-16

Implementation base: `c7c2fb858329668b583162509f433ec3d5e1263c`.

Initial parser-member commit: `3525075a9026caa20fdec6310ed08354cdc8d1c2`.
The current content includes all three subsequent fresh-context adversarial repairs.

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
  combined output ceiling through the shared bounded nonblocking capture in
  `scripts/sweep/process.py`. It retains and hashes no more than the ceiling
  plus one byte, kills overflow promptly, and checks the deadline before
  accepting an observed completion. Timeout/overflow termination targets the
  process group even after its leader exits, so inherited descendants cannot
  survive. It emits schema-1 `provider_observation` records plus normalized
  `FindingInput` rows for the single manifest writer.
- Every successful child stream ends with exactly one canonical typed
  completion record containing schema, provider, language, and finding count.
  The parent requires it to be final and to match the parsed records; absent,
  duplicate, misplaced, or mismatched sentinels become `missing_completion`,
  including a zero-exit empty provider script.
- Complexity retains the characterized six-pattern bad fixture and clean good
  fixture. Its typed compatibility-tree wrapper parses each file once and
  reuses that tree; malformed or corrupt output becomes a typed failure, not a
  skipped row or second parse. Sweep execution requests the detector's uncapped
  result path; a 501-finding regression publishes all 501 rather than a capped
  successful prefix.
- Omnibus now consumes verified `analysis.symbols` facts rather than the
  optional legacy `extract_symbols` result. The same library path drives its
  CLI, so each call walks once and the CLI JSONL is byte-equivalent to library
  serialization. Its exported selection/count contract applies all intrinsic
  skips plus executed roots/exclusions; a directory containing only
  `test_only.py` fails typed instead of becoming clean zero.
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
  scopes fail before detector execution. Complexity eligibility uses the
  detector's exact shared file-selection helper, so direct test files and
  directories containing only detector-excluded files fail loudly. Timeout and
  an in-flight overflow kill the process group; overflow retains and hashes the
  bounded prefix rather than allocating or writing unbounded output.
- The manifest writer now rejects findings outside both declared paths and
  roots, findings under exclusions, out-of-range observation indexes, and
  indexes that do not identify the finding's provider/language in the sorted
  canonical provider array. Every provider observation records canonical
  executed paths, roots, exclusions, and case policy; that exact object is
  passed to the child and enforced during file selection. Publication requires
  manifest scope equivalence (rather than inferred argv/global coverage) and
  rejects excluded findings, narrowed roots, case disagreement, and findings
  outside their own bound observation scope.

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
| direct test-only / directory-only-excluded complexity scope | typed `schema_mismatch` provider failure | 0, unpublishable |
| omnibus directory containing only `test_only.py` | typed `schema_mismatch` provider failure | 0, unpublishable |
| uncapped 501-finding complexity source | `cx/python` | 501, publishable without truncation |
| absent/duplicate/misplaced/mismatched completion | typed `missing_completion` provider failure | 0, unpublishable |
| mismatched/excluded executed scope | typed provider failure or manifest rejection | 0, unpublishable |
| forced timeout / 32-byte overflow | typed `timeout` / `output_overflow` with bounded-prefix hashes | 0, unpublishable |
| timeout/overflow after leader exit | descendant process group killed | no survivor |

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
126 passed in 4.08s

PYTHONDONTWRITEBYTECODE=1 \
<shared-venv-python> -m pytest \
  --override-ini addopts= -q -p no:cacheprovider
625 passed in 36.60s

<shared-venv-ruff> check \
  scripts/sweep/ecosystem.py \
  scripts/sweep/process.py \
  scripts/sweep/provider_process.py \
  scripts/sweep/manifest.py \
  scripts/sweep/schemas.py \
  .claude/skills/find-complexity-hotspots/scripts/detect.py \
  .claude/skills/find-omnibus/scripts/detect.py \
  tests/test_sweep_slice0_characterization.py \
  tests/test_sweep_ecosystem_members.py \
  tests/test_sweep_manifest.py
All checks passed!

git diff --check
exit 0
```

The focused fault suite replays the recorded command and binds its exit code,
stdout/stderr bytes, lengths, and SHA-256 values to the observation. It also
forces deterministic deadline-race and byte-ceiling failures, kills inherited
descendants after their leader exits, faults every completion-sentinel shape,
attacks exact executed scope plus provenance-index binding, proves all 501
complexity findings cross the manifest boundary, and counts exactly one Python
parse per file. The network-denial test
replaces socket creation, DNS lookup, and
`urllib.request.urlopen` with raising functions while complexity plus Python
and TypeScript omnibus members complete deterministically. A bounded static
scan found no network or model import/call in the provider or detectors; the
only match is a literal omnibus risk-term list used to inspect source text.

`scripts/specs.py coverage portable-batch-sweep` reports IM-13 and IM-14 as
the expected two implementation-ahead items because this lane was explicitly
forbidden from editing the specification. Strict inventory remains `CLEAN`.
Capability-consumer, skill, decision, plan, and decision-link guards passed.
The repository-wide spec audit retained its pre-existing unrelated
`status-projection-and-presentation` orphan drift and exited 1; the WP5 spec's
own coverage and strict inventory checks passed, with only the expected
IM-13/IM-14 implementation-ahead entries.

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
| `.claude/skills/find-complexity-hotspots/scripts/detect.py` | `3f066946bf931111f9c6139257e0410d0eaaab0eaba21612579c867cb9e0267e` |
| `.claude/skills/find-omnibus/scripts/detect.py` | `53631a1efdbe81b04206618d7459b09299c6d09ef3866c508de8dec66b8d3747` |
| `scripts/sweep/ecosystem.py` | `31485cc61b0180e81bc54371f6ef466f44931a43f17ac43e63214fb232a9005d` |
| `scripts/sweep/process.py` | `53887726b7fd3aa1ce93a324fc6c2129a38760c93cd990bb75632ff9feb14e3f` |
| `scripts/sweep/provider_process.py` | `14627da476bf0e07e42ce751d56fcd72fa577d94acaea147e0a145283c614a05` |
| `scripts/sweep/manifest.py` | `f7edf474d515e976ccba70b0aaf9182fece2eb6d9e7a111ab745acac8151345a` |
| `scripts/sweep/schemas.py` | `542a295a792319efba40f45ead04cd28accbef9b335ea624884f4e07600e3d7f` |
| `tests/fixtures/sweep/prototype-oracle/schema-cases.json` | `66b56b41ed6da2f17cf2aaeb8812bfc932fde9d68e5031f116611ece7e9d8355` |
| `tests/fixtures/sweep/ecosystem/python/complexity.py` | `1ff81dc5c445dcc81069fbfd4ea434d4022a93bed2a276a00b9fb2293c1179ca` |
| `tests/fixtures/sweep/ecosystem/python/omnibus.py` | `7f3de5d357c01c55f550b3bfbf120f6447f12a71a3a1bb19c97540a361f2bb7b` |
| `tests/fixtures/sweep/ecosystem/typescript/omnibus.ts` | `a7553cf5473d399c8b4b1083f4d8025b5dc2ee9c9a9f3eb2e3ac3a43eb7df76a` |
| `tests/fixtures/sweep/ecosystem/rust/main.rs` | `16b6d261b88c5e3c4934f941ff87a9cd8ec03d690724e5c0d42c7c283a267461` |
| `tests/fixtures/sweep/ecosystem/go/main.go` | `98f8c8362a4725755100e40ff437f9c2c37aeabae8c58b3ae1d53ca502bf517b` |
| `tests/test_sweep_slice0_characterization.py` | `18c8c225d166131974f651cf5bc33307e21f2647e08b64a469c955e2b18bb572` |
| `tests/test_sweep_ecosystem_members.py` | `4a261f732a031550b986671e657a663010feedc6a11a70e2a915250ef235357f` |
| `tests/test_sweep_manifest.py` | `c409ccf90a79bcc47125e72b432160a1dd6d29a6d0b1e96f03aa7b889472aa74` |

Current action: IM-13 and IM-14 are implementation-complete and ready for
coordinator integration. Last fully completed WP5 acceptance criterion: none.
