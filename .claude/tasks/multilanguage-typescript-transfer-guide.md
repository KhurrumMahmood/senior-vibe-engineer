# TypeScript-to-next-language transfer guide

Status: P0 synthesis of accepted TypeScript evidence

Use this guide to plan a new language adapter without replaying the full
TypeScript implementation history. The machine-readable inventory is
`.claude/tasks/multilanguage-skill-matrix.json`; raw evidence remains under
`.claude/tasks/multilanguage-learnings/` and the cited test files.

For every skill, the matrix records the current relative on-demand closure:
each selected/companion skill root, `SKILL.md`, bundled `scripts/` directory
when present, and the shared `scripts`, `_common`, and docs roots. Resolve those
paths under the bootstrapped library returned by the router. The matrix also
retains the old stock selected-install command as
`historical-stock-selected-install` evidence. Optional task-skill installation
is secondary and explicit; it is not the primary execution journey.

## Translation sequence

For each skill:

1. Freeze the final user outcome and its source-mutation boundary.
2. Select the weakest fact level that can establish that outcome: lexical,
   syntax, semantic/project, then framework.
3. Inventory all first-party target-language files before applying narrower
   eligibility rules.
4. Use the target language's native parser/compiler/project model when the
   claim requires it. Pin or discover it from the audited host.
5. Preserve complete, partial, unsupported, and failed as distinct states.
6. Lock positive, negative, must-not-fire, malformed/tool-missing, and native
   verification fixtures.
7. Run the selected guide/tool closure from the on-demand library, verify the
   final artifact or intended diff, and record what did not transfer.

Do not begin by translating the TypeScript AST walker. Begin with the outcome
and determine which native facts the new language needs.

Before implementation, copy the row's `on_demand_closure` into the work packet.
Do not reconstruct it from the historical optional-install command. If that
row reports optional installation as anything other than `passed`, treat the
mode as unsupported until separately repaired.

## Language-level family map

The packet column names the JSON packet containing detailed false-positive,
tooling, closure, and replay evidence. Test paths are recorded per row in the
generated matrix.

| Skill | Fact / outcome | TypeScript mechanism | Translation contract | Packet |
|---|---|---|---|---|
| `adapt-project` | lexical/filesystem; configuration output | Skill-local source-root discovery | Count and classify first-party roots without inferring a framework from dependency metadata. | `adapt-project-typescript.json` |
| `audit-decisions` | syntax; read-only report | Host TypeScript comment trivia | Attribute references only from real comments; strings, templates, and malformed syntax must not become evidence. | `audit-decisions-typescript.json` |
| `explain-code` | lexical/filesystem; read-only explanation | Conservative direct-export collector | Explain only the public surface actually established; unresolved aliases and re-exports stay explicit. | `explain-code-typescript.json` |
| `extract-enum` | semantic/project; proposal | Compiler receiver/type facts consumed from the state detector | Preserve attributed callers, current values, ambiguity, and proposal-only behavior before guard generation. | `b2p-state-reference.json`, `b2t-typescript-closed-state.json` |
| `find-comment-drift` | lexical/filesystem; read-only report | Skill-local lexical detector | Advisory comment/code mismatch requires no semantic platform; unreadable input is failure, not clean. | `b3-comment-drift.json` |
| `find-complexity-hotspots` | syntax; read-only report | Compiler syntax tree and direct control-flow body walk | Count only the frozen syntactic score; nested-function and framework semantics remain outside the claim. | `find-complexity-hotspots-typescript.json` |
| `find-concept-divergence` | lexical/filesystem; read-only report | Exact phrase scan across declared source/document suffixes | Inventory the full source set and preserve phrase/identifier boundaries; no rename-completeness claim. | `b1-portability.json` |
| `find-dormant` | semantic/project; read-only review queue | Program/TypeChecker reference identity | Report review candidates, never safe deletion; exports, dynamic reachability, registrations, and unresolved modules remain conservative. | `find-dormant-typescript.json` |
| `find-duplication` | lexical/filesystem; read-only triage | Pinned offline jscpd plus span-to-symbol mapping | Detect lexical/near clones and enclosing symbols without claiming behavioral equivalence or safe consolidation. | `find-duplication-typescript.json` |
| `find-folder-topology-drift` | lexical/filesystem; read-only report | Path inventory and narrow prefix clustering | Apply an explicit repository folder policy; tests, barrels, generated/vendor paths, and below-threshold clusters must not fire. | `find-folder-topology-drift-typescript.json` |
| `find-implicit-state` | semantic/project; read-only findings | Program/TypeChecker receiver-state facts | Prove the relevant receiver and state literals; lexical property-name matches cannot substitute for type identity. | `b2p-state-reference.json`, `b2t-typescript-closed-state.json` |
| `find-incomplete-sweep` | semantic/project; read-only triage | Resolved callees/options plus explicit human verdicts | Preserve aliases, overload/default/spread uncertainty, framework exclusions, Git trajectory, and candidate-to-verdict lineage. | `find-incomplete-sweep-typescript.json` |
| `find-omnibus` | syntax; read-only report | Compiler top-level symbol spans | Extract trustworthy symbol spans only; do not import the old JavaScript column-zero heuristic as a semantic parser. | `find-omnibus-typescript.json` |
| `find-semantic-duplication` | semantic/project; read-only triage | Program/TypeChecker direct-call and return-shape facts | Separate confirmed, uncertain, and rejected pairs; caller, protocol, policy, and dynamic boundaries remain visible. | `find-semantic-duplication-typescript.json` |
| `find-standard-gaps` | syntax; read-only coverage report | Rule-specific compiler syntax walker | Freeze one concrete standard and its oracle; unsupported or malformed files make the result partial, not clean. | `find-standard-gaps-typescript.json` |
| `map-subsystem` | semantic/project; read-only map | Named project graph with resolved imports/exports | A complete map needs resolved inbound/outbound edges; unresolved edges and unavailable policy fields stay explicit. | `map-subsystem-typescript.json` |
| `move-path` | lexical/filesystem; source mutation | Bounded path/text move and residue audit | Declare whether code imports are supported; verify containment, exact diff, residue, and native build rather than implying parser-safe rewrites. | `move-path-typescript.json` |
| `prevent-regression` | semantic/project; guard generation | Generated compiler-backed closed-state guard | Generate only from an accepted invariant, preserve violation/tool-error exit states, and run the target's native verification. | `b2p-state-reference.json`, `b2t-typescript-closed-state.json` |
| `propose-boundary` | semantic/project; proposal | Resolved symbol/import/call graph | Cite a complete-enough graph, public API, callers, compatibility, and tests; cohesive or unresolved targets defer. | `propose-boundary-typescript.json` |
| `propose-folder-reorganization` | semantic/project; proposal | Resolved import-impact graph | Account for every selected member, alias/barrel compatibility, callers, moves, and tests; unsafe or unresolved impact blocks. | `propose-folder-reorganization-typescript.json` |
| `rename-concept` | semantic/project; read-only assessment | Lexical companion plus language-service identifier evidence | Combine prose divergence with identifier-reference completeness; diagnostics or unavailable semantic evidence prevent certification. | `b1-portability.json`, `rename-concept-typescript.json` |
| `unify-shadows` | semantic/project; proposal | Validated structured upstream finding | Consume one confirmed finding with cited spans/matrix/callers; keep-separate is valid and no new analyzer is implied. | `unify-shadows-typescript.json` |

