# rename-concept TypeScript compiler-assessment learning handoff

Revision: implementation repairs `5c96af6`, `139c369`, and the final in-tree output-symlink guard.
Evidence date: 2026-07-19.

## Invariant

`/rename-concept` remains read-only. Its two glossary-driven lexical bands
prove retired-prose absence and find old/new text candidates; on a TypeScript
or TSX host, terminal completion additionally requires evidence from that
host's pinned TypeScript Compiler API. The report never represents a lexical
hit as an identifier reference.

## Authority, diagnostics, and completion boundary

- The runner loads only the host project's installed `typescript` package. The
  fixture pins TypeScript `5.9.3` in `package.json` and its lockfile; the
  documented preflight is `npm ci --offline --ignore-scripts`. A module
  resolved from an ancestor is rejected rather than silently becoming the
  host compiler.
- A matching glossary name or alias gets rename authority only from a matching
  **top-level exported** variable, function, class, interface, type alias, or
  enum. A same-named local/internal declaration is reported as
  `internal_or_unexported_identifier`, never as a concept symbol.
- Completion requires: no resolved old-concept symbol references, no
  unresolved identifier candidates, at least one resolved exported new-concept
  declaration, and no resolution diagnostics. This permits a finished rename
  to have no old declaration at all while requiring a clear authority for its
  replacement.
- Every invalid `tsconfig` or parse diagnostic blocks certification. Semantic
  errors block when they are at a candidate or undermine name/module/member resolution (`2304`,
  `2305`, `2307`, or `2552`). This is deliberately narrower than treating a
  whole-project type check as the rename gate.
- `--output reports/rename-concept/assessment.json` persists the lifecycle,
  lexical candidates, compiler evidence, diagnostics, verdict, and open items.
  The logical path must stay within `<project-root>/reports/rename-concept/`;
  source paths, external paths, and every existing final or ancestor symlink
  component fail before parent creation or writing. Rejecting in-tree symlinks
  matters too: otherwise `reports -> src` turns a nominal report path into a
  source overwrite. Host source stays unchanged.

## Two-stage TypeScript model

- `.ts` and `.tsx` participate in the same strict glossary-boundary lexical
  scan as the other supported text surfaces. `avoid_term_hit` is labelled
  `lexical_prose`; `superseded_co_occurrence` is labelled
  `lexical_candidate`.
- The compiler then classifies old/new exact-name identifier nodes as
  `old_concept_symbol`, `new_concept_symbol`, `shadowed_local`, `import_alias`,
  `property_key`, `internal_or_unexported_identifier`, or
  `unresolved_identifier`. Candidate hits with no identifier node are
  classified separately as `string_literal`, `comment_text`, or
  `non_identifier_text`.
- The Compiler API reads `tsconfig.json` when present and receives only the
  root-contained TS/TSX file list selected by the coupled scanner's default
  surface. It does not rewrite source, prove dynamic behavior, certify JSX
  runtime behavior, or make unrelated whole-project diagnostics a completion
  condition.

## Copied-install closure and tree safety

The prior assessment depended on PyYAML, a repository `_common` helper, and an
implicit source-checkout sibling path. A standalone `skills --copy` projection
must make the dependency explicit. The repaired skill installs the exact
coupled pair — `rename-concept` and `find-concept-divergence` — in one stock CLI
command, and loads the installed sibling scanner as the lexical authority. In
repository development it may load the source-tree sibling. It does not copy
or fork either detector band.

The walker evaluates exclusions on root-relative logical labels even for direct
targets, rejects files/symlinks that resolve outside the host, and never
traverses directory symlinks — including a directory symlink or a descendant
path beneath one named directly as the target. Retaining the logical label
before resolving the target means an alias placed under `reports/` or another
excluded directory cannot bypass that exclusion. This allows a real host below
an ancestor named `node_modules` while excluding its own `node_modules/`,
`dist/`, migration, and report trees. This safety behavior belongs in the
coupled scanner so both skills share it. Glossary `source:` documents remain
exempt from their own historical phrase examples.

## Locked evidence

`tests/fixtures/rename-concept-typescript/host/` contains dirty TS/TSX positive
cases, clean canonical TSX, an identifier homonym, source-document exemption,
ignored dependency/build trees, and compiler-classification fixtures for a
shadowed local, import alias, property key, string, and comment.

`tests/test_rename_concept_typescript.py` proves:

1. A copied skill runs with `python -I -S`, reports dirty TS/TSX candidate
   classifications, persists JSON, and never mutates source.
2. Assessment output accepts absolute and relative contained reports; rejects a
   source path, source symlink, external/traversal path, report root, and every
   final or ancestor symlink component; and proves `reports -> src` cannot
   overwrite an existing source file.
3. Direct ignored directory/file targets, a direct internal directory symlink
   or descendant beneath it, an excluded logical symlink alias, and an external
   symlink are excluded, while a direct ordinary contained directory still
   scans, even when the host has an ancestor named `node_modules`.
4. The exact documented stock `skills@1.5.19` one-command two-skill
   install/preflight/assessment journey produces exactly the two copied
   `.agents` skills, `COMPLETE` for a clean pinned TS host, and
   `reports/rename-concept/assessment.json`.
5. A missing host TypeScript package leaves structured compiler evidence
   `unavailable` and blocks completion without source writes.
6. A TypeScript package found only in an ancestor is rejected as non-host
   evidence.
7. A copied `rename-concept` without the coupled detector is inconclusive and
   never falls back to the source checkout.
8. Invalid TypeScript syntax emits persistent parse evidence and blocks
   certification.
9. Internal-only old/new declarations cannot supply authority or a completed
   rename.

Observed final verification:

```bash
.venv/bin/python -m pytest -q \
  tests/test_rename_concept_typescript.py \
  tests/test_b1_portability.py \
  tests/test_skill_meta_jobs.py \
  tests/test_perimeter_gaps.py \
  tests/test_run_skill_smokes.py
# 29 passed

.venv/bin/python .claude/skills/rename-concept/scripts/smoke.py
.venv/bin/python scripts/skill_meta.py lint --quiet
.venv/bin/ruff check .claude/skills/rename-concept/scripts/assess.py \
  .claude/skills/find-concept-divergence/scripts/scan.py \
  .claude/skills/rename-concept/scripts/smoke.py \
  tests/test_rename_concept_typescript.py
node --check .claude/skills/rename-concept/scripts/typescript_identifier_evidence.mjs
.venv/bin/python scripts/skill_comply/validate.py
git diff --check
```

## Reuse decision and residual risk

Keep the Compiler API runner family-local: no second accepted consumer has this
exact glossary/lifecycle contract. Reuse the existing coupled divergence
scanner rather than copying it. The reusable principles are explicit coupled
dependency closure, contained report writes, root-relative logical exclusions,
no directory-symlink traversal, symlink containment, evidence labels, and a
terminal diagnostic gate.

Future language support needs a host-pinned native resolver, a declared
authority surface, persistent evidence, and the same missing-tool, invalid
syntax, shadowing/alias/property/string/comment, direct-exclusion, and symlink
fixtures. Codemods and `--apply` remain out of scope.
