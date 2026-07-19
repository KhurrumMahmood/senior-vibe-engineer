# B1 portability learning report

Revision: `28671a38afb476d970c6242e0782f7d07cbb8de8` baseline +
`<B1 YAML fallback repair commit>` on `codex/ts-b1-portability`, 2026-07-19
UTC

## Outcome

`find-concept-divergence` now treats `.ts` and `.tsx` as the same strict,
lexical TypeScript scan surface. The final `findings.jsonl` and `report.md`
contain both must-fire fixtures and omit canonical-only TSX, an identifier
homonym, a justified compatibility alias, and generated/vendor paths.

`find-rule-surface-drift`, `find-skill-artifact-drift`,
`find-skill-intent-drift`, and `find-stale-artifacts` now declare
`language: any, framework: any` because their host invariant is artifact,
frontmatter, or documentation hygiene—not host application source analysis.
Their existing `scans:` values remain factual descriptions of files the
detector reads; no cosmetic TypeScript scan was added.

## Scope and exclusions

- The TypeScript outcome is strict source-text matching only. It includes
  `.ts` and `.tsx`, but does not parse JSX, resolve symbols/imports, inspect
  types, or invoke the TypeScript compiler.
- The four neutral skills do not acquire TypeScript-specific variants. Their
  Python executables remain an installation detail, while their host claims
  are language-neutral.
- Router catalog generation and matching are deliberately not changed in B1.
  The serial integrator owns that generated-data and matcher work.

## Reference repairs and tool decision

- `find-concept-divergence` omitted `.tsx` from its source suffix set and
  imported repository `_common/diff_resolution.py`; it now has a local target
  resolver and a schema-specific, stdlib glossary reader. Its scalar flow-list
  reader preserves quoted comma-containing values (including aliases) rather
  than splitting them into false terms; nested flow collections remain outside
  the declared glossary profile and fail clearly.
- The rule-surface, artifact, and stale-artifact reporters imported repository
  `_common/product_topology.py`. Their small JSONL/report closure now lives in
  each selected reporter, rather than in a new shared platform.
- `find-skill-artifact-drift` also used the repository YAML-frontmatter module
  and source-root constants. It now reads only the evidence fields it owns and
  resolves host paths from `--project-root` / cwd.
- `find-skill-intent-drift` keeps PyYAML behavior for rich YAML, but a copied
  isolated install can read JSON-form YAML and emit JSON-form `_index.yaml`
  with stdlib only. A rich, non-JSON YAML contract without host PyYAML is a
  clear declared boundary, not a source-checkout import.
- The lexical scanner is the least semantic tool for the accepted B1 report;
  TypeScript Compiler API, tree-sitter, ts-morph, and a shared TypeScript
  platform would not improve this outcome.

## Fixtures and evidence

- Locked fixture: `tests/fixtures/b1-portability/concept-host/`.
  `src/deprecated.ts` and `src/deprecated.tsx` must fire on
  `deprecated status`; `canonical.tsx`, `homonym.ts`, and
  `compatibility-alias.ts` stay clean. `node_modules/vendor/` and `dist/`
  are skipped.
- Final TypeScript outcome and copied closure:

  ```bash
  .venv/bin/python \
    -m pytest -q tests/test_b1_portability.py
  # 4 passed
  ```

  The copied-skill test uses `python -I -S` from an external host directory
  and drives each final report / output path. It proves copied
  `find-concept-divergence`, `find-rule-surface-drift`,
  `find-skill-artifact-drift`, `find-skill-intent-drift`, and
  `find-stale-artifacts` do not import repository `_common`, root `scripts/`,
  or a toolkit venv on the exercised paths. A fresh copied
  `find-concept-divergence` run found exactly the two actionable
  `avoid_term_hit`s in `src/deprecated.ts` and `src/deprecated.tsx`; its final
  JSONL/report kept the compatibility alias, identifier homonym, generated
  `dist/`, and vendored `node_modules/` paths clean. The quoted-comma alias
  regression also reaches the final copied report: a backtick TypeScript
  transition using `legacy, status` and `canonical, status` renders the one
  expected `superseded_co_occurrence` finding rather than a false clean.
