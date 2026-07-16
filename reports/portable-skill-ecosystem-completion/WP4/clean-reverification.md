# WP4 clean re-verification — PASS

Verifier: `/root/wp4_clean_reverification`, Codex/GPT-5. The exact deployed
model variant and reasoning-effort setting were not exposed by the runtime.

Verified revision:
`d1a6316f0c57abc5e2162c477d6d56f51165cf14`, tree
`0ab795ec7b6b19dfa987393530404f7e17e98bb6`.

Overall: **PASS**. AC-4.1 through AC-4.6 pass independently, and the mandatory
clean exact-revision full suite passes 549/549. Every retained attempt-1
parser/routing/failure attack and every attempt-3/4 evidence-integrity attack
was replayed. No required check was unavailable and no WP4 claim remains
unsupported.

## Workspace and verification isolation

The shared worktree was clean at verification start:

```text
git status --porcelain=v1
<empty>
git rev-parse HEAD^{commit} HEAD^{tree}
d1a6316f0c57abc5e2162c477d6d56f51165cf14
0ab795ec7b6b19dfa987393530404f7e17e98bb6
```

All executable acceptance checks ran in new exact-revision checkouts:

- Darwin: `/tmp/wp4-clean-d1a6316.XGmD1K`, a local no-local clone detached at
  `d1a6316...`.
- Linux: `/tmp/wp4-clean-d1a6316.8TWqNS/checkout` inside the
  `wp4-linux-x86` Lima VM, cloned from a new Git bundle and detached at
  `d1a6316...`.

Both exact-revision checkouts ended with empty `git status --porcelain=v1`.
The shared live worktree acquired concurrent WP3/WP5 work while verification
ran. Immediately before this report was written, its foreign end-state was:

```text
 M logs/agent_policy/test_runs.jsonl
 M scripts/sweep/__init__.py
 M scripts/sweep/schemas.py
?? logs/agent_policy/friction.jsonl
?? scripts/sweep/manifest.py
?? scripts/wp3_move_gate.py
?? tests/fixtures/wp3/
?? tests/test_sweep_manifest.py
?? tests/test_wp3_move_gate.py
```

Those paths were not WP4 inputs and were neither changed nor removed by this
verifier. This report is the verifier's only intentional repository write;
all other verifier artifacts are under `/tmp`.

At final verifier status capture, the shared worktree additionally contained
the verifier-owned untracked `clean-reverification.md` and the concurrently
created foreign untracked
`reports/portable-skill-ecosystem-completion/WP5/slice-1-evidence.md`. Both
exact-revision verification checkouts still had empty porcelain status.

Darwin environment: macOS 26.5.1 / Darwin 25.5.0 arm64, Apple M1, Python
3.11.10, pytest 9.0.3, PyYAML 6.0.3, Tree-sitter 0.26.0, and
tree-sitter-language-pack 1.12.5.

Linux environment: Ubuntu 22.04.5 / Linux 5.15.0-185 x86_64, Python 3.11.15,
Tree-sitter 0.26.0, and tree-sitter-language-pack 1.12.5 under Lima 2.1.4 / QEMU
with four vCPUs. Immediately before the Linux benchmark, guest load was
0.16/0.06/0.02; no repository test, benchmark, `rg`, or `find` process was
running. The host had ordinary UI/agent processes but no unbounded scan or
test workload; QEMU itself was at 2.5% before the measurement.

Command aliases below are exact path abbreviations: `<venv-python>` and the
Darwin `<python-3.11>` are
`<repo>/.venv/bin/python`; the Linux
`<python-3.11>` is
`/tmp/wp4-final-a1cec-linux-v1/.venv/bin/python`; and the fresh D3 `<tmp>` is
`/tmp/wp4-d3-d1a6316.92p5QX`.

## Mandatory clean full-suite gate — PASS

Exact command in the clean Darwin checkout:

```text
PYTHONDONTWRITEBYTECODE=1 \
<repo>/.venv/bin/python \
  -m pytest --override-ini addopts='' -q -p no:cacheprovider
549 passed in 29.71s; exit 0
```

The same suite first ran with the repository's ordinary quiet configuration
and also exited 0. `--collect-only` reported 549 tests. The override was used
only to expose pytest's otherwise suppressed final count.

### Revision-shape-independent `/which-cleanup` proof — PASS

The repaired module passed without skips:

```text
PYTHONDONTWRITEBYTECODE=1 <venv-python> -m pytest -vv \
  -p no:cacheprovider tests/scripts/test_which_cleanup.py
17 passed in 1.52s; exit 0
```

