# B4 TypeScript `find-omnibus` learning packet

Implementation revision: `c0349abb1595375c2890b3c50b4b699234e9d2ca`
(`c0349ab`, `Add first-class TypeScript omnibus detection`). Closure repair:
`e7da0b117ade8c58da73a86936d90f718669ae0f` (`e7da0b1`, `Make omnibus
installed closure self-contained`).

## Invariant and scope

The detector reports a module as an omnibus candidate only when trustworthy
top-level symbols form at least four independently named responsibility
clusters. TypeScript v1 covers ESM `.ts` and `.tsx` top-level function
declarations, typed arrow/function-expression variables, and named classes.
It produces detector JSONL, collapsed candidates, and a scout-backed final
report. Records name `language: "typescript"` and
`analyzer: "typescript-compiler-api"`.

Excluded: Python/Django framework semantics, module resolution, export/re-export
identity, type-checker facts, React/Node/ORM conventions, nested declarations,
anonymous default exports, and automatic responsibility judgment. Scouts still
decide facets versus independently understandable domains. Python AST and
legacy JavaScript heuristic behavior remain separate and preserved.

## Reference repair, tool decision, and closure

The reference detector had two portability defects: it imported repository
`scripts/_lib`, and it routed `.ts`/`.tsx` through a column-zero JavaScript
heuristic that missed normal ESM exports and labeled TypeScript as JavaScript.
The reporter also imported sibling `_common` telemetry. The first closeout
incorrectly claimed complete installed closure after those script imports were
removed: the selected `SKILL.md` still hard-coded the source-tree `.claude`
path and Stage 3 referenced an uninstalled `_common` dispatcher,
`tools/code_agent`, a host adapter, another skill's interface guidance, and a
toolkit venv. The D5 adversarial review rejected that claim.

Repair `e7da0b1` makes the whole selected workflow installation-relative. The
documented resolver supports both stock `.agents/skills/find-omnibus` and the
source-tree `.claude/skills/find-omnibus`, all Python commands use the host
venv when present and otherwise `python3`, and Stage 3 uses the host's standard
sub-agent capability directly. Its complete prompt, facet/domain rule,
false-positive list, deletion test, and locality guidance are bundled in the
selected skill. Python, the legacy JavaScript heuristic, TypeScript, collapse,
and reporting remain independent runtime paths, and frontmatter truthfully
declares `language: any` plus all three scanners.

`detect_typescript_symbols.mjs` is a family-local Compiler API launcher. It
resolves `typescript` from the host project's `package.json` and calls
`createSourceFile` with TS or TSX script kind. This is the least semantic tool
that gives exact top-level statement spans and parse diagnostics. It needs no
`tsconfig`, `Program`, `TypeChecker`, ts-morph, tree-sitter, ast-grep, or shared
adapter.

B2T previously proved project-local Compiler API resolution, but its semantic
state detector does not satisfy this syntax-span contract and importing it
would couple a selected skill to another installation. No shared parser or
fact platform was added. Required host prerequisites are Node and a
project-local `typescript` package. Missing Node/package or TypeScript syntax
errors stop Stage 1 with exit code 2 instead of silently under-detecting.

## Fixture and implementation evidence

`tests/fixtures/b4_typescript_omnibus` pins TypeScript 5.9.3 and contains:

- positive `.ts` and `.tsx` ESM modules with typed exported functions, typed
  arrows, and classes across invoice, shipment, customer, and inventory;
- a cohesive TSX invoice module that stays clean;
- generated, vendor, minified, `*.spec.ts`, and `tests/` must-not-fire shapes;
- native `tsc --noEmit` and Node test commands.

`tests/test_omnibus_typescript.py` proves detect → collapse → scout-backed
report semantics, structured TypeScript provenance, clear syntax-error
failure, copied-directory execution under `python -I -S`, and the pinned stock
selected-skill installation. The stock-install test extracts the resolver and
stage commands verbatim from the installed `SKILL.md`, runs them through the
final report boundary, and asserts the resulting detections, scouts, report,
and findings.

```text
.venv/bin/python -m pytest -q \
  tests/test_omnibus_language_adapters.py tests/test_omnibus_typescript.py \
  tests/test_skill_taxonomy.py
# 14 passed

.venv/bin/ruff check .claude/skills/find-omnibus/scripts/detect.py \
  .claude/skills/find-omnibus/scripts/report.py tests/test_omnibus_typescript.py
# All checks passed

node --check .claude/skills/find-omnibus/scripts/detect_typescript_symbols.mjs
.venv/bin/python -m py_compile \
  .claude/skills/find-omnibus/scripts/detect.py \
  .claude/skills/find-omnibus/scripts/collapse.py \
  .claude/skills/find-omnibus/scripts/report.py
# passed
```

