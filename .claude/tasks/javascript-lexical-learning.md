# JavaScript lexical cohort learning

## Evidence contract

Support is earned at each skill's final artifact or explicit outcome, not by
recognizing a suffix. All read-only tests hash source trees before and after;
reports/configuration boundaries are exercised where the skill produces them.

## Per-skill record

| Skill | Mechanism and evidence mode | Reused TypeScript parts | Deliberately not reused / limitation |
|---|---|---|---|
| `adapt-project` | First-party `.js`/`.jsx`/`.mjs`/`.cjs` counts plus a per-suffix breakdown in `adapter.json` and `report.md`; JavaScript presence never infers a Node framework. | Existing source-root boundaries and TypeScript count shape. | The established Python/TypeScript-only adapter JSON remains byte-compatible when JS count is zero; no module or framework inference. |
| `explain-code` | Separate JavaScript lexical collector emits direct ESM named functions/classes/variables and property-form CommonJS assignments. Aliases, stars, defaults, CommonJS object/dynamic exports, and unenumerable bindings stay visible in `unexplained`; malformed selected JS emits `syntax-error` and no targets artifact. | Ranking schema, output schema, lexical-boundary philosophy. | Separate JS masking/collector rather than a shared parser. It does not resolve imports, dynamic exports, modules, or JSX semantics. |
| `find-comment-drift` | Existing JS lexical comment/JSDoc detector now accepts all four JS suffixes; copied detector/report output remains the artifact truth. | Existing JS/TS comment bands. | No parser is needed. Root serial verification confirmed the existing pre-commit identify tags already route `.mjs`/`.cjs`. |
| `find-concept-divergence` | Strict textual scan accepts all four suffixes and rejects generated/vendor/test/minified/symlink inputs. | Existing word-boundary term logic and report schema. | No syntax/semantic claim: it scans text only, and malformed source is still lexical input rather than a syntax outcome. |
| `find-duplication` | A separate project-local-tool runner stages eligible JS, writes `tool-missing`, `syntax-error`, `tool-failed`, or `partial` to `run.json`, then maps successful jscpd pairs to conservative named JS spans before the final triage/report boundary. | Output/rank vocabulary and conservative TypeScript source-span idea. | No npm, npx, network install, global-tool assumption, shared parser, semantic-equivalence claim, caller proof, or safe-consolidation claim. Span mapping only accepts named functions/block arrows. |
| `find-folder-topology-drift` | Separate `--javascript-root` collector reports direct sibling first-token clusters for all four suffixes; final reporter accepts `javascript` and mixed-language labels. | TypeScript explicit-root/output pattern. | No package density, import resolution, barrel/framework convention, or safe move claim. Index/test/generated/minified/vendor/symlink paths are excluded. |

## Verification

Executed with `/Users/khurrummahmood/Projects/engineering-skills/.venv/bin/python`: <!-- host-ref-allow: required worktree validation interpreter -->

```text
python -m pytest -q tests/test_javascript_lexical_cohort.py
5 passed in 1.37s

python -m pytest -q tests/test_javascript_lexical_cohort.py tests/test_adapt_project_typescript.py tests/test_explain_code_typescript.py tests/test_comment_drift_typescript.py tests/test_find_duplication_typescript.py tests/test_find_folder_topology_typescript.py tests/test_b1_portability.py
67 passed in 14.64s

python -m ruff check <owned Python files> tests/test_javascript_lexical_cohort.py
All checks passed!
```

The cohort test covers positive and negative outcomes, all four suffixes,
mixed JS/TS roots, generated/vendor/test/minified/symlink exclusions where the
family has a source collector, read-only source hashes, malformed JavaScript
where lexical parsing is required, `tool-missing`, `partial`, and real final
report/configuration boundaries.

## Failures and pitfalls

- Adding zero-valued JavaScript keys to every `adapt-project` root changed the
  established TypeScript adapter contract. Emit JavaScript count fields only
  once first-party JavaScript is observed.
- `package.json` fallback must not append `javascript` to a TypeScript-only
  host; it remains a fallback only when no source-language evidence exists.
- A lexical include list is insufficient on its own: direct symlink paths and
  minified files need explicit exclusions in each family-local collector.
- A successful clone tool run is not a semantic result. Preserve tool/status
  artifacts and map only spans that can be lexically established.

## Shared integration requests for serial work

1. Update shared source inventory, routers/catalogs, coverage/capability
   matrices, `build_multilanguage_matrix.py`, and the language plan/backlog
   only after serial review of this cohort's final artifacts.
2. Keep the next language cohort family-local: copy the evidence model and
   explicit failure outcomes, but do not promote the JavaScript lexical
   maskers or clone span mapper into a cross-language parser platform.