Inspection confirms both former `HEAD~1` cases call `_changed_project()`.
That helper initializes its own temporary Git repository, commits a baseline,
then changes exactly three files for the `small` boundary or 25 files for the
`large`/`--emit-plan` boundary. The outer repository is passed only as the
location of the executable under test; it no longer supplies the diff.

The two integration cases were then rerun in three independently materialized
outer Git histories:

| Outer history | Latest revision shape | Result |
|---|---|---|
| `/tmp/wp4-shape-root.26uhVg`; one root commit; `HEAD~1` absent | root only | 2 passed, 15 deselected |
| `/tmp/wp4-shape-trivial.gOfaAO`; two commits | one empty file in latest commit | 2 passed, 15 deselected |
| `/tmp/wp4-shape-large.u4vUXR`; two commits | 25 files in latest commit | 2 passed, 15 deselected |

All three returned the fixture-pinned `small` and `large` outcomes. This
directly proves the tests no longer depend on the checkout's revision shape.

## Acceptance criteria

### AC-4.1 — PASS

The contract advertises interface version 1 and exactly these universal fact
families: `analysis.symbols`, `analysis.imports`, `analysis.definitions`,
`analysis.references`, `analysis.calls`, and `analysis.writes`. Facts and
results are immutable and location-bearing; every provider exposes language,
extensions, interface/provider versions, and discoverable capabilities.
Python's syntax tree remains a compatibility-only capability. A bounded search
found 25 imports: two adapter-package declarations, two benchmark consumers,
and the same 21 production consumers pinned by the baseline. A search for
route/Django/React/framework facts in `scripts/_lib/lang_adapter` returned no
matches.

### AC-4.2 — PASS

The selected Tree-sitter provider is runtime code and exact dependencies are
pinned. A fresh deterministic installation and D3 rerun used:

```text
<venv-python> -m pip install --target <tmp>/python \
  tree-sitter==0.26.0 tree-sitter-language-pack==1.12.5
npm install --prefix <tmp>/node @ast-grep/cli@0.44.1 \
  typescript-api@npm:typescript@5.9.3 typescript@7.0.2
<venv-python> scripts/analysis_portfolio_spike.py \
  --python-site <tmp>/python --node-modules <tmp>/node/node_modules \
  --output /tmp/wp4-clean-results.Tchbgi/d3-d1a6316.json
exit 0
```

Fresh D3 results:

| Candidate | Precision / recall | Warm | Install | License | Result |
|---|---:|---:|---:|---|---|
| Tree-sitter 0.26.0 + pack 1.12.5 | 1.0 / 1.0 | 0.055522s | 5,089,280 B | MIT | PASS |
| ast-grep 0.44.1, optional | 1.0 / 1.0 | 0.086174s | 154,339,105 B | MIT | PASS |
| TypeScript Compiler API 5.9.3 | 1.0 / 1.0 | 0.688092s | 23,625,066 B | Apache-2.0 | PASS |

All applicable fact-family metrics have empty false-positive and
false-negative sets. Corpus SHA-256 remained
`da03a77d5818deb2c2acd531e3875ad4053ff278d8cc11f17784d57f38d2cf4f`.
A timing/platform-independent projection of the fresh and committed D3 records
was byte-identical, SHA-256
`0322db3f2ca099de10e7c4c82c74f676a2f4de0c3653a16dc1b11077d6d2d2b5`.
SCIP/LSP and the TypeScript 7 stable compiler API remain explicit unsupported
or deferred entries rather than successful zero results.

Installed metadata/license files independently identify MIT for Tree-sitter,
the language pack, and ast-grep, and Apache-2.0 for TypeScript 5.9.3.

### AC-4.3 — PASS

The focused suite and independent failure replay prove real Tree-sitter parsing
for exported functions, exported const arrows, classes/methods, nested
functions/arrows, JSX/TSX, calls, writes, references, exact locations,
malformed input, and `.js/.mjs/.cjs/.jsx/.ts/.tsx/.mts/.cts`. The complete
TypeScript golden SHA-256 is
`13c6bc9e23f65375514931cb843f45589245b0657880b1b4a323685d6ea5fa93`.
The old heuristic under-detection and false-clean malformed-input behavior are
retired.

### AC-4.4 — PASS

Legacy Python symbols/raw-AST behavior and exact normalized spans remain green.
Rust and Go publish their accepted parser-backed syntax subset, and unsupported
type facts raise `unsupported_capability`. Complete golden hashes reproduced:

- Python: `c0239a865802c6ccfb58b4a9b20b2d0cb1431ac9d88339499215c7f5dffcf7b5`
- TypeScript: `13c6bc9e23f65375514931cb843f45589245b0657880b1b4a323685d6ea5fa93`
- Rust: `0dae96a96bbeacfb2ba7479e975ac1418cf984d7c12ad7ef16eeef028890ea2a`
- Go: `8af971cc0ed2ae6446025514be6dd8eb9492943c22baca17bc4b342c9c336e87`

