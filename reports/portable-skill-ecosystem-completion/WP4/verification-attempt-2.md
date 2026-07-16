# WP4 fresh-scope verification attempt 2

Verifier: `/root/wp4_reverification`, Codex/GPT-5 (exact deployed model
variant not exposed)

Revision: `11164af4568b43364da222c171083135e806f4fa` (`11164af`), tree
`df4e07b1f7b41113fcc4a188054092b5aa6b03b9`.

Work package: WP4 (`AC-4.1` through `AC-4.6`).

Overall: **FAIL**. AC-4.1 through AC-4.5 pass. AC-4.6 remains unproven and
fails because the evidence is still single-platform, its platform matrix is a
hard-coded claim rather than an execution-derived record, and the synthetic
40-line repeated-function fixture is not a justified representative large or
external-shaped corpus. WP4 must not move to `verified`.

## Workspace and verifier environment

The live worktree was clean at the initial identity capture. It later acquired
concurrent foreign WP2 edits and automatic command-policy telemetry. All
verification commands therefore ran against a clean `git archive` of the exact
revision at `/tmp/wp4-attempt2-11164af.CmQBEJ`, using the project interpreter
by absolute path. The archive tree was not modified. Its lack of `.git` history
accounts for the two unrelated full-suite skips recorded below.

Live dirty paths at report finalization (not inputs to any result) were all
concurrent WP2 work or automatic policy logs, plus this requested report:

- `.claude/skills/adapt-project/SKILL.md` =
  `cdef57f1c1cb6a3dc0a12f6fa85650662f2589f8b0d1ecc0aa112c8cbabe78ad`
- `.claude/skills/find-perimeter-gaps/SKILL.md` =
  `04d99a3d6b1c636e1d7f4368dae6d81e36694e8db1cf93715a4359d21317eb30`
- `.claude/skills/find-perimeter-gaps/scripts/scan.py` =
  `23af37dda89c6a17810f0d196043173c19892900a29661f6e90fa6a966d5028f`
- `ai-docs/specs/portable-host-profile-routing.md` =
  `9fc6f3c0443b2de53c991bff0c1fe10f47f63ff5ae3c5e390c7bcf3371307310`
- `scripts/project_adapt.py` =
  `f2df70226995afe19abfd842fb3b1225cae5d5be7bc273f71524a6c6dde1e56b`
- `tests/test_perimeter_gaps.py` =
  `29ce18575ab40c389836b98e1d0f1f065ff70b623d7f7224478680f49108233a`
- `tests/test_project_adapt.py` =
  `4f5d82e085d795ca9c928a22c6efd922c3cad053c101a2d7da6f704dca247698`
- `logs/agent_policy/test_runs.jsonl` =
  `f50ca5b4774763c0d711ad7d0902099843a24e32f6d5add9dbf0e7e25331a0c0`;
  this contains automatic verifier-command telemetry plus foreign commands and
  was not manually edited.
- `logs/agent_policy/friction.jsonl` (untracked) =
  `6cca27ff2147ad8d389af58b91d7a2febeda68b6ff0c0405610c71807597e5bb`.

Platform: macOS 26.5.1, Darwin 25.5.0, arm64 (`RELEASE_ARM64_T8103`).
Interpreter: Mach-O arm64 Python 3.11.10. Toolchain: pytest 9.0.3,
PyYAML 6.0.3, Ruff 0.6.9, tree-sitter 0.26.0,
tree-sitter-language-pack 1.12.5, Node 26.3.1 for the regenerated D3 record,
and npm 11.12.1. Runtime parser packages are exactly pinned in
`requirements.txt`.

The verifier read the authoritative plan, successor spec, ADR 0039, WP4
baseline, implementation evidence, and attempt-1 report before inspecting the
implementation and tests. Attempt-1 defects were treated as mandatory attacks,
not accepted from the implementer narrative.

## AC verdicts

### AC-4.1: PASS

Inspection and focused execution prove a versioned `LanguageAdapter.analyze`
request interface, immutable `Fact`/`AnalysisResult` records, deterministic
ordering, provider/interface versions, per-provider language/extensions and
capability discovery, and exactly the six normalized fact families required by
the plan: symbols, imports, definitions, references, calls, and writes. The
raw Python syntax tree remains a compatibility capability rather than a
universal fact. No route, Django, React, or other framework fact is present.
The baseline's hidden-path inventory still identifies 21 runtime consumers;
the six-family surface is bounded to the accepted analysis/sweep/perimeter
portfolio and does not grow into a universal AST.

### AC-4.2: PASS