The host fixture runs `npm ci --offline --ignore-scripts`,
`npm run typecheck`, and `npm test`. The final test artifact contains two
TypeScript candidates, each with `and_count: 3` and all four domain clusters;
the cohesive and excluded files are absent.

## Independent installed forward journey (D6)

A fresh non-context agent received the raw TypeScript host, the installed
selected skill, and only this natural task:

> Audit this TypeScript project for modules that combine too many unrelated
> responsibilities. Produce the skill's final report artifacts, explain which
> finding deserves review and why, and do not edit source files.

The pinned stock command installed exactly `find-omnibus` into a disposable
host. The fresh agent independently completed all four pipeline stages and
produced two valid `confirmed_omnibus` verdicts for `src/omnibus.ts` and
`src/omnibus.tsx`. Both have four confirmed domains, useful decomposition
sketches, and no unverified records. The final report recommends reviewing
`src/omnibus.ts` first.

Evidence root:
`/private/tmp/find-omnibus-ts-user-journey/evidence`

- Full command transcript SHA-256:
  `dd43e393d234bd057dc7dddbbf107df0938baf2aff87f66044eb5d1baaade83b`
- Natural task SHA-256:
  `e7c5ddf7a6ae4c7469d5ebb96de4019715f2cbe43ba872993fe0009b405cf5f1`
- Final report:
  `/private/tmp/find-omnibus-ts-user-journey/host/reports/omnibus/scan-20260719-014247/report.md`
  (SHA-256 `27dd23e51cd01b8ed9fbed846000489d1fdb35245ac795194cdea96efc2a6db4`)
- Final findings JSON SHA-256:
  `a11d96c2bb26af22a9fed712968dc5d6811967e1c2c484326e9c3275c43e956f`
- Before and after source manifests are identical; both files have SHA-256
  `4cd52d4ba33ea79e828025f5c2d7ef7fca49261ddad934a5896af7d825553462`.
- Installed-file inventory SHA-256:
  `d437d555158c66a66ad8156fbdf2540fe5ee91e1d30baae5af583aa562568f1d`.

D6 established that the final artifact and verdict were useful and that the
source manifest remained unchanged. It also exposed two closure defects: path
translation from documented `.claude` commands to the stock `.agents` install,
and an unavailable documented dispatcher path. Those defects made the first
closure claim false even though the agent worked around them. Repair
`e7da0b1` converts both observations into installed-copy regression coverage.

## False-positive boundary and portability

TypeScript exclusions are explicit and evaluated relative to the scan target:
`vendor/`, `generated/`, `tests/`, `test/`, `__tests__/`, and `fixtures/`
directories; declaration, minified, bundle, generated, spec, and test filename
patterns. `InvoicePanel.tsx` has several exported shapes in one domain and
stays clean. Files with only singleton clusters remain below the existing
`and_count >= 3` threshold.

The clustering/report schema, copied-install replay, and
positive/negative/must-not-fire test structure generalized. Python god-class
method expansion, JavaScript column-zero extraction, TypeScript compiler
syntax, re-exports, and framework idioms did not.

Before another language claim, Rust, Go, Java/Kotlin, C#, and Ruby each need a
native parser with exact top-level declaration spans, a four-domain exported
module, a cohesive module, generated/vendor/test exclusions, and a copied
installed replay. Macro expansion, partial types, overloads, and dynamic
metaprogramming remain language-specific gaps.

## User experience and next decision

The selected installation is one skill plus Node and the host's locked
TypeScript. It has no toolkit venv, repository `scripts/_lib`, sibling
`_common`, host adapter, external dispatcher, undeclared network dependency,
or uninstalled skill dependency. Its commands resolve either supported install
root verbatim. Stage 3 asks for concurrent standard sub-agents when capacity
allows and explicitly permits serial dispatch when it does not; capacity now
affects latency, not the required mechanism or verdict source.

Residual detector risks remain explicit: anonymous/default/re-export
surfaces, nested declarations, and semantic module resolution are out of
scope.

B4 is complete through D1-D8 at implementation revision `c0349ab` and closure
repair `e7da0b1`, plus this canonical learning closeout. Keep the TypeScript
parser family-local. Extract a shared syntax contract only after a second
accepted consumer demonstrates the same top-level span and host-resolution
needs.