## Repeated TypeScript primitives

The generated matrix records exact consumer lists and keeps this inventory
fresh. P1 evaluated these primitives in this order:

1. project-local TypeScript resolution and project-root containment;
2. explicit `tsconfig` loading with preserved diagnostics;
3. path containment, symlink rejection, and relative-path rendering;
4. complete first-party `.ts`/`.tsx` inventory with attributed exclusions; and
5. a shared status vocabulary only—not a shared analysis result schema.

P1 stopped runtime extraction: candidates 1–3 remain family-local until a real
two-consumer repair proves both the API and the selected-install closure.
Candidate 4 produced the shared read-only source-inventory contract, without
coupling analyzers to it. Candidate 5 became the test-harness outcome contract,
not a shared analysis result schema. See the P1 decision in
`multilanguage-expansion-plan.md` for the promotion trigger.

Do not extract the following merely because several files use the Compiler
API:

- analysis-specific AST walkers;
- call grouping, clone ranking, or state inference;
- report and proposal schemas;
- jscpd orchestration;
- mutation or guard generation; or
- framework route, ORM, job, or UI semantics.

## What must not be generalized

- TypeScript compiler availability does not prove JavaScript semantic coverage.
- A suffix match does not establish file role, relevance, parse success, or
  mutation safety.
- Syntax facts do not establish reference identity, type identity, dynamic
  reachability, or runtime equivalence.
- Lexical duplication does not establish safe consolidation.
- Static non-reference does not establish safe deletion.
- A dependency name does not establish the active framework or its conventions.
- TypeScript project/module assumptions do not transfer to Go modules, JVM
  builds, .NET solutions, Rust crates, or monorepo boundaries.
- The Python implementation language of a helper is not evidence that the
  inspected host must be Python.
- A successful intermediate facts file is not completion; the skill's final
  artifact, native verification, and source boundary remain authoritative.
- Shared tooling must not create a hidden dependency for optional task-skill
  installation. On-demand closure is primary; optional installation must be
  self-contained or explicitly unsupported.

## Required next-language learning packet

Every pilot produces one compact JSON and Markdown pair recording:

- invariant and final outcome;
- native language/project model and exact tool resolution;
- positive, negative, must-not-fire, malformed, and tool-missing boundaries;
- complete/partial/unsupported/failed semantics;
- on-demand and optional-install closure behavior;
- native verification and source fingerprint/diff evidence;
- reused primitive and why it was actually equivalent;
- rejected abstractions and why; and
- concrete guidance for the next language.
