# P3 existing-substrate inventory

Captured: 2026-07-21
Spine revision: `f56a5f33e8844cbc9059ad2f25e92ae759cc6e7c`
Product baseline: `60898a705115bc4eeb12d0eca55e82c6a7d217ea`

This inventory is the interface-depth gate for P3. It identifies the existing
mechanics that P3 must extend and the policy that a shared surface is allowed to
remove. A P3 change that creates a parallel replacement for one of these
surfaces, or centralizes domain semantics, fails this gate.

## Existing primitives and P3 decisions

| Existing primitive | Current responsibility | P3 decision | Allowed shared policy |
|---|---|---|---|
| `scripts/source_inventory.py` | Contained, symlink-safe source discovery; language support visibility; role classification; atomic JSON output | Extend in place from strict language profiles. Do not add a second inventory engine. | Suffix/language mapping, excluded directory roles, source/test/generated/vendor/build/declaration/configuration/tooling/symlink classification |
| `scripts/build_multilanguage_matrix.py` and accepted `*-language-coverage.json` inputs | Joins the router catalogue with reviewed language evidence and publishes the capability matrix | Preserve as publication truth. Profiles describe runtime/tooling facts and must not become a competing skill-coverage matrix. | None beyond joining a profile identifier/version into evidence where later needed |
| `tests/support/portability_journey.py` | Validates an exact on-demand handoff, hashes closure bytes, snapshots source, observes artifacts, and runs literal native checks | Extend with narrow lifecycle/conformance assertions. Do not build a second journey runner. | Exact documented-command replay, terminal outcome validation, same-destination transitions, source preservation |
| `.claude/skills/find-omnibus/scripts/detect.py` plus `tests/test_omnibus_typescript.py` and `tests/test_find_omnibus_java.py` | Representative skill-local tool resolution, role filtering, language parser dispatch, stale Java artifact clearing, and terminal evidence | Use as the two P3 consumers. Extract only mechanics proven identical; preserve parser facts, scan payloads, clean/unsupported meaning, and reports locally. | Atomic text/JSON writes, stale-output removal, source-manifest mechanics |

## Consumer and policy-removal check

The initial consumers are exactly the TypeScript and Java paths of
`find-omnibus`. The shared profile removes duplicated declarations of suffixes,
project markers, source roles, tool requirements, verification commands, fact
tiers, and explicit limitations. The doctor removes duplicated tool-location
and version-reporting policy. The lifecycle helper removes duplicated safe
write/invalidation mechanics. The journey extension removes duplicated proof of
closure containment, source preservation, terminal status, and transition
behavior.

The following remain skill-owned because their meaning varies by analysis:

- AST, symbol, fact, finding, proposal, and report schemas;
- mutation, rollback, and guard generation;
- the distinction between a clean analysis and an unsupported analysis;
- framework semantics and framework-specific verification;
- dependency installation, caching, scaffolding, and network access.

## Rejected reuse

- `scripts/_lib/lang_adapter/` is not used: its adapter contract is broader and
  would force semantic analysis into the substrate.
- `status_schema.py` is not used: P3 needs a small terminal lifecycle vocabulary,
  not a universal result schema.
- `artifact_scope.py` is not used: the portability journey already owns bounded
  read-only artifact observation, while mutation artifacts remain skill-owned.

## Representative lifecycle gaps P3 must prove

`source_inventory.py` already writes JSON atomically. The Java omnibus path
already clears stale output across valid-to-failed transitions, but its JSONL
and scan writes are not atomic. TypeScript proves copied-closure isolation but
does not yet exercise the same destination transitions. P3 may share the safe
mechanics needed to close those exact gaps; it may not generalize the final
artifact schema.