### AC-4.5 — PASS

The independent replay required a contextual `AnalysisFailure` for every
attempt-1 bypass. Results were:

- absent parser → `missing_tool`;
- raising parser → `tool_failure`;
- cooperative and actually blocking parser → `tool_timeout`;
- absent root, missing/raising `named_children`, raising `children`, raising
  `has_error`, and raising child traversal → `corrupt_output`;
- malformed source → `parse_error`;
- unsupported capability → `unsupported_capability`;
- unknown suffix → `unsupported_language`;
- `.jsx`, `.mts`, `.cts`, and `.pyi` → the correct registered provider.

Every failure included adapter, path, and capability context. No attack
returned zero facts or a raw exception.

### AC-4.6 — PASS

Focused exact-revision suites:

```text
PYTHONDONTWRITEBYTECODE=1 <python-3.11> -m pytest -q \
  -p no:cacheprovider tests/test_analysis_facts.py \
  tests/test_lang_adapter.py tests/test_omnibus_language_adapters.py
Darwin-arm64: 65 passed in 1.44s
Linux-x86_64: 65 passed in 7.46s
```

Each platform then ran:

```text
<python-3.11> scripts/analysis_fact_benchmark.py \
  --source-revision d1a6316f0c57abc5e2162c477d6d56f51165cf14 \
  --output <platform-report>.json
{"passed": true, "violations": []}; exit 0
```

Fresh exact-revision results:

| Platform / fixture | Cold | Warm | CV | Peak Python | Peak RSS |
|---|---:|---:|---:|---:|---:|
| Darwin-arm64 small | 0.048119s | 0.000467s | 0.038274 | 86,019 B | 33,882,112 B |
| Darwin-arm64 external | 0.048963s | 0.003484s | 0.013233 | 946,226 B | 35,733,504 B |
| Linux-x86_64 small | 0.591821s | 0.008704s | 0.038030 | 86,019 B | 29,310,976 B |
| Linux-x86_64 external | 0.628638s | 0.065048s | 0.026879 | 946,226 B | 31,531,008 B |

Every row is below the one-second cold/warm, 20% CV, 64 MiB traced-Python,
and 128 MiB RSS ceilings. Install size was 5,089,262 B on Darwin and
7,676,949 B on Linux, both below 25 MB. Precision and recall were 1.0.

Both reports independently produced:

- source-tree SHA-256:
  `92aca126917a35a078f4b3d40f72de46c2e707a4580def146094425cd4cc70f0`;
- stable-result SHA-256:
  `a8c3596589629e79af1a601ae14c620ddb0d0127887225245c30d543311e7674`;
- small fact SHA-256:
  `79ab49d20aa30bd684c96c3b052517a228410f2090473ea6fc639a7f35354f39`;
- external fact SHA-256:
  `6474a8c3e5b945e3d0d4e9269574f8e004a0df4957cc420d83c15c83aaf7a9e4`.

The comparator passed with `cross_platform_deterministic=true`. Reversing the
report order produced a byte-identical matrix, SHA-256
`d49b676842e747be253e287cb2b67db19a9cdcb33e7cdd92baae43e8e76c48e5`.
Recomparing the committed `01874df` reports reproduced the committed matrix
byte-for-byte, SHA-256
`3d6a39aa395ab4c97d64e69448b986427787547c8f589d23cb160f7f2935ad55`.

## Source, license, and evidence binding

The new platform reports bind `d1a6316...` to the same complete benchmark
source scope as `01874df`; no scoped implementation/input path changed between
those revisions. Fresh downloads from the exact Microsoft TypeScript revision
`c63de15a992d37f0d6cec03ac7631872838602cb` produced:

- raw `symbolWalker.ts` SHA-256:
  `6aec8fecf7d57abd557bdbd4a9744ba2a1f3d8fcc9e9b84721158bd4f284300a`;
- raw license SHA-256:
  `a7d00bfd54525bc694b6e32f64c7ebcf5e6b7ae3657be5cc12767bce74654a47`.

Applying the manifest's exact transformations reproduced the committed files
byte-for-byte:

- CRLF-to-LF source SHA-256:
  `f468759c595c804f5c1ac171814ee43de0b030fa6d08c527525d6e3a24493306`;
- CRLF-to-LF plus trailing-whitespace-stripped license SHA-256:
  `527adf9d4c760f7367c2aeffed6a89afba8ba40ea1b0efbc8f56496ad30ea9cf`.

## Adversarial replay

The independent replay script first validated the fresh matrix, then rejected
all of these attacks:

