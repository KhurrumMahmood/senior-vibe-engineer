# Inward Pass — 02c: Idea de-duplication + ideal shape (structural layer)

Read-only structural analysis of the ES3 skill corpus (68 skills), 2026-05-25.
Pillar 3 of the combined inward pass — companions: `02a-mechanical-duplication.md`
(does the corpus share CODE?), `02b-behavioral-conformance.md` (do the skills
actually WORK?). Synthesized in `02-inward-combined-pass.md`. This pillar answers
self-review §8.1 (the real ideas, de-duplicated) and §8.2 (ideal shape).

## Measured shape (live, 68 skills)

```
JOB (67 carry job): suspect 28 | meta 11 | explain 9 | plan 6 | teach 2
                    refactor 2 | map 2 | guard 2 | decide 2 | triage 1 | diagnose 1 | construct 1
TIER:               maintenance 43 | cross-cutting 19 | system 4 | feature 1
NAME-PREFIX:        find- 27 | extract- 5 | plan- 3 | which- 2 | propose- 2 | map- 2 | (33 singletons)
```

Job and name-prefix agree: the corpus is overwhelmingly **detect-and-fix**, and
the detection is one mega-family.

## §8.1 — The canonical ideas (68 skills → ~10 ideas)

| # | Idea (job) | Skills | Count |
|---|---|---|---|
| 1 | **Detect debt** (suspect) | 26 of the 27 `find-*` + `audit-decisions` | ~27 |
| 2 | **Propose the explicit form** (explain) | extract-{cotton-primitive,enum,state-type,workflow-registry}, introduce-fk, unify-shadows, propose-{boundary,folder-reorganization}, explain-code, teach-pattern | 10 |
| 3 | **Execute the cleanup** (refactor) | refactor-subsystem, fix-workflow | 2 |
| 4 | **Guard the fix back** (guard) | prevent-regression | 1 |
| 5 | **Plan & decide** (plan/decide) | plan-{feature,skill,spec}, scope-feature, impact-feature, architecture-fit, decide, design-it-twice | 8 |
| 6 | **Ideas subsystem** (meta) | track-idea, brainstorm-ideas, mature-existing-ideas, extract-existing-ideas, query-patterns, find-orphaned-ideas | 6 |
| 7 | **Map / inventory** (map) | map-subsystem, map-product-workflow | 2 |
| 8 | **Bootstrap & orient** (meta) | orient, engineer-init, adapt-project, project-interview, which-skill, which-shape, gut-check | 7 |
| 9 | **Diagnose symptoms** (diagnose) | diagnose | 1 |
| 10 | **Harvest standards** (meta/suspect) | harvest-learnings, find-standard-gaps | 2 |

Idea 1 (**detect**) further splits into three named sub-ideas, by the smell each targets:

- **duplication ×4** — find-{duplication, semantic-duplication, frontend-duplication, workflow-duplication}
- **drift / staleness ×13** — find-{async-lifecycle, comment, contract, doc-route, folder-topology, frontend-contract, rule-surface, skill-artifact, test-obligation}-drift + find-{concept-divergence, stale-artifacts, workflow-state-gaps, standard-gaps}; `check-ecosystem-consistency` is drift-adjacent but not `find-*`-named
- **structural smell ×9** — find-{dormant, omnibus, implicit-state, layer-violation, query-mutation, transaction-overreach, complexity-hotspots, route-sprawl, dead-route-surface}

(`find-orphaned-ideas` is name-prefixed `find-` but belongs to idea 6, not detection — the
name-prefix analog of this session's `extract-existing-ideas` carve-out: the prefix is not
the idea.)

**The load-bearing imbalance.** Idea 1 (detect) holds ~40% of the corpus; idea 4 (guard)
holds **one** skill. The ecosystem is excellent at *finding* debt and nearly silent at
*converting a closed fix into an automatic standard* — exactly the activation gap VISION
destination 2 names ("the right ideas are standards, activated automatically"). Detection
is overbuilt; guard-back is a stub. (This is the structural-layer echo of what 02b tests
behaviorally: a skill ecosystem that detects 27 ways but guards 1 way is under-defending
its own outputs.)

