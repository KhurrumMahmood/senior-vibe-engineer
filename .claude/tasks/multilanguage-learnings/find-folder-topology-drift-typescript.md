# `find-folder-topology-drift` — TypeScript v1 learning handoff

## Invariant

Under an explicitly supplied TypeScript source root, report only a direct-file
cluster of three or more `.ts`/`.tsx` siblings sharing a first domain token
before `_` or `-`. The result is lexical evidence, not an import-safe move or
package recommendation.

Python remains additive: its four existing bands (`flat_prefix_cluster`,
`tests_by_prefix`, `sparse_folder_package`, and `pages_route_mirror`) run as
before. The TypeScript path neither replaces nor broadens them.

## Implementation and boundary

`--typescript-root` is repeatable and required for TypeScript scanning. The
skill validates that every supplied root is an existing directory within
`--project-root`; an invalid root exits 2 rather than falling back to a wider
scan. TypeScript v1 excludes `index.ts[x]`, declarations, spec/test files,
test trees, generated/vendor/dependency/build/report trees, and additive
`--exclude` matches. It does not make package-density, test-placement,
Next/pages, barrel, module-resolution, import-safety, or framework claims.

The old repository `_common` imports prevented a copied selected skill from
running with `python -I -S`. `scripts/support.py` now bundles only this
family's scope parsing/walk and report rendering. No shared helper or platform
was introduced.

## Fixture and verification evidence

The committed fixture root is
`tests/fixtures/find-folder-topology-typescript/`.

- Python positive fixture fires each preserved band once; the Python clean
  fixture keeps a two-file cluster, test tree, and migrations package clean.
- The TypeScript fixture produces exactly one result for
  `billing_parser.ts`, `billing-validator.ts`, and `billing-types.ts`.
- Two siblings, mixed prefixes, `tests/`, `__tests__/`, `index.ts[x]`,
  declarations, `*.spec.ts[x]`, `*.test.ts[x]`, generated, vendor,
  node_modules, dist, build, coverage, reports, and a declared custom exclude
  stay clean.
- The final Markdown and JSON artifacts assert `language: typescript` and
  `pattern: flat_prefix_cluster`; source hashes stay unchanged.
- A copy containing only the selected skill runs detector and reporter from an
  unrelated cwd with `python -I -S`.

Commands run on this revision:

```bash
.venv/bin/python -m pytest tests/test_find_folder_topology_typescript.py -q
.venv/bin/python -m ruff check .claude/skills/find-folder-topology-drift/scripts tests/test_find_folder_topology_typescript.py
.venv/bin/python scripts/skill_meta.py lint
.venv/bin/python .claude/skills/_common/scripts/run_skill_smokes.py --skills-dir .claude/skills --timeout 10
.venv/bin/python -m pytest tests/test_find_folder_topology_typescript.py tests/test_yaml_frontmatter.py tests/test_skill_meta_jobs.py tests/test_skill_taxonomy.py tests/test_scope.py tests/test_run_skill_smokes.py -q
```

Results: 5 passed for the dedicated suite; Ruff clean; frontmatter lint found
76/76 skills declaring the new contract; the smoke gate passed (11 explicit
smokes, 42 import-floor scripts); the focused metadata/scope/smoke matrix
passed 63 tests. A direct Python replay of the selected skill against its own
source directory wrote zero findings and both final artifacts.

## D1–D8 status

| Gate | Status | Evidence |
|---|---|---|
| D1 scope honesty | pass | Skill states explicit-root lexical TS invariant and every excluded mode. |
| D2 Python oracle | pass | Locked positive and clean/must-not-fire fixtures cover all four Python bands. |
| D3 TypeScript outcome | pass | Final `detections.jsonl` → `report.md` / `findings.json` test asserts the single labeled finding. |
| D4 change or guard | not applicable | This is a read-only detector; no mutation or blocking guard is claimed. |
| D5 installed closure | pass | Copied skill runs detector and reporter under `python -I -S` outside checkout with no `_common` import. |
| D6 fresh forward task | pending | All four agent slots were occupied at commit time; parent will dispatch the installed natural task after a slot opens. |
| D7 regression and conformance | pass | Dedicated, metadata/scope/smoke, Ruff, frontmatter, and Python replay evidence above. |
| D8 learning handoff | pending D6 | This packet is complete except for the forward-task transcript and reviewer result. |

## What generalized and what did not

The reusable ideas are narrow: explicit roots, direct-sibling grouping,
additive excludes, deterministic JSONL, and a self-contained stdlib runtime.
They have only this accepted consumer, so `support.py` remains family-local.

Python's bidirectional package policy, Django folder exemptions, page-route
mirror rule, and host scope descriptors do not generalize to TypeScript. Nor
does TypeScript naming establish import resolution or a safe package move.

## Next-language translation prerequisites

| Language | Native capability before support | Required locked fixture | Remaining semantic gap |
|---|---|---|---|
| Rust | stdlib path walk over direct `.rs` files; cargo is only needed if a later move claim requires compile proof | three common-token files plus `mod.rs`, tests, generated/vendor equivalents | module declarations and `mod.rs` ownership are not inferred by lexical names |
| Go | stdlib walk over direct `.go` files; `go test` only for a later package change | three direct production files plus `_test.go`, generated, vendor, and package-boundary cases | package/import behavior and build tags remain unresolved |
| Java/Kotlin | stdlib walk for `.java`/`.kt`; Gradle/Maven only for later source moves | three naming-cluster source files plus test/generated and class-name convention cases | class/file identity and package/import impact are unresolved |
| C# | stdlib walk for `.cs`; `dotnet test` only for later mutation claims | three direct source siblings plus `.g.cs`, test, obj/bin exclusions | partial classes, namespaces, and project membership remain unresolved |
| Ruby | stdlib walk for `.rb`; Bundler/RSpec only for later move claims | three common-token files plus `_spec.rb`, generated/vendor exclusions | load-path/autoload/constant resolution remains unresolved |

## Residual risk and next decision

This detector can miss clusters whose domain is expressed without a shared first
filename token, and it intentionally reports no TypeScript package demotion or
test placement. Keep it at this lexical advisory boundary. Expand only after a
separate TypeScript proposal family proves resolved import impact and a
framework-specific convention with its own fixtures.
