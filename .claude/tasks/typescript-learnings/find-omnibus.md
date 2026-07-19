# B4 TypeScript `find-omnibus` learning packet

Revision: pending B4 implementation commit on `codex/ts-omnibus`.

## Invariant and scope

The detector reports a module as an omnibus candidate only when trustworthy
top-level symbols form at least four independently named responsibility
clusters. TypeScript v1 covers ESM `.ts` and `.tsx` top-level function
declarations, typed arrow/function-expression variables, and named classes.
It produces the ordinary detector JSONL, collapse candidates, and final
scout-backed report; records name `language: "typescript"` and
`analyzer: "typescript-compiler-api"`.

Excluded: Python/Django framework semantics, module resolution, export/re-export
identity, type checking facts, React/Node/ORM conventions, nested declarations,
anonymous default exports, and responsibility judgment itself. The scout still
decides facets versus real domains. Python AST and legacy JavaScript heuristic
contracts remain separate and unchanged.

## Tool decision and closure

`detect_typescript_symbols.mjs` is a family-local Compiler API launcher. It
resolves `typescript` from the host project's `package.json` and calls
`createSourceFile` with TS or TSX script kind. This is the least semantic tool
that gives exact top-level statement spans and detects parse errors; no
`tsconfig`, `Program`, `TypeChecker`, ts-morph, tree-sitter, ast-grep, or shared
adapter is needed for this invariant.

The first semantic B2T family already proved project-local Compiler API
resolution, but its state detector's contract does not fit symbol-span
extraction. Reusing it would also make a selected `find-omnibus` install depend
on another skill. No shared parser/platform was added. The copied skill owns
the Python extractor, JavaScript heuristic, TypeScript launcher, collapse, and
reporter; `report.py` no longer imports sibling `_common` telemetry code.

Required TypeScript host prerequisites are Node and a project-local
`typescript` package. Missing package, missing Node, or TypeScript syntax
errors stop Stage 1 with exit code 2 rather than silently under-detecting.

## Fixture and outcome evidence

`tests/fixtures/b4_typescript_omnibus` locks a TypeScript 5.9.3 host and
contains:

- positive `.ts` and `.tsx` ESM modules, each with typed exported functions,
  typed arrows, and classes across invoice, shipment, customer, and inventory;
- a cohesive TSX invoice module that stays clean;
- must-not-fire generated, vendor, minified, `*.spec.ts`, and `tests/` shapes;
- a native `tsc --noEmit` plus Node test command.

`tests/test_omnibus_typescript.py` proves the full detect → collapse →
scout-backed report outcome, structured TypeScript provenance, native typecheck
and test, clear syntax-error failure, copied-directory execution under
`python -I -S`, and the pinned stock selected-skill installation:

```text
DO_NOT_TRACK=1 npx --yes skills@1.5.19 add <checkout> \
  --skill find-omnibus --agent codex --copy -y
```

Observed implementation verification:

```text
.venv/bin/python -m pytest -q \
  tests/test_omnibus_language_adapters.py tests/test_omnibus_typescript.py
# 8 passed

.venv/bin/python -m pytest -q \
  tests/test_omnibus_language_adapters.py tests/test_omnibus_typescript.py \
  tests/test_skill_taxonomy.py
# 11 passed

.venv/bin/ruff check .claude/skills/find-omnibus/scripts/detect.py \
  .claude/skills/find-omnibus/scripts/report.py tests/test_omnibus_typescript.py
# All checks passed

node --check .claude/skills/find-omnibus/scripts/detect_typescript_symbols.mjs
.venv/bin/python -m py_compile .claude/skills/find-omnibus/scripts/{detect,collapse,report}.py
# passed
```

The fixture host runs `npm ci --offline --ignore-scripts`, `npm run typecheck`,
and `npm test` before each outcome execution. Its report has two confirmed
TypeScript candidates (`src/omnibus.ts`, `src/omnibus.tsx`), `and_count: 3`,
and all four responsibility clusters; no excluded or cohesive module appears.

## False-positive boundary and portability

TypeScript exclusions are explicit and evaluated relative to the requested
scan target: `vendor/`, `generated/`, `tests/`, `test/`, `__tests__/`, and
`fixtures/` directories; declaration, minified, bundle, generated, spec, and
test filename patterns. The clean `InvoicePanel.tsx` has multiple exported
shapes in one domain and stays clean. Files with only singleton clusters stay
clean by the existing `and_count >= 3` rule.

The common clustering/report schema, copied-install replay shape, and
positive/negative/must-not-fire corpus generalized. Python god-class method
expansion and JavaScript column-zero behavior did not. TypeScript compiler
facts, re-exports, and framework idioms remain variant-specific.

Before a Rust, Go, Java/Kotlin, C#, or Ruby claim, each needs a native parser
with top-level declaration spans, a four-domain exported-module fixture, a
cohesive module, generated/vendor/test exclusions, and a copied-install replay:

- Rust: rust-analyzer/rustc parser; functions, impl blocks, macro boundary.
- Go: `go/parser`; package-level functions/types and generated-file boundary.
- Java/Kotlin: compiler/parser; classes, top-level declarations, overloads.
- C#: Roslyn; partial classes and generated-source boundary.
- Ruby: Prism/Ripper; modules/classes and metaprogramming boundary.

## User experience, risk, and next decision

The installed path is one selected skill, Node, the host's locked TypeScript,
and the detector command; it has no toolkit venv, repository `scripts/_lib`,
or sibling `_common` runtime dependency. The residual risks are intentionally
visible: no anonymous/default/re-export symbol support, no nested span model,
and no semantic/module-resolution claim.

**D6 status: pending independent fresh forward replay.** The prepared sandbox
is `/tmp/b4-omnibus-forward.idzVeC`, with raw host at `host/` and a stock
installed selected skill at `stock/.agents/skills/find-omnibus`. It was
prepared without changing host source. The fresh agent must receive only that
installed skill, raw host, and the natural request to audit unrelated module
responsibilities; it must create its own final report under `artifacts/`.

Recommendation: accept this as one family-local syntax consumer only after the
fresh replay. Do not extract a shared TypeScript parser until a second accepted
family demonstrates this exact top-level symbol-span and host-resolution
contract.
