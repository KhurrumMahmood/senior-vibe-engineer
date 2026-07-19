# TypeScript `find-dormant` learning packet

Implementation revision: `46a16c7` (`Add TypeScript find-dormant review
scan`) on `codex/ts-find-dormant`, based on `0e4eb68`. This is an additive,
family-local TypeScript v1: the historical Python detector and scout pipeline
remain unchanged.

## Accepted v1 contract

The TypeScript branch reports only non-exported **top-level** functions,
classes, and function-valued variables with zero TypeChecker-resolved static
symbol references in eligible `.ts`/`.tsx` project sources. Its final artifacts
are `reports/find-dormant/<scan>/report.md` and `findings.json`.

Every static result has `verdict: review_required`,
`recommendation: human_review_only`, and a dynamic/external reachability
uncertainty. The final summary always has `certain_delete: 0`. Matching string
names are separately emitted as `uncertain`, not as review candidates. Thus a
static scan cannot imply that a deletion is safe.

Excluded from this v1: routes/endpoints, error swallowing, source changes,
dynamic imports, external consumers, registries, event handlers, framework
callbacks, runtime/module-loader reachability, method/nested implementation
analysis, cross-project completeness, and framework/API identity. A project
with unresolved static module specifiers produces a visible `partial` report;
missing/invalid tsconfig, missing host compiler, and syntax errors fail with
exit 2.

## Tool and containment decision

`detect_typescript_dormant.mjs` is one family-local Compiler API consumer. It
resolves the `typescript` package from the host's `package.json`, parses the
named tsconfig, builds a `Program`, gets a `TypeChecker`, enumerates exports,
and compares declaration/reference symbol identity across eligible source
files. This distinguishes a direct callback/registry/event/framework reference
from a merely textual name without inventing runtime coverage.

The accepted `map-subsystem` resolver supplied only the demonstrated pattern:
host-pinned `typescript` loading, a named tsconfig, `Program`/`TypeChecker`,
project-relative exclusions, symlink rejection, and atomic artifacts. Its map
schema and module-edge facts were not imported. There is no shared parser
platform: dormant analysis has a different reference, uncertainty, final-report,
and installed-closure contract.

The report directory must stay beneath `reports/find-dormant/`; every existing
path component is checked for symlinks before output is written. Broad traversals
skip symlinks, direct symlink targets fail, and excluded directories/files stay
excluded even when directly targeted.

## Fixture and final-output proof

`tests/fixtures/find-dormant-typescript/host` locks TypeScript 5.9.3. It
contains one unreferenced private function, a directly used private function,
exported API, registry/event/framework callback references, a string-addressed
dynamic uncertainty, a TSX direct-reference shape, and generated/vendor/spec
exclusions.

`tests/test_find_dormant_typescript.py` reaches the final `report.md` and
`findings.json`, not just an AST helper. It asserts exactly one
`review_required` candidate (`unusedPrivate`), one `uncertain` string-addressed
symbol (`dynamicByName`), no callback/registry/event/framework false positive,
and `certain_delete: 0`. It also covers:

- the preserved Python detector's positive (`unused`), direct-reference
  negative (`used`), and framework-decorator must-not-fire oracle;
- unresolved project status, syntax failure, missing tsconfig, and missing
  project-local compiler;
- broad/direct project-relative exclusions, internal/external symlink safety,
  report-path containment, and source SHA-256 immutability;
- copied selected-skill closure; and
- the verbatim stock `skills@1.5.19 add ... --skill find-dormant --copy`
  command plus installed TypeScript command, followed by native typecheck and
  native tests.

## D1–D8 closeout

| Gate | Evidence | Status |
|---|---|---|
| D1 scope honesty | `SKILL.md` declares `language: any`, `scans: [python, typescript]`, the top-level static invariant, and explicit dynamic/framework/deletion exclusions. | pass |
| D2 Python oracle | The focused suite creates a git-backed Python source fixture and proves stable structured output for positive, direct-reference negative, and decorator must-not-fire shapes. | pass |
| D3 TypeScript outcome | Locked host reaches final Markdown/JSON with one private positive; direct/exported/registry/event/framework shapes clean; string dynamic shape uncertain. | pass |
| D4 change/guard semantics | Not applicable: this advisory v1 proposes no source change or guard. | n/a |
| D5 installed closure | Copied selected-skill replay and exact stock selected-skill installation run only the installed Node command against a host-pinned compiler; no toolkit venv, repository script, or sibling skill runtime. | pass |
| D6 fresh forward task | A fresh non-context installed replay reported one review-required candidate, one dynamic uncertainty, zero certain-delete claims, passed native checks, and preserved source hashes. | pass |
| D7 regression/conformance | Focused suite, taxonomy, metadata lint, Node syntax check, Ruff, native host typecheck/tests, pre-commit, and diff check pass. Unsupported prerequisites fail explicitly; direct/broad exclusions and symlink/report containment are covered. | pass |
| D8 learning handoff | This MD/JSON pair records scope, tooling, outcome, commands, closure, accepted D6, and translation requirements. | pass |

## Verification at `46a16c7`

```text
.venv/bin/python -m pytest \
  tests/test_find_dormant_typescript.py tests/test_skill_taxonomy.py -q
# 9 passed

.venv/bin/python -m ruff check \
  tests/test_find_dormant_typescript.py
# All checks passed

node --check .claude/skills/find-dormant/scripts/detect_typescript_dormant.mjs
# passed

.venv/bin/python scripts/skill_meta.py lint
# OK — 76 skills, 76 declaring new contract

git diff --check
# clean
```

The focused fixture itself runs `npm ci --offline --ignore-scripts`,
`npm run typecheck`, and `npm test` before scanning; the copied and stock
replays run the same native typecheck/test checks after report generation.
The implementation commit's pre-commit hook also passed the project lint and
skill-artifact drift checks.

## Residual risk and next decision

This v1 can still under-report dynamic/runtime reachability and deliberately
does not investigate methods, nested functions, dynamic imports, string
dispatch beyond an exact string-name uncertainty, external callers, framework
registrations, or cross-project references. It must stay a review aid and never
a safe-deletion mechanism.

The fresh non-context installed-skill D6 replay passed with the expected
conservative human-review conclusion and unchanged sources. Do not extend
to UX/performance work, shared resolver infrastructure, or framework semantics
until that replay is accepted.
