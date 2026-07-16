# WP4 final source verification — FAIL

Verifier: `/root/wp4_final_source_verifier`, Codex/GPT-5. Exact deployed
variant and reasoning-effort setting were not exposed.

Verification start revision:
`a1cec852c5399b56d1599a53f189022decaff779` (`Advance WP4 to implemented`).
The source/evidence checkout was clean at start. The verifier changed no
implementation, test, plan, tracker, spec, or prior evidence file. Temporary
checkouts, reports, downloaded upstream blobs, and attack scripts were confined
to `/tmp`; this report is the only repository write.

The shared live worktree later acquired concurrent foreign WP3/WP5 work. At
report finalization the non-verifier paths reported by `git status --short`
were `.claude/skills/plan-skill/SKILL.md`,
`.claude/skills/_common/skill-catalog-inventory.yml`,
`logs/agent_policy/test_runs.jsonl`, `logs/agent_policy/friction.jsonl`,
`scripts/skill_meta.py`, `scripts/_lib/skill_catalog.py`,
`scripts/sweep/{__init__.py,schemas.py,serialization.py}`,
`tests/test_skill_meta_jobs.py`, `tests/test_skill_catalog_layers.py`,
`tests/test_sweep_slice0_characterization.py`, and four files under
`tests/fixtures/sweep/prototype-oracle/`. They were neither read as WP4
source nor changed by this verifier. All executable acceptance results came
from the clean exact-revision `/tmp` clones described below.

Overall verdict: **FAIL**. AC-4.1 through AC-4.6 each pass independent source,
execution, and adversarial replay. The mandatory clean-revision full-suite gate
does not pass: `tests/scripts/test_which_cleanup.py::test_run_changed_from_head`
expects a non-`trivial` scope for `HEAD~1`, but clean revision `a1cec852` changes
one plan file by 12 lines and the product correctly returns `trivial`. The exact
result is 518 passed, 1 skipped, 1 failed. The same test also fails at clean WP4
source revision `01874df` because that commit changes one test file by four
lines. Therefore the prior implementer claim of 519 passed/1 skipped is not
reproducible from either clean committed revision. Under the requested
all-gates rule, WP4 must not move to `verified` until this non-hermetic test is
repaired and a fresh verifier reruns the gate.

## Acceptance-criterion verdicts

### AC-4.1 — PASS

Independent inspection and the 65-test adapter contract suite confirm analysis
interface version 1, immutable location-bearing facts/results, per-provider
versions and capability discovery, and exactly the six bounded universal fact
families: symbols, imports, definitions, references, calls, and writes. Search
found 25 imports: two adapter-package declarations, two benchmark/cold-probe
consumers, and the same 21 production consumers recorded by the baseline. No
route, Django, React, or framework fact occurs in the adapter package.

Commands:

```text
rg -l 'from _lib\.lang_adapter import|import _lib\.lang_adapter' \
  scripts .claude/skills --hidden -g '*.py'
25 paths (2 adapter declarations + 2 benchmark paths + 21 production consumers)

rg -n 'route|django|react|framework' scripts/_lib/lang_adapter
no matches; exit 1 as expected for an empty search
```

### AC-4.2 — PASS

A new pinned D3 installation and run reproduced corpus SHA-256
`da03a77d5818deb2c2acd531e3875ad4053ff278d8cc11f17784d57f38d2cf4f`.
All supported fact families had precision and recall 1.0. The stable D3
projection was identical to committed `d3-rerun.json` at
`80616b4b31c6e059cc66d2bbf4cddd925382fbf1e8933441cd2480e6759e8acd`.

| Candidate | Fresh warm | Install bytes | License | Verdict |
|---|---:|---:|---|---|
| Tree-sitter 0.26.0 + language-pack 1.12.5 | 0.043185s | 5,089,280 | MIT | PASS (`<=1s`, `<=25MB`) |
| ast-grep 0.44.1, optional | 0.078038s | 154,339,105 | MIT | PASS (`<=6s`, `<=200MB`) |
| TypeScript Compiler API 5.9.3 | 0.643015s | 23,625,066 | Apache-2.0 | PASS (`<=1s`, `<=30MB`) |

