# WP4 pre-implementation baseline

Characterization revision: `db0fed19c7c783d04314dacbc4da73b7a4b3bbf7`
(`db0fed1`). This report characterizes the committed pre-WP4 implementation;
it does not claim that AC-4.1–AC-4.6 are implemented.

## Workspace and method

The worktree started with two unrelated dirty paths owned by the coordinating
lane:

- `ai-docs/plans/portable-skill-ecosystem-completion.md` — tracker-only WP2/WP4
  start-state edit; ignored for baseline behavior.
- `logs/agent_policy/test_runs.jsonl` — command telemetry from prior
  verification; not analysis behavior.

No production, tracker, spec, dependency, or git state was changed by this
characterization. The only intended artifact is this report. Commands ran on
macOS 26.5.1 / Darwin 25.5.0 / arm64 with Python 3.11.10 and Node 22.21.1.
The D3 rerun reused the already-pinned temporary dependencies; it performed no
network access or installation and wrote its dynamic report to
`/tmp/wp4-baseline-db0fed1.json`.

## Existing adapter contract

`scripts/_lib/lang_adapter` is an unversioned, extension-keyed registry. A
`LanguageAdapter` advertises `name`, `language`, `extensions`, and a set of
string capabilities, then implements `extract_symbols(source, path=...)`.
Registration is last-writer-wins for an extension.

Only two capabilities exist:

| Capability | Providers | Meaning |
|---|---|---|
| `symbols` | `python-ast`, `js-heuristic` | Returns `list[Symbol]`, or currently `None` only for unparseable Python. |
| `python_ast` | `python-ast` | Exposes `PythonAdapter.parse()` and its raw `ast.Module`; it is not a normalized cross-language fact. |

`Symbol` currently contains `name`, `cluster_name`, `kind`, 1-based `lineno`
and `end_lineno`, `loc`, optional `parent`, `is_dunder`, and `decorators`.
There is no interface version, requested-capability method, immutable generic
fact type, typed result/error, tool version, or normalized imports,
definitions, references, calls, or writes surface.

Registered providers at the baseline are:

| Provider | Language label | Extensions | Capabilities |
|---|---|---|---|
| `python-ast` | `python` | `.py` | `symbols`, `python_ast` |
| `js-heuristic` | `javascript` | `.js`, `.mjs`, `.cjs`, `.ts`, `.tsx` | `symbols` |

The TypeScript extensions therefore report language `javascript` today. `.rs`
and `.go` resolve to no adapter. The capability registry separately names the
Rust `cargo` and Go `go-toolchain` sweep shims as `unsupported`; those shims do
not emit normalized facts.

## AR-2 consumer and requested-fact inventory

All production imports of `_lib.lang_adapter` were traced, including hidden
`.claude/skills` paths. There are 21 runtime consumers outside the adapter
package: one normalized-symbol consumer and 20 Python-AST consumers. The
reviewer's first non-hidden search found only the four rows below; the
coordinator's hidden-path recheck corrected that incomplete inventory before
implementation acceptance.

| Consumer | Requested adapter capability/facts | Current output dependence | Current failure handling |
|---|---|---|---|
| `.claude/skills/find-omnibus/scripts/detect.py` | `symbols` for Python and JS-family files | `name`, `cluster_name`, `loc`, plus adapter `language`/`name`; symbols are clustered and candidate records are sorted by score/file. | No adapter, read error, `None`, and non-candidate/empty symbols all yield no record. |
| `scripts/duplication_audit.py` | `python_ast` | AST calls, function names/signatures, request access shapes, file/line/column, and cross-file clone fingerprints. | Missing capability, decode failure, and parse `None` silently skip the file. |
| `scripts/semantic_inventory.py` | `python_ast` | Top-level definitions, class methods, decorators, arity, line/end line/size, and call edges with caller/callee/style/location. | Missing capability silently skips; decode/syntax failures increment `parse_errors` and warn. |
| `scripts/name_audit.py` | `python_ast` | Function/method names, parameters, owning class, body length, property/staticmethod flags, path and line. | Missing capability silently skips; syntax failure warns; read/decode errors are not wrapped here. |

