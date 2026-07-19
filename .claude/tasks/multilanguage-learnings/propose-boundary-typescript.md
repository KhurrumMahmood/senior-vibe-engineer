# TypeScript `propose-boundary` learning packet

Implementation revision: `5e8ebb41d3c3bea056f201faaba77852cd9bffae`
on `codex/ts-propose-boundary`.

## Accepted TypeScript v1 contract

Keep the existing Python AST helper unchanged. Add one self-contained
TypeScript/TSX runner that accepts a target, one named project-local
`tsconfig.json`, and the host's installed `typescript` package. It writes both
`reports/propose-boundary/<name>/inspection.json` and `proposal.md` from
compiler-resolved static module edges, top-level symbols, and target-local
call edges.

The final proposal contains an evidence-cited public API table, a temporary
barrel/compatibility plan, direct/alias/barrel caller-impact table, private
reach blockers, and characterization/native verification plan. It is
read-only. A target with an unresolved static import or an ambiguous barrel
export defers with `recommendation: defer_unresolved_graph`; a cohesive
one-domain target defers with `defer_no_seam`.

## Tool and closure decision

`scripts/propose_typescript.mjs` is a family-local Compiler API consumer. It
loads `typescript` through the host `package.json`, parses only the named
tsconfig, gives its compiler options and project references to a `Program`,
uses `resolveModuleName` for direct and `paths` alias specifiers, and uses the
checker for declarations and resolved call signatures. The TypeScript package
is pinned to 5.9.3 in the fixture lockfile; the installed skill never uses a
toolkit venv, repository `scripts/`, `_common`, or a sibling skill.

Lexical import/call collection was rejected because it cannot honestly resolve
aliases or establish a call target. `ts-morph` and tree-sitter were rejected
because they add a dependency without improving this contract. The module
resolver remains local even though `map-subsystem` has a related accepted
pattern: map and boundary proposals have different symbols, call facts,
deferral conditions, artifacts, and caller-impact requirements. No shared
platform is justified.

## Fixture and result evidence

`tests/fixtures/propose-boundary-typescript/host` locks all required shapes:

- A positive two-domain legacy module: quote and settlement symbols, with
  `settlementCapture` reaching private `_quoteNormalize` across the proposed
  cut.
- Resolved direct, `@orders/*` alias, and `index.ts` barrel callers; the final
  proposal names the barrel and marks the direct private import as a Phase 1
  blocker.
- Cohesive shipping code that explicitly defers instead of inventing a seam.
- Unresolved alias and ambiguous `export *` fixtures, both explicit
  `defer_unresolved_graph` artifacts.
- Generated, vendor, test, declaration-compatible exclusion policy plus a
  direct external-symlink rejection.

`tests/test_propose_boundary_typescript.py` asserts final proposal and JSON,
not only helper facts. It also runs the legacy Python helper against positive,
cohesive, and excluded paths, proving its behavior remains unchanged.

## D1–D8 evidence

- **D1:** `SKILL.md` declares `language: any`, `scans: [python, typescript]`,
  the narrow framework-neutral TS v1 contract, explicit framework/runtime
  exclusions, and clear compiler prerequisite failures.
- **D2:** The targeted suite runs the Python helper's positive quote/settlement
  case, cohesive no-seam case, and direct excluded `node_modules` case without
  changing `propose.py`.
- **D3:** The locked TypeScript host reaches final `inspection.json` and
  `proposal.md`; the positive proposal cites resolved symbol, import, call,
  direct/alias/barrel, and native verification evidence.
- **D4:** This is a read-only proposal family, so no mutation or guard applies.
  The proposed native matrix is `npm run typecheck` and `npm test`; both pass
  in the locked positive host.
- **D5:** The suite installs exactly `propose-boundary` with the verbatim stock
  command into `.agents/skills/` outside the checkout, runs the verbatim
  installed proposal command, and asserts no checkout/repository import in the
  bundled TypeScript runner.
- **D6:** **Pending independent replay.** The automated installed-host replay
  is green, but a fresh non-context agent has not yet received only the raw
  fixture and natural task. Serial integration owns that independent replay.
- **D7:** `7 passed` in the focused suite; fixture `npm ci --offline
  --ignore-scripts`, `npm run typecheck`, and `npm test` pass; `node --check`,
  Ruff, metadata lint, pre-commit, and `git diff --check` pass.
- **D8:** This packet and companion JSON record the evidence and D6 limitation
  for integration review before any reuse decision.

## Exact verification

```text
.venv/bin/python -m pytest tests/test_propose_boundary_typescript.py -q
# 7 passed

npm ci --offline --ignore-scripts --prefix tests/fixtures/propose-boundary-typescript/host
npm run typecheck --prefix tests/fixtures/propose-boundary-typescript/host
npm test --prefix tests/fixtures/propose-boundary-typescript/host
# passed

node --check .claude/skills/propose-boundary/scripts/propose_typescript.mjs
.venv/bin/python -m ruff check .claude/skills/propose-boundary/scripts/propose.py tests/test_propose_boundary_typescript.py
.venv/bin/python scripts/skill_meta.py lint
git diff --check
# passed (the Python script has a pre-existing noqa-format warning from Ruff)
```

The focused suite's stock-install test calls the exact documented command
blocks, copies the selected skill under a temporary host's `.agents/skills/`,
and executes the installed command from that host root. It produces
`reports/propose-boundary/typescript-legacy/inspection.json` and `proposal.md`
with recommendation `refactor`; no host source is edited.

## Boundaries, risks, and next decision

Static resolution does not establish dynamic import, runtime loader,
reflection, decorator, framework registry, external consumer, or safe-move
facts. Ambiguous compiler export diagnostics are a defer signal, not a
framework interpretation. Direct symlink targets fail and broad traversal does
not follow symlinks. The only accepted TSX claim is syntax/module resolution;
no React semantics are inferred.

Keep this resolver family-local. A second accepted proposal consumer must
prove the same project-local resolution, direct-target exclusion, deferral,
artifact, and copied-install contract before any shared utility is considered.
Do not claim TypeScript support is fully promoted until the pending independent
D6 installed-host replay passes.