## §8.2 — Ideal shape

The 68 flat dirs are **not shapeless** — they carry obvious idea structure the flat layout
hides. ADR 0006 ("≥3 `<prefix>_*` siblings earn a package") applies directly at the
skill-dir level, and several clusters clear the bar by a wide margin:

```
.claude/skills/
  find/                      # 27 -> sub-package by smell:
    duplication/   (4)
    drift/         (13)
    smell/         (9)
  propose/                   # 10  the EXPLAIN proposers (extract-*, introduce-fk, unify-shadows, propose-*)
  plan/                      # 8   plan-*, scope/impact/architecture-fit, decide, design-it-twice
  ideas/                     # 6   track/brainstorm/mature/extract-existing/query-patterns/find-orphaned
  orient/                    # 7   orient, engineer-init, adapt-project, project-interview, which-*, gut-check
  map/   refactor/   guard/  # 2 / 2 / 1
  diagnose/  harvest/        # 1 / 2
```

A flat **68 collapses to ~7–8 idea packages**, each mirroring an idea from §8.1 — VISION
destination 3 (shape mirrors intent), applied to the ecosystem itself.

### The tool gap (the finding that bites)

The ecosystem's **own** `propose-folder-reorganization` cannot propose this. Its
`inspect.py` is scoped to underscore **module** siblings — `--parent <dir> --prefix
<name>` over `<prefix>_*.py` files (ADR 0006's *Python-module* case). It does **not**
reach the hyphenated skill-**dir** grouping above. `which-shape/route.py` routes a
*situation → shape recommendation*; it does not restructure a corpus either. So:

> The ecosystem can detect 27 kinds of debt in a host project but **cannot currently
> propose its own ideal shape** — the precise "ideal-shape / compose" corner the
> self-review §5 calls "the least-built corner… the one the vision most needs."

That is not a vague gap; it is a missing capability with a clear shape: a folder-reorg
mode that clusters **hyphen-prefixed sibling directories** by leading token (and ideally
by `job:`), the dir-level analog of the existing `<prefix>_*.py` mode.

## Cross-references into the other pillars

- **02a (mechanical):** name-prefix proves the 4-dup and 13-drift *families* exist; 02a
  proves whether they share **code** (the §2 "shared report + fan-out scaffold"
  hypothesis) or merely names. Idea-level DRY (this file) and code-level DRY (02a) are
  different claims — both needed for VISION destination 1.
- **02b (behavioral):** idea 1's 27 detectors are advisory *lists* (graded by
  precision/recall vs labels); idea 4's 1 guard is the only thing skill-comply can grade
  by "did it fire." The detect/guard imbalance here predicts 02b's bucket sizes.
  - **Cross-session reconciliation (2026-05-25):** a co-located agent just captured the
    skill-comply future in the **host-a** ledger — parent idea `skill-spec-conformance-validation`
    (skill-comply is its realization) with child `skill-comply-real-run-orchestration`
    (Stage 3, proposed/harness). Our behavioral pillar is the **cross-skill generality**
    evidence for that parent idea (STAGE2 follow-up #4). Synthesis must POINT AT those
    existing ideas, not mint a duplicate intake.

## Disposition (this pillar)

- **fix-now candidate:** none — read-only diagnostic.
- **log-later (intake):** "folder-reorg: hyphen-prefixed sibling-dir mode" — extend
  `propose-folder-reorganization` to the dir-level/`job:`-clustered case so the ecosystem
  can shape itself. Revisit-when: the corpus is actually restructured, or a second flat
  ≥3-sibling dir cluster appears in a host project.
- **monitor:** the detect(27)/guard(1) imbalance — re-measure as guard/construct skills land.
