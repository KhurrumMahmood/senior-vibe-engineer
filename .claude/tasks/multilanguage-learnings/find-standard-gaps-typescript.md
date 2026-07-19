# TypeScript `find-standard-gaps` learning packet

Feature revision: `77e99d65499dea75dd5a57ecf88faf11942d682b`; completeness
repair: `df60ffbc2677f3d056032c34388858a811ce1886`, both on
`codex/ts-find-standard-gaps`, based on
`dac52aa29fb1c795809490209d1d2db378b34e57`.

## Accepted TypeScript v1 contract

Keep the Python scanner intact and add one concrete, framework-neutral
TypeScript/TSX standard: direct syntactic `JSON.parse(...)` calls must be
lexically inside `try`. The locked host fixture includes both `.ts` and `.tsx`,
with one protected TypeScript call and three exact gaps (ordinary TS, a nested
callback inside an outer `try`, and TSX).

The launcher uses the host's pinned TypeScript Compiler API only to create a
syntax tree and collect direct identifier/property-access call spellings,
source lines, and lexical `try` state. It does not read a tsconfig, build a
Program, resolve imports/aliases/types/receivers, prove a global API, or infer
React, Node, or any other framework. Nested function/callback bodies reset
outer `try` protection because callback invocation timing is not known.

`requires_kwarg` and `enclosed_by: with` remain Python-only. A TS/TSX standard
using either reports `language_unsupported`; it is never represented as a
clean zero-gap scan. Missing Node or host-local `typescript` also reports that
status. A TS parse/read failure returns `status: partial` and records
`skipped_files`, so a zero-gap result with skips is never clean.

## Selection and installation boundary

The fixture's durable user artifact is `standards.json`, not generated parser
state. It declares the concrete `JSON.parse` / `enclosed_by: try` detector and
root-relative `src/**/*.ts` / `src/**/*.tsx` paths.

The selected skill bundles `detect_typescript_calls.mjs` and the narrow
state-home resolver needed by `project_state.py`. This removes the prior hidden
`_common/engineering_home.py` dependency, so a stock `.agents/skills`
projection contains the entire runtime. The resolver/run command blocks in
`SKILL.md` choose `.agents` or `.claude`, use host Python, and write only the
declared reports.

## Source policy and oracle

All paths are evaluated relative to `--project-root`. Direct files and
directories are supported, but TS/TSX scans exclude declaration, generated,
minified/bundle, test/spec, fixture, build, dependency, report, and vendor
trees even when selected directly. A symlink that resolves outside the project
root is excluded. This prevents a caller from bypassing source policy by
narrowing the target to `vendor/` or an external linked file.

`tests/test_find_standard_gaps_typescript.py` proves final `coverage.md` and
`coverage.json`, not only launcher facts. Its boundary corpus covers:

- exact `.ts` + `.tsx` sites/gaps and string/comment non-matches;
- Python + TS/TSX mixed scanning and legacy Python `requires_kwarg` behavior;
- unsupported TS condition, missing host TypeScript, and malformed TS partial
  scan behavior;
- generated/vendor/test/declaration exclusions, direct excluded file/directory
  targets, and external symlink escapes;
- copied `python -I -S` closure and stock `skills@1.5.19` installation with
  extracted documented command blocks.

## Fresh installed-host journey

A fresh locked host at
`/private/tmp/find-standard-gaps-forward-partial.gDKW8r/host` ran only this
sequence: `npm ci --offline --ignore-scripts`, native `typecheck`/`test`, stock
`skills@1.5.19 add --skill find-standard-gaps --agent codex --copy`, and the
installed `SKILL.md` resolver/run blocks with `STANDARDS=standards.json`.

The installed skill wrote
`reports/standard-gaps/scan-20260719-042018/coverage.{md,json}`. It reported
one fully scanned standard, zero partial standards, four situation sites, three
gaps, two analyzed files, and the expected assumed-MAX state warning. Artifact
SHA-256 values:

- `coverage.md`: `10a9390ea0a440ee9e962ad8ca2a09b3d327b57bf024acc7b6b372dadfa7aeff`
- `coverage.json`: `6bc1740abf1b66e121fce576f2f0ca8d0a594170f629082270c81474a9535bf8`

## What generalized, what did not

Generalized: host-local pinned Compiler API resolution, final-artifact oracle,
root-relative exclusion policy, explicit unsupported/partial states, and stock
installed command replay.

Did not generalize: Python `requires_kwarg`/`with` semantics, TypeScript call
identity, option-object interpretation, framework behavior, a TypeChecker or
module resolver, and a shared parser/fact platform. One syntax consumer is not
evidence for a reusable cross-skill runtime.

## Verification

```text
.venv/bin/python -m pytest -q tests/test_find_standard_gaps_typescript.py tests/test_standard_gaps_census.py
# 27 passed

.venv/bin/ruff check scan_coverage.py project_state.py engineering_home.py tests/test_find_standard_gaps_typescript.py
# All checks passed

node --check detect_typescript_calls.mjs
.venv/bin/python -m py_compile scan_coverage.py project_state.py engineering_home.py
.venv/bin/python scripts/skill_meta.py lint
# OK — 76 skills, 76 declaring new contract
```

## Next decision

Keep the family-local launcher and narrow `try` contract. Add another
TypeScript condition only when a concrete standard and its positive/negative
fixture establish its syntax semantics. Any future alias/type/API claim needs a
separate Program/TypeChecker contract and its own installed-host proof.