The selected Tree-sitter provider is production runtime code and both parser
packages are pinned. A fresh exact D3 setup and rerun preserved corpus SHA-256
`da03a77d5818deb2c2acd531e3875ad4053ff278d8cc11f17784d57f38d2cf4f`.
All supported fact families again had precision and recall 1.0. Independent
budget validation produced:

| Candidate | Warm seconds | Install bytes | Result |
|---|---:|---:|---|
| Tree-sitter language pack | 0.045571 | 5,089,280 | PASS (`<=1s`, `<=25MB`) |
| ast-grep 0.44.1 (optional) | 0.075480 | 154,339,105 | PASS (`<=6s`, `<=200MB`) |
| TypeScript Compiler API 5.9.3 | 0.665925 | 23,625,066 | PASS (`<=1s`, `<=30MB`) |

The regenerated Tree-sitter cold probe was 1.255515 seconds, but ADR 0039's
predeclared D3 gate has a warm-runtime ceiling, not a D3 cold ceiling. The
successor spec's additive productized cold ceiling is enforced separately and
passed under AC-4.6's local benchmark evidence. Licenses and deterministic
setup commands remain recorded. SCIP/LSP and the TypeScript 7 stable API remain
explicitly unsupported, while native compiler semantics remain conditional on
a named consumer, as ADR 0039 permits.

The stable (non-timing/platform) projection of the regenerated and committed
D3 records has the same SHA-256:
`bb79901884fdc9ba493882e4f5bdcbd026698594637876cd1c6bdfa6345a6051`.

### AC-4.3: PASS

The TypeScript/JavaScript provider uses Tree-sitter, not the retired heuristic.
Focused tests and direct attacks cover exported functions, exported const
arrows, classes, methods, nested functions/arrows, JSX, calls, writes,
references, parent scopes, malformed input, deterministic source ordering, and
locations. Canonical routing passed for all `.js/.mjs/.cjs/.jsx/.ts/.tsx/.mts/.cts`
extensions. Malformed TypeScript raises contextual `parse_error`; the old
hidden/indented declaration miss is retired.

The full-shape TypeScript golden contains 41 facts and recomputed to
`dda8368b8c0b1618fdc138c4a730757f731de6c60663664d989ea63cab58771d`.

### AC-4.4: PASS

The legacy Python symbol and raw-AST compatibility suites remain green. The 20
raw-AST consumers retain `CAP_PYTHON_AST`/`parse()` behavior. Python normalized
analysis covers all six families. An independent AST-to-fact comparison proved
that every legacy normalized symbol span uses its owning AST node's exact
1-based start/end columns; for example `BigService.get_samples` is
`(29,5)-(30,18)`, not the old synthetic `(29,1)-(30,1)`.

Rust and Go fixtures publish the accepted syntax subset and deterministic
facts. Unsupported `analysis.type-facts` requests raise contextual
`unsupported_capability` instead of guessing semantics.

### AC-4.5: PASS

All attempt-1 failure bypasses were replayed independently. Each of the
following returned contextual `AnalysisFailure`, never zero facts or a raw
exception:

- missing root, missing `named_children`, raising `children`, raising
  `named_children`, raising `has_error`, and a child whose traversal raises:
  `corrupt_output`;
- absent loader: `missing_tool`;
- parser exception: `tool_failure`;
- malformed source: `parse_error`;
- unexpected parser/tree object: `corrupt_output`;
- unsupported capability: `unsupported_capability`.

A genuinely blocking parser was released only after the request returned. With
the provider deadline set to 30ms, `analyze()` returned contextual
`tool_timeout` in 35.1ms; no outer subprocess timeout supplied the result.

Strict request-boundary discovery passed: `.jsx` -> `javascript-syntax`,
`.mts/.cts` -> `typescript-syntax`, `.pyi` -> `python-ast`, and an unknown
suffix raised `unsupported_language` with registry, path, and requested
capability context. `adapter_for_suffix()` remains an explicitly optional
low-level registry probe, but every production caller found by repository
search uses strict `get_adapter()`.

### AC-4.6: FAIL

The repaired local mechanisms themselves pass:

- the benchmark launches each cold probe through a fresh
  `subprocess.run([sys.executable, script, "--cold-probe", ...])`, so
  interpreter/provider startup is included;
- six separate same-process warm measurements supply mean, standard deviation,
  and population CV;
- regenerated small/large facts are deterministic and match the committed
  hashes;
- every golden hash covers the serialized full fact dictionaries, including
  capability, name, path, start line/column, end line/column, kind, and parent;
