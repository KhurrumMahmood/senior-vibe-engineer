# TypeScript `find-complexity-hotspots` learning packet

Implementation revisions: `63a3ac0f869b08b70278605047e8b1bfaadd6768`
(`Add TypeScript complexity hotspot detection`) and `886ded0` (project-relative
exclusion repair) on `codex/ts-complexity`, based on `05711c4`. This is a
post-B4, family-local TypeScript body-analysis packet.

## Accepted invariant and scope

The selected skill remains a read-only advisory scan. Python preserves its
existing six bands: `django-query-in-loop`, `nested-loop`,
`membership-scan-in-loop`, `sort-in-loop`, `repeated-scan-in-loop`, and
`high-branch-function`. Its JSONL/final report contract was made
self-contained, not redesigned.

TypeScript v1 adds only `high-branch-function` records for `.ts`/`.tsx`
function declarations, methods, and block-bodied arrows. For each function the
Compiler API establishes the function span, LOC, and a syntax-only branch score.
The score counts the direct counterparts of the existing Python branch
invariant: `if`, all loop forms, `try`/`catch`, `with`, `switch`, `&&`/`||`,
and ternaries. Nested function bodies do not contribute to their enclosing
function's score.

Records are explicitly marked `language: "typescript"` and
`analyzer: "typescript-compiler-api"`; the final Markdown repeats this
provenance. The report is a structural/readability lead, not a runtime-cost or
safe-refactor claim.

Excluded: ORM, React, Node, and framework semantics; receiver/type/API claims;
module resolution; function expressions; expression-bodied arrows; overload and
declaration signatures without a body; `.d.ts`; and generated, vendor,
minified/bundle, test/spec, and fixture paths. `--include-tests` remains a
Python-only switch. Missing Node, missing host-local `typescript`, malformed
parser JSON, and TS syntax errors return 2 rather than producing a false clean
scan.

## B4 reuse decision

B4 proved that a selected skill can resolve the host's pinned `typescript`
package and obtain reliable `createSourceFile` spans without a tsconfig or
TypeChecker. This implementation copied only the exact fitting local syntax
pieces into its own bundled launcher: host `package.json` resolution through
`createRequire`, line/span calculation, and parenthesized/`as`/assertion/
`satisfies` initializer unwrapping for arrows.

It deliberately did **not** reuse B4's top-level symbol extractor. That
contract is top-level names/classes; complexity needs function bodies, direct
control-flow traversal, and nested-function exclusion. Reusing the B2T semantic
state parser would also overclaim receiver/type facts and couple an installed
skill to another selected directory. No shared adapter, fact layer, catalog, or
router changed. The two accepted consumers prove only a common deployment
pattern, not an identical reusable syntax interface.

## Fixture and outcome proof

`tests/fixtures/find-complexity-hotspots-typescript` locks TypeScript 5.9.3.
It has three positive shapes in `src/complexity.ts`: a function declaration,
`ComplexityService.methodHotspot`, and a block-bodied arrow. Each scores 18 over
23 LOC. `clean.tsx`, expression-bodied arrows, overloads, declarations, and
generated/vendor/minified/spec/test sources are all present in the scanned host
and must stay absent.

`tests/test_find_complexity_hotspots_typescript.py` reaches the final report,
not merely the parser. It asserts exact reported files/symbols, score, language
and analyzer provenance, and start/end source spans. It also proves:

- the historical Python smoke still emits all six bands and leaves the good
  fixture clean;
- invalid TypeScript, absent `typescript`, and absent `node` fail with rc 2;
- a copied selected skill runs under `python -I -S` with no `scripts/_lib` or
  sibling `_common` import;
- `npm ci --offline --ignore-scripts`, `npm run typecheck` (`tsc --noEmit`),
  and `npm test` are native fixture checks;
- `skills@1.5.19` installs only this skill, and its extracted installed
  resolver/run commands execute verbatim using host `python3` rather than a
  toolkit venv.

Executed verification after `886ded0`:

```text
.venv/bin/python -m pytest -q tests/test_find_complexity_hotspots_typescript.py
# 7 passed

.venv/bin/ruff check .claude/skills/find-complexity-hotspots/scripts/detect.py \
  .claude/skills/find-complexity-hotspots/scripts/run.py \
  tests/test_find_complexity_hotspots_typescript.py
# All checks passed

.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/smoke.py
# OK - 6 bad fixture findings, good fixture clean

node --check .claude/skills/find-complexity-hotspots/scripts/detect_typescript_complexity.mjs
.venv/bin/python -m py_compile \
  .claude/skills/find-complexity-hotspots/scripts/detect.py \
  .claude/skills/find-complexity-hotspots/scripts/run.py
.venv/bin/python scripts/skill_meta.py lint
# all passed; metadata: OK — 76 skills, 76 declaring new contract
```

## Fresh installed journey (D6)

A fresh non-context agent received an installed selected-skill copy at
`/private/tmp/find-complexity-hotspots-forward.NJDE6E/host/.agents/skills/find-complexity-hotspots`,
the raw locked TypeScript host, and only this task:

