# JavaScript syntax cohort learning packet

Status: candidate evidence complete; serial capability promotion pending.

## Results

| Skill | Candidate disposition | Evidence mode | Mechanism | Demonstrated outcome |
|---|---|---|---|---|
| `audit-decisions` | `javascript-supported` | `syntax` | Existing family-local Compiler API comment parser now selects JS/JSX script kinds | Final drift artifacts retain real comments and exclude comment-shaped strings across `.js`, `.jsx`, `.mjs`, `.cjs` |
| `find-complexity-hotspots` | `javascript-supported` | `syntax` | Existing syntax walker now inventories the four JS suffixes and labels provenance as JavaScript | Final report contains exact function spans and branch scores; tests/generated/minified files remain excluded |
| `find-omnibus` | `javascript-supported` | `syntax` | Replaced the legacy column-zero JavaScript heuristic with the existing family-local top-level symbol parser | Four-suffix candidates reach detector output with exact spans and Compiler API provenance |
| `find-standard-gaps` | `javascript-supported` | `syntax` | Existing direct-call/lexical-try parser now accepts the four JS suffixes | Final coverage artifact distinguishes protected and unprotected direct calls without claiming alias or receiver resolution |

## Transfer learning

- TypeScript's family-local `createSourceFile` launchers transferred cleanly
  when the only required facts were comments, function spans, top-level
  declarations, or direct calls. The reusable seam was explicit `ScriptKind`
  selection, not a generic language adapter.
- `.mjs` and `.cjs` use the JavaScript script kind; `.jsx` requires the JSX
  script kind. `node --check` cannot validate JSX and was not used as evidence
  for the parser-backed outcomes.
- One parser can serve both JS and TS inside a skill, but the emitted language
  must come from the selected suffix. Parser acceptance alone is not the
  support claim; each test reaches the skill's established final artifact.
- Mixed-host scans should keep useful Python results when JavaScript tooling is
  missing. A JS-only scan without a project-local parser remains explicitly
  unavailable; a mixed scan is partial rather than falsely clean.
- Fixed source-policy exclusions need the full suffix family. Adding parser
  support without extending test/spec/generated/minified globs silently
  widens the scan into non-production files.
- No shared JavaScript parser platform was needed. A future language should
  first try the same family-local parameterization and extract common tooling
  only after a repeated maintenance repair proves the shared boundary.

## Boundaries

- These are syntax outcomes. They do not establish module resolution, symbol
  identity, type/receiver identity, framework behavior, or runtime cost.
- `find-standard-gaps` still supports only direct dotted calls protected by a
  lexical `try` for JavaScript/TypeScript. Aliases, dynamic calls, and
  `requires_kwarg` remain outside that branch.
- `find-omnibus` reports responsibility leads from top-level declaration
  names; scout judgment is still required before a decomposition claim.

## Verification

- JavaScript final outcomes and failure boundaries:
  `../engineering-skills/.venv/bin/python -m pytest -q tests/test_javascript_syntax_cohort.py`
- Additive TypeScript regression suites:
  `../engineering-skills/.venv/bin/python -m pytest -q tests/test_audit_decisions_typescript.py tests/test_find_complexity_hotspots_typescript.py tests/test_omnibus_typescript.py tests/test_find_standard_gaps_typescript.py`
- Static checks:
  `../engineering-skills/.venv/bin/python -m ruff check <owned Python paths>` and pre-commit on the owned file list.
