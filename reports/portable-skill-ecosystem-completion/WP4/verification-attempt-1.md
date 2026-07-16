# WP4 fresh-scope verification attempt 1

Verifier: `/root/wp1_final_reverification`, Codex/GPT-5 (exact model variant not exposed)

Revision: `20291397412f66d24f918ee1b2949bad753282d6`; actual implementation
commit `e30fcb4fe0ae2fd194017bdc0c908554891ac9b2`.

Workspace state: clean at initial capture. Concurrent foreign WP2 work appeared
after verification began: `scripts/_lib/host_profile.py` (SHA-256
`aac34c776be7ab5020b1c924bfbbac6fb179b1cc369e97b0dece9e6f5b778284`)
and `tests/test_host_profile.py` (`69a28a7da3aeb0f2f55bea14eb7bb017667f7e6d08a14f2103cc3c42cb2639aa`)
became untracked, while automatic policy telemetry modified
`logs/agent_policy/test_runs.jsonl` (HEAD hash `626ff572...`, observed final
pre-report hash `c1378878...`). None was altered or removed. Because the
foreign test made the live-tree full suite fail collection against HEAD, the
exact committed tree was independently materialized with `git archive HEAD`
under `/tmp` and tested there using the required project virtualenv. This
report is the verifier's only intentional workspace write.

Platform: macOS 26.5.1 / Darwin 25.5.0 / arm64.

Toolchain: Python 3.11.10; pytest 9.0.3; PyYAML 6.0.3; Ruff 0.6.9;
tree-sitter 0.26.0; tree-sitter-language-pack 1.12.5; Node 22.21.1; npm
11.12.1. Runtime parser dependencies are exactly pinned in `requirements.txt`.

Work package: WP4

## Verdicts

- **AC-4.1: PASS** — Inspection found the versioned `LanguageAdapter.analyze`
  request interface, immutable normalized facts, per-provider language,
  extensions, provider/interface versions, capability discovery, and exactly
  the six required fact-family IDs. No framework/route facts are present.
  The hidden-path inventory still resolves to 23 importing paths: two adapter
  declarations plus 21 runtime consumers (one symbol consumer and 20 raw
  Python-AST compatibility consumers). The constants duplicate a selected
  subset of registry strings in Python, but their values exactly match the
  canonical registry and deliberately do not auto-enable future capabilities;
  this is an API alias surface rather than evidence of extra support.

- **AC-4.2: PASS** — The selected Tree-sitter provider is production runtime
  code and both parser packages are pinned. The exact D3 rerun preserved corpus
  SHA-256 `da03a77d...`; every supported family remained precision/recall 1.0.
  Warm time/install size were Tree-sitter 0.039719 s / 5,089,280 bytes,
  optional ast-grep 0.068865 s / 154,339,105 bytes, and TypeScript Compiler API
  0.638514 s / 23,625,066 bytes. All predeclared D3 budgets passed. SCIP/LSP
  and TypeScript 7's stable API remain explicitly unsupported; compiler
  semantics remain conditional as ADR 0039 permits because the 21-consumer
  inventory contains no semantic/type consumer.

- **AC-4.3: PASS** — Focused tests and direct inspection confirm a real
  Tree-sitter parser for exported functions, exported const arrows, classes,
  methods, nested functions/arrows, JSX, `.js/.mjs/.cjs/.ts/.tsx`, calls,
  writes, syntax references, parents, deterministic order, and source starts.
  Malformed TS raises contextual `parse_error`, and legacy hidden/indented JS
  is now found. The focused suite passed 45/45.

- **AC-4.4: PASS** — The clean-revision full suite passed and the legacy Python
  symbol oracle remains green. All 20 raw-AST consumers retain the same
  `CAP_PYTHON_AST`/`parse()` seam. Python normalized facts cover all six
  families. Rust and Go fixtures produce the accepted syntax subset, while
  requests for `analysis.type-facts` raise contextual
  `unsupported_capability` rather than guessing semantics.

- **AC-4.5: FAIL** — The ordinary unknown-capability, missing-loader,
  exception-raising parser, cooperative `TimeoutError`, wholly missing root,
  and malformed-source cases are typed. The boundary is nevertheless
  bypassable. A parser returning a root with `children` and `has_error` but no
  `named_children` escapes as raw `AttributeError`; a root whose `children`
  property raises escapes as raw `RuntimeError`. A parser whose `parse()`
  blocks does not have a substrate-enforced deadline: a verifier subprocess
  required an external one-second timeout instead of receiving
  `AnalysisFailure(tool_timeout)`. Also, adapter discovery for an unknown
  extension remains bare `None`; `.jsx`, although registered as a JavaScript
  extension in the canonical registry, likewise resolves to `None`. These are
  false-clean/untyped paths forbidden by AR-5 and AC-4.5.

- **AC-4.6: FAIL** — The regenerated product report passed its implemented
  checks and was deterministic, with no declared violation: small 431-byte
  fixture 0.004479 s reported cold / 0.004535 s warm mean / CV 0.011957 /
  129,112 Python bytes / 31,490,048 RSS bytes; large 3,457-byte fixture
  0.028326 s / 0.028017 s / CV 0.013788 / 686,269 Python bytes / 32,440,320
  RSS bytes. However, `build_report()` analyzes the D3 corpus before invoking
  either `_benchmark`; that analysis loads and exercises the TS parser. The
  first timed fixture run labeled `cold_seconds` is therefore not a cold
  provider/process measurement, so the cold gate is invalid. The committed
  goldens hash only capability/name/start-line/start-column/kind, omitting
  `end_line`, `end_column`, `parent`, and path. Python symbol facts additionally
  synthesize column/end-column as 1 (for example `BigService.get_samples`
  reports `(29,1)-(30,1)` while the AST span is `(29,5)-(30,18)`). Thus the
  evidence does not pin the interface's claimed precise locations. Finally,
  only Darwin-arm64 execution is recorded; an `ubuntu-latest` workflow
  configuration is not a linked passing multi-platform result. Determinism
  across supported platforms/tool versions remains unverified.