> Audit this TypeScript project for complex functions. Produce the skill's
> final report artifacts, then tell me which findings deserve engineering
> review and why. Do not edit source files.

It used the installed workflow, made no source edit, wrote
`reports/find-complexity-hotspots/scan-20260719-093930`, and independently
returned `measure-first`: the three score-18 findings deserve a single
maintainability/behavior-coverage review cluster, but no performance conclusion
is justified without input sizes or call frequency. The final artifacts hash to:

- `detections.jsonl`: `9fc7c0bb2efb56adedc4ae18deafd4c84fe1829a3e7ebc189c29ac2bb1722b5c`
- `report.md`: `f0b20f1059cb98bba7679f9d42dcb31d4689c269343745c9e699f88407a05459`
- `findings.json`: `f1ff1ccd938f0f5fa55a50b304a7902e89d363b38ab835ee5ce73d73bc23eff6`

The same host subsequently passed `npm run typecheck` and `npm test`. The
agent's useful final artifact, no-source-edit observation, and independent
`measure-first` reasoning close D6 without leaked expected output.

## Adversarial exclusion repair

The first independent review found that excluded-source policy was evaluated
relative to the caller's narrowed target. Directly targeting `vendor/`,
`generated/`, `tests/`, or a file beneath them therefore removed the path token
that was supposed to exclude it. Revision `886ded0` anchors the policy to
`--project-root`, covers direct directory and file targets across dependency,
build, generated, fixture, spec, test, vendor, coverage, and report trees, and
adds a regression that exercises every category. This is transferable to all
language adapters: ignore policy is a property of the host project, not of the
invocation target.

## D1–D8 closeout

| Gate | Evidence | Status |
|---|---|---|
| D1 scope honesty | `SKILL.md` and frontmatter declare the narrow syntax-only TS v1 and exclusions. | pass |
| D2 Python oracle | Existing six-band `smoke.py` passes. | pass |
| D3 TypeScript outcome | Locked positive/clean/must-not-fire host reaches final report/JSON with spans and provenance. | pass |
| D4 change/guard | Not applicable: this advisory detector proposes neither a source change nor guard. | n/a |
| D5 installed closure | Copied `-I -S` and stock installed-command tests pass with host Python/Node only. | pass |
| D6 fresh forward task | Fresh installed journey above produces final artifacts and useful conclusion. | pass |
| D7 regression/conformance | Seven focused tests, Ruff, native checks, metadata lint, compile/syntax, and diff check pass. | pass |
| D8 learning handoff | This MD/JSON pair records decisions, evidence, adversarial repair, and prerequisites. | ready for re-review |

## What generalized, what did not

Generalized: pinned host-local TypeScript resolution; explicit analyzer
provenance; positive/clean/must-not-fire fixtures; native typecheck/test;
copied/stock-install replay; and a final-output rather than parser-only oracle.

Did not generalize: Python Django/ORM bands, TypeScript control-flow syntax,
branch scoring, source path policy, framework interpretation, TypeChecker facts,
and any global parser cache. Keep `detect_typescript_complexity.mjs`
family-local.

## Next-language prerequisites

Do not claim another language from this packet. A later language must provide
all of the following before joining this invariant:

| Language | Native syntax tool | Required representation and fixture | Deferred semantic gap |
|---|---|---|---|
| Rust | `syn`, rustc parser, or rust-analyzer syntax tree | named functions, impl methods, closures with bodies; clean/generated/test/macro-adjacent corpus | macros, trait dispatch, async lowering |
| Go | `go/parser` / `go/ast` | functions and receiver methods; clean/vendor/generated/`_test.go` corpus | build tags, generated markers, interface dispatch |
| Java/Kotlin | compiler parser or language-server syntax facts | methods, lambdas, overload/declaration boundary, generated/test corpus | overload resolution, annotations, companion/nested types |
| C# | Roslyn | methods, local/lambda bodies, partial/generated/test corpus | partial/source-generated type aggregation |
| Ruby | Prism or Ripper | methods, blocks, reopened-module/test/generated corpus | metaprogrammed methods and runtime reopening |

Every candidate needs a pinned local tool, an explicit score mapping limited to
established constructs, exact function spans, native type/test command,
excluded-source policy, copied selected-skill replay, and a fresh final-report
task. A TypeChecker or resolver is required only if a later claim explicitly
needs identity/type semantics.

## Residual risk and next decision

A branch score is intentionally not a performance score. Deep but legitimate
validation/policy code can fire; algorithmic costs hidden in calls cannot.
TypeScript v1 does not inspect expression arrows, function expressions, JSX
meaning, decorators, aliases, calls, imports, types, receivers, or framework
conventions. It may therefore under-report and must not be used as a safety or
performance verdict.

Accept this isolated family as additive Python + narrow TypeScript support.
Keep B4 and this body walker separate. Consider a shared syntax component only
after a third accepted consumer demonstrates the same body traversal, span,
host-resolution, failure, and installed-closure contract—not merely that it
also uses the TypeScript Compiler API.