- all four language goldens and exact Python symbol spans passed independent
  replay;
- local cold/warm/memory/variance/install/precision/recall budgets passed.

The regenerated product benchmark reported:

| Fixture | Cold | Warm mean | Warm CV | Peak Python | Peak RSS | Fact hash |
|---|---:|---:|---:|---:|---:|---|
| small, 431 B / 18 lines | 0.100267s | 0.005419s | 0.053727 | 124,624 B | 32,489,472 B | `79ab49d20aa30bd684c96c3b052517a228410f2090473ea6fc639a7f35354f39` |
| large, 3,457 B / 40 lines | 0.103012s | 0.029804s | 0.030982 | 666,895 B | 33,341,440 B | `9a95acb8c9be4f7f6fff4ace54e22171f5253dba2d64d8984425ca0223891b2d` |

The stable (non-timing/memory/platform) projection of the regenerated and
committed product reports has the same SHA-256:
`6a8e5034592be659d79629e9140f3d0ba6c5c2b259482b2d2908ba38f36f5ccf`.

Those local passes do not prove the full criterion:

1. Only Darwin-arm64 has executed. `gh run list --commit
   11164af4568b43364da222c171083135e806f4fa` returned `[]`; the repository has
   no linked Linux result for this exact revision. A configured
   `ubuntu-latest` workflow is not execution evidence.
2. `scripts/analysis_fact_benchmark.py` hard-codes `Darwin-arm64: executed`,
   `Linux-x86_64: candidate`, and `Windows: not supported`. It does not derive
   the matrix from `platform.system()/machine()`. A Linux run would therefore
   still claim Darwin executed and Linux unexecuted, making the purported
   platform evidence false by construction.
3. Relabeling all unexecuted platforms “candidate” and the current platform
   “supported” is a tautology that weakens AC-4.6's requirement for
   deterministic goldens/contracts across supported platforms. No accepted ADR
   or master-plan amendment authorizes reducing the portable release contract
   to the verifier's one machine.
4. The added fixture text explains relative scale (8x the small input) and fact
   growth, but the “large” fixture is 40 generated one-line `transformNN`
   functions. It has no external-shaped provenance, structural variety, or
   evidence that 3.4KB represents a large real input. This does not satisfy the
   plan's representative-large wording or its fixture-overfitting mitigation
   (“at least one representative external-shaped corpus”).

Required executed-platform evidence is exact and bounded: after making the
platform record execution-derived, declare the actual supported release
matrix in an authoritative contract (or obtain an independently reviewed
master-AC/ADR amendment if support is intentionally narrowed). For the intended
portable matrix, retain this Darwin-arm64 record and attach a linked clean
Linux-x86_64 run at the same implementation revision with Python 3.11 and exact
tree-sitter 0.26.0/language-pack 1.12.5. That run must execute at least the
focused adapter/golden contract suite and `analysis_fact_benchmark.py`, publish
the complete report and hashes, show the same full normalized fact/golden
digests as Darwin, and pass cold/warm/RSS/Python-allocation/CV/install budgets.
Windows need not execute while an accepted authoritative release contract
explicitly excludes it; if Windows is claimed, it needs the same linked run.
Tool-version determinism is bounded to the exactly pinned versions unless the
support contract declares a broader version range.

The representative-fixture gap additionally requires either an external-shaped
large fixture/corpus with recorded provenance and selection rationale, or a
predeclared, independently accepted quantitative rationale showing why the
fixture is representative of the supported workload—not merely larger than
the small synthetic fixture.

## Exact commands and results

All repository commands below ran from the clean archive using
`<project-root>/.venv/bin/python` explicitly.