- Existing oracles remain green:

  ```bash
  .venv/bin/python \
    .claude/skills/find-skill-artifact-drift/scripts/smoke.py
  # OK - 6 bad fixture findings across 6 bands, good clean, gate honored

  .venv/bin/python \
    .claude/skills/find-skill-intent-drift/scripts/test_scan.py
  # 8 tests, OK
  ```

- Rule-surface replay produced three expected existing bands
  (`dormant_doc`, `missing_doc`, `unreferenced_doc`) and rendered final
  `report.md` / `findings.json`. Stale-artifacts rendered a verified zero
  finding final report. The concept scanner also read the repository's
  ordinary YAML glossary under `python -I -S` and emitted its final artifacts.
- Project checks passed: `scripts/skill_meta.py lint` (76 skills), targeted
  pytest (15 passed), `scripts/skill_comply/validate.py` (PASS), targeted
  Ruff (all checks passed), and the B1 artifact-drift gate (clean).
- The generic skill-creator `quick_validate.py` rejected valid extended
  frontmatter fields (`argument-hint`, `best_for`, `framework`, `job`,
  `language`, `not_for`, `scans`, `tier`, `user-invocable`). This is an
  expected validator-model mismatch; `scripts/skill_meta.py` plus project
  conformance tests are the authoritative checks for this repository.

## False-positive boundary

The TypeScript scan stays lexical. It deliberately keeps a canonical-only TSX
component, `deprecatedStatus` as an identifier homonym, and a glossary-listed
compatibility alias clean; it excludes `node_modules/` and `dist/`. It can
still flag an intentional deprecated phrase in a first-party source/comment
file because source-comment semantics are outside the accepted strict report.

## What generalized and what did not

Generalized: `language` / `framework` express host assumptions, strict suffix
coverage, structured JSONL + Markdown reports, exclusion paths, and
copied-install validation.

Did not generalize: JSX semantics, TypeScript symbols/types/imports, generic
YAML parsing, Python AST inspection of skill scripts, git freshness facts,
and each skill's independent report domain. No shared parser, report library,
or TypeScript adapter was extracted; there is no accepted second consumer with
the same contract.

## Next-language prerequisites

- Rust: a `.rs` lexical fixture plus generated `target/` boundary; rust-analyzer
  or compiler facts before naming symbol-level guarantees.
- Go: a `.go` lexical fixture plus vendor/generated boundary; `go/packages`
  before package/symbol claims.
- Java/Kotlin: `.java` / `.kt` fixtures and generated-source boundary; compiler
  or language-server facts before overload/visibility claims.
- C#: `.cs` fixtures and generated-code boundary; Roslyn before partial-type
  or symbol guarantees.
- Ruby: `.rb` fixtures and vendored-gem boundary; a parser/language server
  before metaprogrammed-name claims.

## Serial-integrator proposals and residual risk

1. Regenerate router catalog data so the five revised frontmatters preserve
   `language`, `framework`, and `scans`; then implement the B1 matcher
   language-source contract.
2. Remove `find-omnibus`'s unearned TypeScript `scans` claim before copied
   router testing; restore only after B4 evidence.
3. Correct `find-workflow-state-gaps` to its Django framework binding before
   TypeScript routing is enabled.
4. Review and refresh the five intent/provenance contracts after accepting
   these frontmatter changes; B1 did not own contract files.

Residual risks: rich YAML intent contracts require host PyYAML outside the
JSON-as-YAML stdlib path; the broader router work is intentionally untested
here; and D6 fresh forward testing plus D8 independent review are pending
because the parent task explicitly prohibited spawning agents while all
concurrency slots are occupied. The recommended next decision is to accept
this evidence packet, perform the serial router / contract work, and then run
a fresh installed-skill forward test before advancing another language batch.
