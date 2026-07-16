# WP4 implementation evidence

Implementation base: `db0fed19c7c783d04314dacbc4da73b7a4b3bbf7`.
Implementation revision: `e30fcb41e04be7532d2fc5c1244ea7dc675d124a`.
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
- `AnalysisFailure` distinguishes unsupported capability, parse error, missing
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
  methods, nested functions/arrows, `.js/.mjs/.cjs/.ts/.tsx`, JSX, malformed
  input, calls/writes/references, parent scope, and exact locations. The known
  hidden/indented under-detection is retired.
- **AC-4.4:** Existing Python symbol tests remain byte-shape compatible and the
  new Python golden pins all six normalized families. Rust and Go providers
  expose the accepted syntax subset; `analysis.type-facts` remains an explicit
  unsupported capability.
- **AC-4.5:** Fault injection proves unsupported, missing, broken, timed-out,
  corrupt, and malformed requests raise contextual typed failures rather than
  return zero facts.
- **AC-4.6:** Hash-backed goldens pin facts and locations for Python, TS, Rust,
  and Go. The product benchmark runs seven times on committed small/large TS
  fixtures and enforces the additive cold/warm/RSS/Python-memory/variance gates
  recorded in the spec before measurement.

## Verification results

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_analysis_facts.py tests/test_lang_adapter.py \
  tests/test_omnibus_language_adapters.py
45 passed in 0.41s

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
465 passed, 1 skipped in 17.62s

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
| small | 431 B | 0.004518 s | 0.004830 s | 0.029549 | 128,831 B | 31,096,832 B |
| large | 3,457 B | 0.028593 s | 0.029572 s | 0.009900 | 686,157 B | 31,997,952 B |

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
