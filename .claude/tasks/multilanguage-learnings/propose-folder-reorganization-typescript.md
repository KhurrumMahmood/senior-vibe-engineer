# TypeScript `propose-folder-reorganization` learning handoff

Implementation revision: pending the single logical commit on
`codex/ts-propose-folder-reorganization` (based on product revision
`6dfd0604c399ebe9029ed793ef9496272214bcb9`).

## Accepted TypeScript v1 contract

This is one read-only proposal for one direct TypeScript/TSX filename cluster,
not a generic refactor engine. The host supplies a named `tsconfig`, its own
installed `typescript` Compiler API, a direct parent, a prefix, and an
explicit human `split` or `cohesive` judgment. The final artifacts are
`reports/propose-folder-reorganization/<name>/proposal.md` and
`inspection.json`.

For a ready three-file cluster, JSON and Markdown agree on every source move,
every resolved static impact edge, a destination tree, characterization/native
test plan, and one explicit compatibility decision:
`preserve_existing_barrels_migrate_subpaths`. Existing `index.ts[x]` barrels
remain compatible through rewritten re-exports; a new domain barrel is
created; every resolved direct relative or `paths`-alias subpath importer is
rewritten; legacy file shims are deliberately not retained.

The proposal records cluster-internal imports as well as outside consumers.
That is required because a relative import between two files changes base path
when both files move. The generator computes those specifiers from the
**post-move importer** location; computing them from the original importer
produced the invalid `./billing/types` path and was repaired before
acceptance.

## Scope boundaries

- The Python `inspect.py` path remains unchanged and is pinned by a positive
  cluster/import result plus a below-threshold defer oracle.
- TS v1 supports static `import`, `export … from`, and `import = require`
  facts resolved by the named host tsconfig only.
- Dynamic/runtime loading, CommonJS `require()` calls, external package
  subpath compatibility, framework ownership, test-framework conventions,
  automatic cohesion judgment, and refactor execution remain outside scope.
- Three lexical siblings are not a refactor verdict. `--cluster-judgment
  cohesive` produces `defer_cohesive_cluster`; `split` is an explicit human
  confirmation.
- Project-root-relative exclusions include direct test/generated/vendor
  targets. Directory symlinks, logical project escapes, symlinked tsconfigs,
  and symlinked report ancestors fail safely rather than being traversed.
- An unresolved or unsafe static import inside a selected member produces a
  final `blocked` `defer_unresolved_imports` proposal. It never silently
  claims a complete impact table.

## Tool and closure decision

`scripts/propose_typescript.mjs` is a self-contained, family-local Node
Compiler API consumer. It resolves TypeScript from the host `package.json`,
parses the named tsconfig, uses `resolveModuleName` for direct and `paths`
aliases, and uses the checker only for exported public symbols. The locked
host pins TypeScript `5.9.3`; no toolkit Node dependency, Python virtualenv,
repository `scripts/`, `_common`, sibling skill, or network API is used at
runtime.

The accepted `map-subsystem` resolver is the evidence source for this level of
precision, but this skill does not import it. Its inventory/map output,
partial-status semantics, and artifact locations are different enough that a
shared platform would expand scope without reducing the installed closure.
Lexical imports were rejected because they cannot prove alias destinations;
ts-morph and tree-sitter add dependencies without improving the accepted
proposal; inferred framework compatibility would make a broader claim than
the fixture proves.

## Locked fixture and results

`tests/fixtures/propose-folder-reorganization-typescript/host` includes:

- a `src` three-sibling `billing-*` cluster;
- direct relative and `@app/*` alias importers, cluster-internal imports, and
  a root `index.ts` barrel re-export;
- below-threshold, explicitly cohesive, scratch, generated, vendor, and test
  clusters;
- a named paths-aware tsconfig and lockfile-backed native `npm run typecheck`.

`tests/test_propose_folder_reorganization_typescript.py` proves the final
ready proposal has three moves and seven resolved import-impact rows, including
relative, alias, internal, and barrel rows. It then applies the generated move
table in a disposable host, creates the declared new barrel, rewrites every
recorded specifier, and passes `npm run typecheck`.

The same suite proves threshold/cohesive/scratch and direct
generated/vendor/test deferrals; a selected unresolved alias blocks with a
visible final proposal; logical and physical symlink containment rejects both
target and artifact escapes; Python reference output remains stable; and the
exact documented `skills@1.5.19` stock command copies only this skill to an
outside-checkout `.agents/skills/` location. The automated clean-host replay
runs the installed documented command and writes a ready proposal without any
checkout runtime path in the installed TypeScript script.

## D1–D8 status