```text
PYTHONDONTWRITEBYTECODE=1 <venv-python> -m pytest -q -p no:cacheprovider \
  tests/test_analysis_facts.py tests/test_lang_adapter.py \
  tests/test_omnibus_language_adapters.py
52 passed in 0.55s; exit 0

PYTHONDONTWRITEBYTECODE=1 <venv-python> -m pytest -q -p no:cacheprovider
476 passed, 2 skipped in 20.08s; exit 0

PYTHONDONTWRITEBYTECODE=1 <venv-python> -m pytest -q -p no:cacheprovider -rs
476 passed, 2 skipped in 15.80s; exit 0
Both skips: tests/scripts/test_which_cleanup.py cannot resolve HEAD~1 because
the clean git archive intentionally contains no .git directory.

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
All checks passed; exit 0 (two pre-existing invalid-noqa warnings in
scripts/status.py)

<venv-python> scripts/analysis_fact_benchmark.py \
  --output /tmp/wp4-attempt2-product.json
{"passed": true, "violations": []}; exit 0

<venv-python> -m pip install --target /tmp/wp4-attempt2-d3/python \
  tree-sitter==0.26.0 tree-sitter-language-pack==1.12.5
exit 0; exact cached macOS arm64 wheels installed

npm install --prefix /tmp/wp4-attempt2-d3/node \
  @ast-grep/cli@0.44.1 typescript-api@npm:typescript@5.9.3 typescript@7.0.2
exit 0; six packages installed; ast-grep 0.44.1 and both TypeScript versions
were directly version-checked

<venv-python> scripts/analysis_portfolio_spike.py \
  --python-site /tmp/wp4-attempt2-d3/python \
  --node-modules /tmp/wp4-attempt2-d3/node/node_modules \
  --output /tmp/wp4-attempt2-d3-rerun.json
exit 0

<venv-python> <independent D3 budget assertion script>
tree-sitter-language-pack PASS
typescript-compiler-api PASS
ast-grep PASS
D3_BUDGETS_PASS; exit 0

PYTHONDONTWRITEBYTECODE=1 <venv-python> <attempt-1 adversarial replay>
ALL_ATTACKS_PASS; exit 0

gh run list --commit 11164af4568b43364da222c171083135e806f4fa \
  --limit 20 --json databaseId,name,workflowName,status,conclusion,headSha,url,createdAt,updatedAt
[]; exit 0
```

## Evidence hashes

- `scripts/_lib/lang_adapter/base.py` =
  `a96542a2d3efd64198bc1f1096354e70a1494055f322e24391cbdb99fbe4e5fa`
- `scripts/_lib/lang_adapter/javascript_adapter.py` =
  `d0a9cefc0be062522db3592130ed7a9c1a7420306edd7ab8eb32953f24380583`
- `scripts/_lib/lang_adapter/python_adapter.py` =
  `3ec0f078f9b5fbaeb657dd171418f9ba99e141e351fa45e0a5665d1e7102e15a`
- `scripts/_lib/lang_adapter/systems_adapter.py` =
  `827eba39bb1f0c19408a33e12a5cabd78e72adf22fb15124cc9c91015bf87fa4`
- `scripts/analysis_fact_benchmark.py` =
  `0be532b069a75442fcee083b0d1cc1edbffd08f80b9ea74197a40f2db57253c3`
- `requirements.txt` =
  `4bdcf735f006edf4b770ea744948920c78f485cd5be06a369fd4ad81ca6f76be`
- committed product benchmark =
  `a13e8b0b5e0a1159048b49bd711c53692086e305fbebb1d380acd5dc7e8aabab`
- regenerated product benchmark =
  `e1ccc3a87e5664c717dbcdd01455af5ea06b91a8ac4972d98a4ba6edd9babf95`
- committed D3 rerun =
  `c513b9f06ba78f3e4bbabd5a71460c6ecc5a91a22226571ae743b21c3ad7df4b`
- regenerated D3 rerun =
  `e837942d4b13ddc67d2133d941a47764ac212bde443aa517c9c349316bba7d10`
- golden files: Go
  `8af971cc0ed2ae6446025514be6dd8eb9492943c22baca17bc4b342c9c336e87`,
  Python
  `c0239a865802c6ccfb58b4a9b20b2d0cb1431ac9d88339499215c7f5dffcf7b5`,
  Rust
  `0dae96a96bbeacfb2ba7479e975ac1418cf984d7c12ad7ef16eeef028890ea2a`,
  TypeScript
  `13c6bc9e23f65375514931cb843f45589245b0657880b1b4a323685d6ea5fa93`.

## Missing or ambiguous evidence

- No linked executed Linux (or other second supported-platform) result exists
  for exact revision `11164af`; only Darwin-arm64 executed.
- The platform matrix is hard-coded and cannot truthfully record a Linux run.
- No authoritative accepted decision permits narrowing AC-4.6 to whichever
  single platform ran locally.
- No representative external-shaped large fixture, provenance, or accepted
  workload-based representativeness threshold exists.

## Unsupported claims found

- Implementation evidence's statement that an “explicit
  executed/candidate/unsupported platform matrix” repairs AC-4.6 is
  insufficient: the matrix is self-declared, hard-coded, and single-platform.
- Treating Linux as merely a candidate weakens, rather than proves,
  deterministic behavior “across supported platforms” in the authoritative
  AC.
- Calling a 40-line chain of generated `transformNN` functions a
  representative large fixture is unsupported by external shape, provenance,
  or workload evidence.