The Tree-sitter D3 cold probe was 1.020386s; D3's accepted predeclared gate is
warm runtime, while WP4's separate product cold gate is covered and passes
under AC-4.6. TypeScript 7.0.2, SCIP, and LSP remain explicit unsupported or
deferred entries rather than clean zero-finding results.

Commands:

```text
.venv/bin/python -m pip install --target /tmp/wp4-final-d3-v1/python \
  tree-sitter==0.26.0 tree-sitter-language-pack==1.12.5
npm install --prefix /tmp/wp4-final-d3-v1/node \
  @ast-grep/cli@0.44.1 typescript-api@npm:typescript@5.9.3 typescript@7.0.2

.venv/bin/python scripts/analysis_portfolio_spike.py \
  --python-site /tmp/wp4-final-d3-v1/python \
  --node-modules /tmp/wp4-final-d3-v1/node/node_modules \
  --output /tmp/wp4-final-d3-v1.json
exit 0

.venv/bin/python <independent D3 budget/license assertion>
D3_PRECISION_RECALL_RUNTIME_INSTALL_LICENSE_PASS; exit 0
```

Package metadata/license files independently identify MIT for Tree-sitter,
the language pack, and ast-grep, and Apache-2.0 for TypeScript 5.9.3.

### AC-4.3 — PASS

The TypeScript/JavaScript providers use Tree-sitter. Focused execution covers
exported functions and const arrows, classes/methods, nested functions/arrows,
JSX/TSX, calls, writes, syntax references, exact locations, malformed input,
and `.js/.mjs/.cjs/.jsx/.ts/.tsx/.mts/.cts`. The full-shape TypeScript golden
remains SHA-256
`13c6bc9e23f65375514931cb843f45589245b0657880b1b4a323685d6ea5fa93`.
Every attempt-1 under-detection/routing case passed direct replay.

### AC-4.4 — PASS

The focused suite preserves legacy Python symbol/raw-AST behavior and exact
normalized spans. Rust and Go expose their accepted parser-backed syntax
subset; unsupported type facts raise `unsupported_capability`. All complete
golden hashes reproduced:

- Python: `c0239a865802c6ccfb58b4a9b20b2d0cb1431ac9d88339499215c7f5dffcf7b5`
- TypeScript: `13c6bc9e23f65375514931cb843f45589245b0657880b1b4a323685d6ea5fa93`
- Rust: `0dae96a96bbeacfb2ba7479e975ac1418cf984d7c12ad7ef16eeef028890ea2a`
- Go: `8af971cc0ed2ae6446025514be6dd8eb9492943c22baca17bc4b342c9c336e87`

### AC-4.5 — PASS

The verifier's standalone replay required contextual `AnalysisFailure` for
all prior bypasses. Missing parser -> `missing_tool`; raising parser ->
`tool_failure`; cooperative and actually blocking parser -> `tool_timeout`;
missing root, missing/raising `named_children`, raising `children`, raising
`has_error`, and raising child traversal -> `corrupt_output`; malformed source
-> `parse_error`; unsupported capability -> `unsupported_capability`; unknown
suffix -> `unsupported_language`. Every result included adapter, file, and
capability context. Registered `.jsx`, `.mts`, `.cts`, and `.pyi` routed to the
correct providers. No case returned successful zero facts or a raw exception.