| Gate | Status | Evidence |
|---|---|---|
| D1 — scope honesty | pass | Skill declares one static-module resolved proposal, human cohesion gate, exclusions, deferred framework/runtime modes, and no move execution. |
| D2 — Python oracle | pass | Dedicated test preserves a positive Python inspection/import record and `cluster_below_threshold` output; Python production code is untouched. |
| D3 — TypeScript outcome | pass | Locked fixture reaches final `proposal.md` and `inspection.json`, asserting all three moves, seven resolved rows, and compatibility decision. |
| D4 — change/guard semantics | not applicable to this read-only proposal | A disposable host applies the planned move/rewrite/barrel result and `npm run typecheck` passes, which is the required native feasibility proof. |
| D5 — installed closure | pass | Exact selected-skill `skills@1.5.19` copy install runs the installed documented command outside the checkout; no repository runtime import occurs. |
| D6 — fresh natural forward task | blocked for independent replay | The automated clean-host test exercises the documented natural command, but a fresh independent agent was stopped before `npm ci --offline --ignore-scripts` and `npx … skills add` by the repository `command.package_install` policy; no user-approved scoped grant was available. |
| D7 — regression and conformance | pass | Dedicated outcome suite, native TypeScript syntax check, Python reference replay, metadata/frontmatter tests, Ruff, metadata lint, and diff checks are recorded below. |
| D8 — learning handoff | ready | This Markdown and matching JSON record tool, fixture, closure, false-positive, translation, UX, and residual-risk evidence. |

## Verification commands

```text
.venv/bin/python -m pytest tests/test_propose_folder_reorganization_typescript.py -q
# 7 passed

node --check .claude/skills/propose-folder-reorganization/scripts/propose_typescript.mjs
# passed

.venv/bin/python -m ruff check tests/test_propose_folder_reorganization_typescript.py
# All checks passed

.venv/bin/python -m pytest tests/test_yaml_frontmatter.py tests/test_skill_meta_jobs.py tests/test_skill_taxonomy.py -q
# 15 passed

.venv/bin/python scripts/skill_meta.py lint
# OK — 76 skills, 76 declaring new contract

git diff --check
# clean

npm ci --offline --ignore-scripts && npm run typecheck
# passed in the locked fixture before the proposal and after applying its move plan
```

No unsupported full-suite claim is made here. The independent D6 replay remains
blocked on an explicit package-install grant; automated D5 closure evidence is
not relabeled as independent-agent D6 proof.

## False-positive boundary

Legitimate cohesive clusters need an explicit `cohesive` judgment and stay
deferred. Scratch paths, fewer than three files, and any direct excluded
target stay deferred. Existing `index.ts[x]` files do not become candidate
cluster members, but they remain graph importers so public-barrel breaks are
not missed. Dynamic imports, CommonJS `require()` calls, unresolved external
package aliases, tests, generated code, vendored code, declarations, and
symlinked paths are intentionally not presented as complete move facts.

## What generalized, what did not, and reuse

The demonstrated reusable knowledge is narrow: host-pinned Compiler API
loading, named-tsconfig direct/alias resolution, post-move relative-specifier
calculation, project-root-relative direct-target exclusions, safe artifact
paths, final-artifact assertions, and copied stock-install replay.

Python AST/public symbol extraction, Python package semantics, framework
conventions, dynamic reachability, external package compatibility, a shared
Compiler API service, and a generic move executor did not generalize. Although
`map-subsystem` is an accepted second module-resolution consumer, keep both
implementations family-local until identical resolver inputs, failure modes,
artifact policy, and installed closure are independently demonstrated.

## Translation prerequisites

| Language | Native capability and fixture required before support | Remaining gap |
|---|---|---|
| Rust | rust-analyzer/compiler-backed module resolver; direct `use`, crate-alias, `mod.rs`, re-export, generated/test, `cargo check` fixture | macros, cfg, workspace crates |
| Go | `go/packages` plus `go/types`; package/module import, `_test.go`, generated/vendor, `go test` fixture | build tags, replace/workspace rules |
| Java/Kotlin | compiler/language-server model; package imports, Gradle/Maven source sets, generated/test, native build fixture | annotation processing, multi-module resolution |
| C# | Roslyn workspace; project/namespace imports, partial/source-generated/test fixture, `dotnet build` | conditional compilation and NuGet graph |
| Ruby | Prism/Ripper plus explicit loader convention; `require`, autoload-style, spec/vendor fixture | dynamic require and constant lookup |

## User experience and next decision

The user installs one skill with the ordinary stock command, then runs one
documented command with four clear host variables. The smallest later UX
improvement worth measuring is accepting a confirmed detector finding ID as a
TypeScript command input without weakening the required human cohesion
judgment. Do not extract shared resolver infrastructure yet. Expand only after
a second proposal-style consumer proves the same move-impact and closure
contract, or add a named framework packet with its own compatibility fixture.