- missing/duplicate/unexpected platform, platform machine/system/key, and
  embedded platform-contract forgery;
- cold, warm, RSS, Python allocation, CV, determinism, install, precision,
  recall, pass-state, violations, budget key/value, fixture set, and run-count
  forgery;
- execution-tool version, toolchain version/setup/license forgery;
- non-commit revision, different real revision, and stale source-tree forgery;
- malformed schema, missing fixtures, nonnumeric timing, and malformed digest;
- one-sided and coordinated two-report D3 corpus, normalized source,
  normalized license, source raw-upstream, license raw-upstream, source
  normalization, and license-normalization forgery, with every affected stable
  hash recomputed by the attacker;
- dirty representatives from each of the six `SOURCE_SCOPE` entries and an
  untracked consumed D3-corpus file;
- every attempt-1 parser/routing/failure bypass listed under AC-4.5.

Result:

```text
ALL COMPARATOR ATTACKS REJECTED
FULL SOURCE SCOPE DIRTY REJECTION PASS
ALL ATTEMPT-1 FAILURE ATTACKS REJECTED
ALL ADVERSARIAL REPLAYS PASS
```

The exact replay script SHA-256 is
`35ac05fd23115279fc8f0bab38a6d34f84dd905e36950d7c5122f44e34056319`.
The exact Git bundle used for the new Linux checkout is
`e91bd6b75c8741671568a77121941f48fe543b3e9a9dcf35d02c9877302b4295`.

## Other deterministic gates

```text
<venv-python> scripts/specs.py coverage portable-analysis-substrate
9 implemented, 5 documented, 0 partial/lag/ahead/orphans; exit 0

<venv-python> scripts/specs.py inventory-check portable-analysis-substrate
CLEAN; exit 0

<venv-python> scripts/plans.py audit
OK — 7 plans, no drift; exit 0

<venv-python> scripts/decisions.py audit
OK — 34 decisions, no drift; exit 0

<venv-python> scripts/decisions.py link-check
OK — 34 decisions, all links resolve, 22 host-scoped; exit 0

<venv-python> -m ruff check scripts tests
All checks passed; exit 0
```

Ruff emitted only the two already-recorded invalid-`noqa` warnings in
`scripts/status.py`.

## Temporary evidence hashes

| Artifact | SHA-256 |
|---|---|
| fresh D3 rerun | `5c00dfb65530f4682ba038c6cdee59ca230488b9e09f2a25dd22a0225ff3abcd` |
| fresh Darwin report | `43d692aef80842deedbcb943134d0af5b8d93b640245968d66f5741e9a0261b5` |
| fresh Linux report | `20912a253093dfdd4d388f9e4e0b333f2e4bedee36221f51169dc600a7469af1` |
| forward matrix | `d49b676842e747be253e287cb2b67db19a9cdcb33e7cdd92baae43e8e76c48e5` |
| reverse matrix | `d49b676842e747be253e287cb2b67db19a9cdcb33e7cdd92baae43e8e76c48e5` |
| recomputed committed matrix | `3d6a39aa395ab4c97d64e69448b986427787547c8f589d23cb160f7f2935ad55` |
| raw upstream source | `6aec8fecf7d57abd557bdbd4a9744ba2a1f3d8fcc9e9b84721158bd4f284300a` |
| raw upstream license | `a7d00bfd54525bc694b6e32f64c7ebcf5e6b7ae3657be5cc12767bce74654a47` |
| adversarial replay | `35ac05fd23115279fc8f0bab38a6d34f84dd905e36950d7c5122f44e34056319` |
| Linux Git bundle | `e91bd6b75c8741671568a77121941f48fe543b3e9a9dcf35d02c9877302b4295` |

## Setup-attempt disclosures

Three non-acceptance setup attempts failed before the clean reruns above:

1. An initial `/tmp` setup command included a blocked destructive `rm -rf`;
   no path changed. A `mktemp`-only setup replaced it.
2. The first outer-history construction used a shell glob from the wrong
   directory, leaving the intended large checkout at its root commit. That
   root-history run passed, but was not counted as large-history evidence; the
   25 files were then committed and the same tests reran and passed.
3. A diagnostic introspection snippet requested nonexistent convenience names
   `adapters`/`interface_version`; it raised `ImportError`. The public
   `iter_adapters` and `ANALYSIS_INTERFACE_VERSION` API was then used and
   returned the expected interface/provider contract.

None changed tracked verification inputs or supplied acceptance evidence.

Missing or ambiguous evidence: **none**.

Unsupported claims found: **none**.

Final verdict: **PASS — WP4 satisfies AC-4.1–AC-4.6 and the mandatory clean
full-suite gate at `d1a6316f0c57abc5e2162c477d6d56f51165cf14`.**
