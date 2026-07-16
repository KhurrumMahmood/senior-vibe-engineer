# WP4 implementation evidence

> **Superseded AC-4.6 evidence:** This report and
> `analysis-fact-benchmark.json` preserve the initial schema-v1 implementation
> history only. Their synthetic `large` fixture, platform narrative, timings,
> and claim that the file is current were superseded after verification attempt
> 2. Current AC-4.6 evidence begins with `ac-4.6-repair-evidence.md` and its
> linked schema-v2 platform reports; later verification attempts remain the
> authoritative disposition when they identify further repair work.

Implementation base: `db0fed19c7c783d04314dacbc4da73b7a4b3bbf7`.
Initial implementation revision: `e30fcb4fe0ae2fd194017bdc0c908554891ac9b2`.
Verification-gap repair revision: `d12b730a4afc9bb403f7a2b78c70e5629691047e`.
This is implementer evidence for fresh-context verification; it is not the
independent PASS record required to move WP4 to `verified`.

## Delivered contract

- Analysis interface v1 uses the canonical `analysis.*` capability IDs for
  symbols, imports, definitions, references, calls, and writes. Providers
  publish an interface version, provider version, language, extensions, and
  discoverable capability set.
- Immutable facts include capability, name, canonical caller-supplied path,
  precise 1-based start/end locations, kind, and optional parent. Results are
  deterministically sorted and serializable.
- `AnalysisFailure` distinguishes unsupported language/capability, parse error, missing
  tool, tool failure, tool timeout, and corrupt parser output, always including
  adapter, file, capability, and detail.
- Pinned Tree-sitter 0.26.0 plus language-pack 1.12.5 replaces the JavaScript/
  TypeScript heuristic and provides syntax facts for JS, TS/TSX, Rust, and Go.
  Python keeps its exact legacy symbol/AST behavior behind the same fact API.
- The 20 raw-Python-AST consumers retain their compatibility seam. The omnibus
  consumer now reports `javascript-syntax`; no other call-site change was
  required.

## Acceptance mapping

- **AC-4.1:** `LanguageAdapter.analyze` is versioned, request-based, and limited
  to the six registry fact families. Framework facts are absent. The corrected
  baseline inventories 21 production consumers and shows why the raw Python
  tree remains a compatibility-only capability.
- **AC-4.2:** The selected Tree-sitter portfolio is now a runtime dependency,
  not a probe. The exact D3 driver was rerun to `d3-rerun.json`; all candidate
  precision/recall/runtime/install budgets pass and the corpus hash is
  unchanged. Optional ast-grep, conditional native compiler semantics, and
  deferred SCIP/LSP retain ADR 0039's dispositions.
- **AC-4.3:** Parser tests cover exported functions/const arrows, classes,
  methods, nested functions/arrows, `.js/.mjs/.cjs/.jsx/.ts/.tsx/.mts/.cts`, JSX, malformed
  input, calls/writes/references, parent scope, and exact locations. The known
  hidden/indented under-detection is retired.
- **AC-4.4:** Existing Python symbol tests remain byte-shape compatible and the
  new Python golden pins all six normalized families. Rust and Go providers
  expose the accepted syntax subset; `analysis.type-facts` remains an explicit
  unsupported capability.
- **AC-4.5:** Fault injection proves strict unsupported-extension discovery,
  missing/broken tools, cooperative and actually blocking timeouts, malformed
  root variants, and malformed source all raise contextual typed failures.
  Tree-sitter parsing has a substrate-enforced five-second deadline, and the
  public provider wrapper converts unexpected traversal/output exceptions into
  `corrupt_output` instead of leaking or returning zero facts.
- **AC-4.6:** Hash-backed goldens now hash every fact field, including path,
  end location, and parent. Python symbol facts derive precise columns and end
  spans from their original AST nodes. Cold time is measured in a fresh child
  process including interpreter/provider startup; six separate same-process
  runs supply warm mean/variance. The report declares Darwin-arm64 as the only
  executed platform, Linux as a candidate that cannot be claimed until it
  executes, and Windows as outside the current release contract.

## Verification results

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_analysis_facts.py tests/test_lang_adapter.py \
  tests/test_omnibus_language_adapters.py
52 passed in 0.53s

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
477 passed, 1 skipped in 16.86s

.venv/bin/python scripts/specs.py coverage portable-analysis-substrate
9 implemented, 5 documented, no lag/ahead/orphans

.venv/bin/python scripts/specs.py inventory-check portable-analysis-substrate
CLEAN

.venv/bin/python scripts/plans.py audit
OK — 7 plans, no drift

.venv/bin/python scripts/decisions.py audit
OK — 34 decisions, no drift

.venv/bin/python scripts/decisions.py link-check
OK — 34 decisions, all links resolve, 22 host-scoped

.venv/bin/ruff check scripts tests
All checks passed!
```

The current product benchmark records:

| Fixture | Input | Cold | Warm mean | Warm CV | Peak Python | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| small | 431 B | 0.084476 s | 0.004756 s | 0.024436 | 124,982 B | 31,866,880 B |
| large | 3,457 B | 0.081308 s | 0.028097 s | 0.011455 | 666,682 B | 32,768,000 B |

All five D3 fact families are precision/recall 1.0. The runtime install is
5,089,262 bytes. Every declared product and D3 budget passes with no violation.

## Evidence and limitations

- Baseline: `reports/portable-skill-ecosystem-completion/WP4/baseline.md`.
- Product benchmark:
  `reports/portable-skill-ecosystem-completion/WP4/analysis-fact-benchmark.json`.
- Exact D3 rerun:
  `reports/portable-skill-ecosystem-completion/WP4/d3-rerun.json`.
- Goldens: `tests/fixtures/analysis_facts/golden/`.

Execution evidence here is Darwin arm64 with Python 3.11.10. The repository CI
installs the exact requirements and runs the full suite on `ubuntu-latest`, but
that remote run is not claimed by this local record. The support state remains
experimental until WP8's registry-pinned conformance issuer can validate all
declared surfaces. No current named consumer requires semantic type facts or
cross-file definition resolution; ADR 0039 therefore keeps the TypeScript
Compiler API conditional rather than imposing a Node dependency on every host.
The product benchmark SHA-256 at the repair revision is
`a13e8b0b5e0a1159048b49bd711c53692086e305fbebb1d380acd5dc7e8aabab`.