The other 17 raw-AST consumers use the same compatibility seam and keep their
existing Python-specific walks: `_common/product_topology.py`,
`explain-code/inventory_symbols.py`, `extract-enum/collect.py`,
`extract-state-type/collect_target.py`, `find-async-lifecycle-drift/detect.py`,
`find-complexity-hotspots/detect.py`, `find-contract-drift/detect.py`, both
`find-dormant` detectors, `find-duplication/collapse.py`,
`find-implicit-state/detect.py`, `find-layer-violation/detect.py`,
`find-query-mutation/detect.py`, `find-transaction-overreach/detect.py`,
`introduce-fk/collect.py`, `propose-boundary/propose.py`, and
`propose-folder-reorganization/inspect.py`. They request only the Python syntax
tree, not a language-neutral AST. This full list is pinned by:

```text
rg -l "from _lib\\.lang_adapter import|import _lib\\.lang_adapter" \
  scripts .claude/skills --hidden -g '*.py'
23 paths total: 2 adapter-package declarations + 21 runtime consumers
```

The adapter tests and omnibus integration tests are contract consumers but not
runtime products. `scripts/analysis_portfolio_spike.py` and its three probes
are evaluation consumers: the syntax probes request `definitions`, `imports`,
`calls`, and `writes`; the TypeScript compiler probe additionally requests
`references`. No current production consumer requests the planned universal
imports/definitions/references/calls/writes interface. Framework facts such as
routes are absent, as ADR 0039 and AC-4.1 require.

## AR-1 Python compatibility oracle

Fixture SHA-256: `tests/fixtures/lang_adapter/sample.py` =
`c2bc3377bd721e3e45d656c7bb99527dc90a52dda37d75fd7c83636685a35175`.
The ordered `PythonAdapter.extract_symbols()` output is:

| Name | Cluster | Kind | Lines | LOC | Parent |
|---|---|---|---:|---:|---|
| `load_invoice` | `load_invoice` | `function` | 4–5 | 2 | — |
| `fetch_shipment` | `fetch_shipment` | `async_function` | 8–9 | 2 | — |
| `SmallThing` | `SmallThing` | `class` | 16–20 | 5 | — |
| `BigService.get_samples` | `get_samples` | `method` | 29–30 | 2 | `BigService` |
| `BigService.save_samples` | `save_samples` | `method` | 32–33 | 2 | `BigService` |
| `BigService.parse_html` | `parse_html` | `async_method` | 35–36 | 2 | `BigService` |

Every row has `is_dunder=false`; decorators are empty for this fixture.
Top-level `__ignored_dunder__` and `BigService.__init__` are omitted. A class
with at least three non-dunder methods expands to method symbols; a smaller
class remains one class symbol. Python AST traversal preserves source order.

`parse("def f(:\n")` and `extract_symbols(...)` both return `None`. That is the
only adapter-level Python parse-failure signal; it has no file or requested-
capability context. The existing fixture pins symbols and locations, not
normalized Python imports, definitions, references, calls, or writes. The
three raw-AST consumers derive their own incompatible fact shapes, so AR-1
still needs golden outputs for those planned common facts before migration.

## JavaScript/TypeScript heuristic oracle

Fixture SHA-256: `tests/fixtures/lang_adapter/sample.ts` =
`f3d3126bdc72e8a61418821fe93c7a94fca7307925051cd381edd8024e29dae1`.
The ordered heuristic output is:

| Name | Kind | Lines | LOC |
|---|---|---:|---:|
| `loadInvoice` | `function` | 2–5 | 4 |
| `fetchShipment` | `function` | 6–9 | 4 |
| `CustomerWidget` | `class` | 10–15 | 6 |
| `bootInventory` | `function` | 16–18 | 3 |

Each row has `cluster_name == name`, no parent/decorators, and
`is_dunder=false`. LOC extends through the line before the next recognized
column-zero declaration, or through end of file.

The heuristic misses ordinary `export function`, `export const`, indented or
nested declarations, many arrow forms, and scope relationships. It returns
`[]` for empty input, malformed input such as `export function broken( {`, and
an IIFE containing an indented function. These cases are indistinguishable
from a valid file with no findings and are the known AC-4.3/AC-4.5 defect to
retire rather than preserve.

## AR-3 pinned D3 oracle

Committed evidence:
`reports/portable-skill-ecosystem-completion/WP1/analysis-portfolio-spike.json`
(SHA-256
`eaec37c970c564483f8d0ca02325d6b570593b9b627c18865767d862ab922de1`).
Corpus: `tests/fixtures/analysis_portfolio_spike`, tree SHA-256
`da03a77d5818deb2c2acd531e3875ad4053ff278d8cc11f17784d57f38d2cf4f`.
Oracle SHA-256:
`bd6c74f03c2397ef5453a6756b3c40456454aced4f444f446869970ecd67a1e3`.
The corpus is two TypeScript files plus `tsconfig.json` and the oracle.