Command:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  /tmp/wp4-final-adversarial-v1.py
ALL ATTEMPT-1 FAILURE ATTACKS REJECTED
ALL ADVERSARIAL REPLAYS PASS; exit 0
```

### AC-4.6 — PASS

Fresh reports were generated at exact final revision `a1cec852` on the required
Darwin-arm64 and real Linux-x86_64 platforms. Both independently produced
source-tree SHA-256
`92aca126917a35a078f4b3d40f72de46c2e707a4580def146094425cd4cc70f0`,
stable-result SHA-256
`a8c3596589629e79af1a601ae14c620ddb0d0127887225245c30d543311e7674`,
small fact SHA-256 `79ab49d2…`, and external fact SHA-256 `6474a8c3…`.

| Platform / fixture | Cold | Warm | CV | Peak Python | Peak RSS |
|---|---:|---:|---:|---:|---:|
| Darwin-arm64 small | 0.060863s | 0.000457s | 0.052462 | 85,962 B | 30,670,848 B |
| Darwin-arm64 external | 0.061401s | 0.003605s | 0.039470 | 946,226 B | 30,752,768 B |
| Linux-x86_64 small | 0.672594s | 0.009057s | 0.040985 | 85,962 B | 29,224,960 B |
| Linux-x86_64 external | 0.720769s | 0.064962s | 0.028394 | 946,226 B | 31,334,400 B |

All rows are below the one-second cold/warm, 20% CV, 64 MiB traced-Python,
and 128 MiB RSS ceilings. Install size was 5,089,262 B on Darwin and
7,676,949 B on Linux, both below 25 MB. Precision and recall were 1.0.

Darwin was Apple M1, macOS 26.5.1/Darwin 25.5.0, Python 3.11.10. Linux was
Ubuntu 22.04.5, kernel 5.15.0-185 under Lima 2.1.4/QEMU, Python 3.11.15. Both
used Tree-sitter 0.26.0 and language-pack 1.12.5. The Linux checkout was a new
`/tmp` clone of Git bundle SHA-256
`07c9d5133fb4a6e9587f9fcc25fc35bce98edaeeb9778f86206e8cd074da795f`.
Host and guest process snapshots immediately before the Linux run showed no
`rg`, `find`, repository test, or benchmark scan; guest CPU was otherwise idle.

Commands/results:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  -p no:cacheprovider tests/test_analysis_facts.py \
  tests/test_lang_adapter.py tests/test_omnibus_language_adapters.py
Darwin-arm64: 65 passed in 1.47s
Linux-x86_64: 65 passed in 8.03s

.venv/bin/python scripts/analysis_fact_benchmark.py \
  --source-revision a1cec852c5399b56d1599a53f189022decaff779 \
  --output /tmp/<platform>.json
Both: {"passed": true, "violations": []}; exit 0

.venv/bin/python scripts/analysis_fact_benchmark.py \
  --compare-platform-reports /tmp/wp4-final-a1cec-darwin-v1.json \
  /tmp/wp4-final-a1cec-linux-v1.json \
  --output /tmp/wp4-final-a1cec-matrix-v1.json
{"passed": true, "violations": []}; cross_platform_deterministic=true
```

Reversing report order generated a byte-identical matrix, SHA-256
`6275bbbfeada754da387036b18dc537bd04ee0b00a06376184a681a2b0230136`.
Recomparing the committed `01874df` reports regenerated the committed matrix
byte-for-byte, SHA-256
`3d6a39aa395ab4c97d64e69448b986427787547c8f589d23cb160f7f2935ad55`.
There is no source-scope change between `01874df` and `a1cec852`.

The standalone adversarial replay rejected:

- a dirty representative from every one of the six `SOURCE_SCOPE` entries,
  plus an untracked consumed corpus file;
- missing/duplicate/wrong platform, malformed schema/shape/timing/digest,
  cold/warm/RSS/Python/CV/install/precision/recall/determinism/pass/violations,
  budget key/value, fixture-set, run-count, toolchain/license/setup, non-commit
  revision, different real revision, and stale-tree forgeries;
- every one-sided and coordinated two-report D3 corpus, normalized source,
  normalized license, source raw-upstream, license raw-upstream, source
  normalization, and license normalization forgery after recomputing the
  affected stable hashes.

All were rejected. The focused committed-source/provenance regression also
passed 10 tests (29 deselected) in 1.53s. The comparator baseline remained
passing and deterministic.

Fresh downloads from Microsoft's exact TypeScript revision independently
verified raw source SHA-256
`6aec8fecf7d57abd557bdbd4a9744ba2a1f3d8fcc9e9b84721158bd4f284300a`
and raw license SHA-256
`a7d00bfd54525bc694b6e32f64c7ebcf5e6b7ae3657be5cc12767bce74654a47`.
Applying the manifest's exact transformations reproduced committed normalized
source SHA-256 `f468759c…` and license SHA-256 `527adf9d…` byte-for-byte.

