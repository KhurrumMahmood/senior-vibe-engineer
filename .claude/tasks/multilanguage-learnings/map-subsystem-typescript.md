# TypeScript `map-subsystem` learning packet

Implementation revisions: `be84d41487f57438bca2d4a32251d5fa1eb4396d`
(Compiler API map) and `d3d2af1ce03534f60cb81d59717fb3477172c348`
(artifact-path containment) on `codex/ts-map-subsystem`, based on
`6a93a7c2731da4defb6dbf0a33458bcc8f907317`.

## Accepted TypeScript v1 contract

Keep the Python mapping stages and renderer unchanged. Add a self-contained
TypeScript/TSX v1 final-map command that accepts one named project-local
`tsconfig`, resolves the host's pinned `typescript` Compiler API, and produces
both durable Markdown and matching JSON evidence.

The map establishes eligible `.ts`/`.tsx` inventory; exported surface with
re-exports marked; resolved static direct/alias inbound and outbound imports;
`index.ts`/`index.tsx` barrel boundaries; workflow-map references; and target
TypeScript diagnostic counts. Responsibility clustering, judgment-oriented
open questions, and ESLint policy are explicit unavailable fields. An
unresolved or symlink-blocked selected import makes the map `partial`, not
complete. Syntax errors, absent/invalid tsconfig, and absent project-local
TypeScript fail with exit code 2.

## Tool and closure decision

`map_typescript.mjs` is one family-local resolver. It reads the named tsconfig
with `parseJsonConfigFileContent`, creates a Compiler API Program, uses
`resolveModuleName` for direct and `paths` alias specifiers, and uses the
checker only to enumerate module exports. The fixture locks TypeScript `5.9.3`;
installed execution resolves that package from the host `package.json`, never a
toolkit package or venv.

Rejected alternatives: lexical imports cannot resolve aliases or expose an
incomplete graph; ts-morph/tree-sitter add dependencies without improving the
accepted outcome; a shared parser platform has no demonstrated second consumer;
and an inferred ESLint policy would be less honest than an unavailable field.

The resolver passes project references to `createProgram`, but v1 proves the
named config's direct and alias resolution only. It does not claim complete
cross-project package/reference analysis.

## Fixture and source-policy evidence

`tests/fixtures/map-subsystem-typescript/host` is a locked multi-file host:
three selected TS/TSX feature files, direct and `@app/*` alias imports, an
`index.ts` barrel, external direct and alias importers, a workflow document,
and generated/vendor/test exclusions. Its package lock supplies the native
`npm run typecheck` proof.

`tests/test_map_subsystem_typescript.py` asserts final artifacts with 3 source
files, 5 exports, 2 inbound imports, 2 outbound imports, one barrel boundary,
and one workflow entry. It also proves a visible partial unresolved import;
syntax/missing-tsconfig/missing-TypeScript failure; broad and direct
project-relative exclusions; no internal/external directory-symlink traversal;
report/evidence paths cannot overwrite source or traverse a symlink; and stock
`.agents` installation uses only documented command blocks.

## Fresh installed-host forward outcome

A fresh no-context agent created a clean host at
`/private/tmp/map-subsystem-typescript-stock.tNLR4Q`, copied only the locked
host fixture, ran `npm ci --offline --ignore-scripts` and `npm run typecheck`,
then used the documented stock install to copy only `map-subsystem` into
`.agents/skills/`. The documented installed command wrote:

- `.claude/docs/subsystems/typescript-features.md`
- `reports/map/typescript-features/typescript-map.json`
- `reports/_meta/effectiveness.jsonl`

The final map was complete: 3 source files, 5 exports, 2 resolved outbound
edges, 2 resolved inbound edges, 0 unresolved imports, and one workflow entry.
No source was edited. Artifact SHA-256 values:

- Markdown: `bfc0574c6b551f71477e44763729ea222e28405abcaca9adb143d70b78a0b247`
- JSON: `aa2590931effd92cc5e839c9e3839c3abdf6d766bbb2e7a555225fdecd31c3fa`

The agent reported no source mutation and no blocker. The host passed its
native typecheck both before and after mapping, satisfying the fresh D6
installed-user replay.

## Verification

```text
.venv/bin/python -m pytest \
  tests/test_map_subsystem_typescript.py tests/test_skill_taxonomy.py -q
# 10 passed

npm ci --offline --ignore-scripts && npm run typecheck
# passed in the locked fixture and clean installed host

node --check .claude/skills/map-subsystem/scripts/map_typescript.mjs
# passed

.venv/bin/python \
  -m ruff check tests/test_map_subsystem_typescript.py
# All checks passed

.venv/bin/python scripts/skill_meta.py lint
# OK — 76 skills, 76 declaring new contract

git diff --check
# clean
```

`check-ecosystem-consistency` completed but its baseline predates many
unrelated product-branch skills, yielding 84 advisory catalog/shape findings.
This lane deliberately does not edit the shared catalog, router, tracker,
contracts, or baseline state; serial integration owns that review.

## What generalized and what did not

Generalized: host-pinned Compiler API loading, final-artifact assertions,
project-root-relative direct-target exclusions, explicit partial/unavailable
states, and stock selected-skill closure testing.

Did not generalize: Python AST clustering; dynamic/runtime imports;
call/reference graphs; API/framework semantics; cross-project package/reference
analysis; lint policy; or a shared TypeScript platform. No accepted second
consumer has the same resolution/output/closure contract.

## Next decision

Keep the resolver local and retain this narrow module-fact contract. A later
boundary or folder proposal may reuse it only after proving its own
direct+alias, barrel, project-reference, final-proposal, and installed-closure
fixture. Do not turn one successful consumer into a parser service.