The schema-1 oracle is fixed as:

- definitions: `Item`, `Status`, `dispatch`, `initial`, `normalize`,
  `normalized`, `transition`;
- imports: `./state`, `./util`;
- calls: `normalize`, `transition`;
- writes: `item.status`;
- references: `Draft`, `Item`, `Published`, `Status`, `count`, `item`, `next`,
  `normalize`, `normalized`, `status`, `transition`, `value`.

| Candidate | Version/license | Supported facts | Committed cold/warm | Install bytes | Budget |
|---|---|---|---:|---:|---|
| Tree-sitter language pack | tree-sitter 0.26.0 + pack 1.12.5, MIT | definitions/imports/calls/writes; references explicit gap | 0.056645s / 0.041139s | 5,089,280 | P/R 1.0; warm ≤1s; ≤25MB |
| ast-grep, optional | 0.44.1, MIT | definitions/imports/calls/writes; references explicit gap | 0.115009s / 0.067535s | 154,339,105 | P/R 1.0; warm ≤6s; ≤200MB |
| TypeScript Compiler API | 5.9.3, Apache-2.0 | all five D3 families including references | 0.774711s / 0.620167s | 23,625,066 | P/R 1.0; warm ≤1s; ≤30MB |

Every supported committed metric is precision/recall 1.0. SCIP and LSP are
explicitly unsupported. TypeScript 7.0.2 is explicitly unsupported as the
stable compiler API, while remaining viable as a native guard. Execution
evidence is macOS arm64; other Tree-sitter wheels and ast-grep targets require
CI verification. Owners and deterministic install commands are present in
the committed JSON.

An offline rerun using the existing pinned temporary dependency trees produced
the same corpus hash, facts, metrics, versions, sizes, and unsupported entries.
Dynamic timings were Tree-sitter 0.080366s cold / 0.041107s warm, ast-grep
0.112679s / 0.073572s, and TypeScript API 0.656365s / 0.658697s. All declared
budgets passed. Rerun SHA-256:
`fc840a97fe65e666d3857ebba1650857dd3e53fb42dd8bfe88e117eca9bccca5`.

The D3 baseline does not record peak memory, variance, source locations, a
large fixture, or multi-platform executions. AC-4.6 refers to a predeclared
memory budget “from AC-1.7,” but the committed AC-1.7 budget block contains no
memory ceiling. WP4 must resolve that evidence/threshold gap explicitly rather
than silently inventing or waiving a passing threshold.

## AR-4 stable-finding identity inputs

Finding identity schema v2 hashes exactly:

`schema | provider | rule | language | normalized repository-relative path |
semantic_anchor | occurrence`

The ID is `f2_` plus 24 SHA-256 hex characters. Case policy is explicit.
`line`, severity/metrics/message (by ADR), and producer/tool version are
volatile and must not affect identity. Moves intentionally change identity;
`legacy_ids` carries migration continuity.

No current production path converts adapter facts into `FindingIdentity`.
WP4 facts nevertheless must preserve the inputs WP5 will need:

- stable provider and subject-language identifiers;
- canonical repository-relative file paths;
- a stable semantic anchor derived from syntax/semantics, not line number or
  rendered message;
- deterministic ordering so repeated equal anchors receive stable zero-based
  occurrences;
- source locations as evidence outside the hash.

Current Python and JS symbol order is source order; D3 probes deduplicate facts
into sets and sort strings, losing per-occurrence locations. The common WP4
fact contract therefore cannot use D3’s name-only ordering as sufficient AR-4
evidence.

## AR-5 failure oracle

| Failure | Baseline observation | Required WP4 disposition |
|---|---|---|
| Unsupported extension/capability | `get_adapter("file.rs")` is `None`; consumers test capability membership and skip. There is no request API. | Typed adapter/file/capability skip/error. |
| Malformed Python | Adapter returns `None`; consumer behavior varies from silent skip to warning/counter. | Typed parse failure with context. |
| Malformed/hidden JS/TS | Adapter returns `[]`, identical to clean. | Real parser plus typed parse/unsupported result; never clean zero. |
| Missing pinned Python dependency | D3 driver exits 1 with uncaught `KeyError: 'tree-sitter'`. | Typed missing-tool failure. |
| Missing ast-grep executable | Probe traceback is wrapped as a generic failed-command error; no normalized adapter/file/capability object. | Typed missing/broken-tool failure. |
| Tree-sitter parse error | Probe prints a path and exits nonzero, then the driver wraps the command. | Preserve path while adding adapter/capability context. |
| Corrupt JSON output | `_run_json` raises `JSONDecodeError`; top-level emits a generic error string. | Typed corrupt-output failure. |
| Rust/Go | Registry shim entries are `unsupported`; no adapters/facts exist. | Implement only the accepted consumer subset and enumerate all remaining gaps. |