## Mandatory full-suite failure

Command at clean final evidence revision:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -x -vv \
  -p no:cacheprovider
collected 520 items
FAILED tests/scripts/test_which_cleanup.py::test_run_changed_from_head
assert 'trivial' in {'small', 'medium', 'large'}
1 failed, 18 passed before -x; exit 1
```

The non-failing remainder proves isolation:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  -p no:cacheprovider -k 'not test_run_changed_from_head' -rs
518 passed, 1 skipped, 1 deselected in 26.59s; exit 0
```

The skip is the same test module's separate large-diff-only case: `HEAD~1 is
not large in this checkout`. Running only the failed test at clean source
revision `01874df5d8d73b5fc74bf7a6e04fa51936a694ff` also fails because that
commit changes only four lines in one test file. This confirms a clean-commit
shape dependency, not a WP4 parser/fact/budget failure. It is nevertheless a
real mandatory gate failure and is not waived.

## Other deterministic gates

```text
.venv/bin/python scripts/specs.py coverage portable-analysis-substrate
9 implemented, 5 documented, 0 partial/lag/ahead/orphans; exit 0

.venv/bin/python scripts/specs.py inventory-check portable-analysis-substrate
CLEAN; exit 0

.venv/bin/python scripts/plans.py audit
OK — 7 plans, no drift; exit 0

.venv/bin/python scripts/decisions.py audit
OK — 34 decisions, no drift; exit 0

.venv/bin/python scripts/decisions.py link-check
OK — 34 decisions, all links resolve, 22 host-scoped; exit 0

.venv/bin/python -m ruff check scripts tests
All checks passed; exit 0
(two pre-existing invalid-noqa warnings in scripts/status.py)
```

## Fresh artifact binding

| Temporary verifier artifact | SHA-256 |
|---|---|
| exact-revision Git bundle | `07c9d5133fb4a6e9587f9fcc25fc35bce98edaeeb9778f86206e8cd074da795f` |
| Darwin report | `51187827c7c2fe90a2dfc63051bd73af62e79db8308f44c820977eb509826bdd` |
| Linux report | `0176e116cd42d9eee1abf03b4fb6e0bf76a0ec5d4012403cdc0f3978dd1867e0` |
| cross-platform matrix | `6275bbbfeada754da387036b18dc537bd04ee0b00a06376184a681a2b0230136` |
| D3 rerun | `0a16f2b5037bbc91dc2c5077cd705dcf27e0cc117c3e41e9d8c0338081b88aca` |
| adversarial replay script | `b8e93ee06721f470bdf557df8e75cd3304dce11821fc9fdd3b30ea867e5a9f08` |

The generated `/tmp` artifacts are not proposed as durable repository
evidence; their hashes bind the exact commands and values reported here. The
committed Darwin/Linux reports and committed matrix also validated against
their real `01874df` commit and raw blobs. Their source-tree/stable-result
hashes are identical to the fresh final-revision run because the complete
benchmark source scope did not change.

## Setup-attempt disclosures and limitation

The first focused invocation in the disposable Darwin checkout used an
incomplete venv symlink and failed with missing `tree_sitter_language_pack`
(22 failed, 33 passed, 10 errors). Adding the existing venv's `pyvenv.cfg` and
library path made `.venv/bin/python` resolve the intended environment; the
exact focused command then passed 65/65. The first standalone attack script
run reached and passed every comparator/source-scope attack but stopped on a
verifier-script `type` name-shadowing error before its final traversal case;
the ephemeral harness was corrected and rerun from the beginning to the final
`ALL ADVERSARIAL REPLAYS PASS` result. Neither setup attempt changed tracked
files or supplied acceptance evidence.

No Windows execution is claimed; `platform-contract.json` explicitly excludes
Windows from this release. No limitation remains within AC-4.1–AC-4.6. The only
blocking result is the mandatory clean-revision full-suite failure above.