## Command evidence

```text
# First live-tree attempt after foreign WP2 test appeared
PYTHONDONTWRITEBYTECODE=1 .../.venv/bin/python -m pytest -q -p no:cacheprovider
ERROR collecting tests/test_host_profile.py: no _lib.host_profile in HEAD

# Exact clean HEAD from /tmp git archive
PYTHONDONTWRITEBYTECODE=1 .../.venv/bin/python -m pytest -q -p no:cacheprovider
464 passed, 2 skipped in 15.68s

PYTHONDONTWRITEBYTECODE=1 .../.venv/bin/python -m pytest -q \
  -p no:cacheprovider tests/test_analysis_facts.py tests/test_lang_adapter.py \
  tests/test_omnibus_language_adapters.py
45 passed in 0.42s

.../.venv/bin/python scripts/specs.py coverage portable-analysis-substrate
9 implemented, 5 documented, 0 lag/ahead/orphans

.../.venv/bin/python scripts/specs.py inventory-check portable-analysis-substrate
CLEAN

.../.venv/bin/python scripts/plans.py audit
OK — 7 plans, no drift

.../.venv/bin/python scripts/decisions.py audit
OK — 34 decisions, no drift

.../.venv/bin/python scripts/decisions.py link-check
OK — 34 decisions, all links resolve, 22 host-scoped

.../.venv/bin/ruff check scripts tests
All checks passed!

.../.venv/bin/python scripts/analysis_portfolio_spike.py \
  --python-site /tmp/engineering-skills-d3-spike-20260716/python \
  --node-modules /tmp/engineering-skills-d3-spike-20260716/node/node_modules \
  --output /tmp/wp4-verification-d3.xeAqgF
exit 0

.../.venv/bin/python scripts/analysis_fact_benchmark.py \
  --output /tmp/wp4-verification-product.tOpvUQ
{"passed": true, "violations": []}
```

Evidence hashes:

- `scripts/_lib/lang_adapter/base.py` = `4d65b2c2514148d54b3370a3f99c13d89af433de7d4cd991002bb70b5818865f`
- `scripts/_lib/lang_adapter/javascript_adapter.py` = `afcd1b5e3bc3564a8e59034634a16d4a50eb76255fcd453f7bb794dfc4985301`
- `scripts/_lib/lang_adapter/python_adapter.py` = `b14237907e5666b271c499963c5a81ba86c07167510dbf4d7f22d28a3daec328`
- `scripts/_lib/lang_adapter/systems_adapter.py` = `827eba39bb1f0c19408a33e12a5cabd78e72adf22fb15124cc9c91015bf87fa4`
- `scripts/analysis_fact_benchmark.py` = `2a5779be1b6f4f16b0830ada95cbce4bf2f0fdcb2fe2a4899aebfe8d20731e54`
- `requirements.txt` = `4bdcf735f006edf4b770ea744948920c78f485cd5be06a369fd4ad81ca6f76be`
- committed product benchmark = `cbe0a6e9f83ffbeb2995ca46dcf87085f0af942181a96cdb847f936c57123866`
- committed D3 rerun = `c513b9f06ba78f3e4bbabd5a71460c6ecc5a91a22226571ae743b21c3ad7df4b`
- regenerated product benchmark = `18c6735824f305266fb22cac17f078ff0260e50e3b94b13c5b36f41b6702a8d8`
- regenerated D3 rerun = `21b0df46cbfaa0565078295f73faad847aef8c76a7fcd3218f57925152704fa8`

Missing or ambiguous evidence:

- no real blocking-parser deadline test; the committed timeout test injects a
  cooperative `TimeoutError`;
- no malformed-root variants beyond a wholly missing root object;
- no linked Linux/Windows execution record or defined supported-platform
  matrix for AC-4.6;
- the 40-line/3,457-byte “large” fixture has no representativeness rationale;
- syntax `analysis.references` satisfies the pinned D3 name oracle, but its
  semantic strength is not encoded in the capability ID; compiler-backed
  semantic references remain conditional;
- the implementation evidence names nonexistent full revision
  `e30fcb41e04be7532d2fc5c1244ea7dc675d124a`; the actual `e30fcb4` commit is
  `e30fcb4fe0ae2fd194017bdc0c908554891ac9b2`.

Unsupported claims found:

- “timed-out ... requests raise contextual typed failures” is overstated for
  a parser that blocks without raising `TimeoutError`;
- “precise 1-based start/end locations” and “goldens pin facts and locations”
  are overstated for Python symbol columns/end-columns and omitted golden
  fields;
- the benchmark's `cold_seconds` label is false after the pre-measurement
  corpus warm-up;
- portable/multi-platform determinism is not established by a workflow
  configuration without a linked executed result.

Overall: **FAIL** — AC-4.5 and AC-4.6 have material gaps; WP4 must not move to
`verified`.