## Requirements status at the baseline

| Requirement | Guaranteed at `db0fed1` | Pre-WP4 gap |
|---|---|---|
| AR-1 | Exact Python symbol shape, order, locations, class expansion, and syntax-failure sentinel are pinned. | Common imports/definitions/references/calls/writes and raw-AST consumer outputs are not golden-pinned. |
| AR-2 | All 21 production adapter consumers and their two requested capability shapes are inventoried above. | Future facts must remain tied to these named consumers or an explicit accepted downstream consumer. |
| AR-3 | Corpus, hash, oracle, selected portfolio, versions, licenses, owners, unsupported entries, install/runtime budgets, and deterministic commands are pinned and rerun. | Memory, variance, large-fixture, locations, and cross-platform evidence are absent. |
| AR-4 | Identity hash inputs and current source ordering/location behavior are pinned. | There is no fact-to-identity integration or stable occurrence/location golden. |
| AR-5 | Existing unsupported, malformed, missing, broken, and corrupt paths are characterized. | All are sentinel/generic paths rather than typed contextual results; JS malformed input can appear clean. |
| AC-4.1 | Existing adapters advertise two string capabilities. | No versioned six-family fact interface or per-request typed discovery. |
| AC-4.2 | D3 candidates and budgets are executable from pinned dependencies. | Selected providers are probes, not the runtime adapter substrate; platform gates remain incomplete. |
| AC-4.3 | Legacy JS-family extensions and coarse symbol locations are pinned. | Heuristic remains; exports, nested scopes, parser errors, accurate kinds/locations, and real parsing are missing. |
| AC-4.4 | Python legacy symbols are pinned; Rust/Go shim support is honestly `unsupported`. | Common Python facts and accepted Rust/Go fact subsets do not exist. |
| AC-4.5 | Some failures are nonzero or `None`. | No typed contextual error/skip; JS malformed input is false clean. |
| AC-4.6 | Small D3 facts are deterministic and current runtime/install budgets pass. | No small/large multi-language goldens, peak memory, variance gate, declared memory ceiling, or supported-platform matrix run. |

## Commands and results

All repository commands ran from the project root without network access:

```text
git rev-parse HEAD
db0fed19c7c783d04314dacbc4da73b7a4b3bbf7

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  -p no:cacheprovider tests/test_lang_adapter.py \
  tests/test_omnibus_language_adapters.py tests/test_finding_identity.py
32 passed in 0.05s

.venv/bin/python scripts/analysis_portfolio_spike.py \
  --python-site /tmp/engineering-skills-d3-spike-20260716/python \
  --node-modules /tmp/engineering-skills-d3-spike-20260716/node/node_modules \
  --output /tmp/wp4-baseline-db0fed1.json
exit 0; every declared budget passed

# Same driver with both dependency roots absent
exit 1; uncaught KeyError: 'tree-sitter'

# Valid pinned Python dependencies, absent ast-grep/Node dependency root
exit 1; generic failed-command error containing the child FileNotFoundError traceback
```

Key implementation hashes:

- `scripts/_lib/lang_adapter/base.py`:
  `19bab1f61747e8a8abe430c1515b81ee37dc828ef901b53165a2a5d86131f8ac`
- `scripts/_lib/lang_adapter/python_adapter.py`:
  `1d063a24eb76dfe632fe33f801bd1d8fbdd07dcd522fe2ef3f992c12af531ad2`
- `scripts/_lib/lang_adapter/javascript_adapter.py`:
  `f144f11826c105ef617eb1f0c81d031230b5e830a0eef083e14e20d2e1b7e769`
- `scripts/_lib/finding_identity.py`:
  `db30dc0257df209bb4af3dbf1dcc31b639fd5cd8e820c3e2dc071fda1abe412c`

This baseline is sufficient to begin WP4 implementation without treating a
legacy empty/sentinel result as success or changing consumer-visible Python
behavior accidentally. It is not acceptance evidence for any AC-4 criterion.
