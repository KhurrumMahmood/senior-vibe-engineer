---
name: shareable-core-reorganization
title: "Shareable-core reorganization: layering, generalization, distribution"
status: scoped
date: 2026-06-11
authors: [khurrum, claude-code]
motivating_decision: "0034"
successor_spec: null
subsystems: [skills, contracts, scripts, decisions]
workflows: []
---

# Shareable-core reorganization: layering, generalization, distribution

Make the ecosystem easily shareable: a host project (Django today,
TypeScript/other tomorrow) installs only what applies to it, gets honest
coverage claims, and reaches first value fast. This plan is the embodiment
tracker for ADR 0034 (skill namespace layering) and the execution vehicle
for the de-baking recon (`.claude/tasks/classbc-recon.md`), the ADR
embodiment backlog (0026-0030, 0003), and the on-ramp gaps named in the
June 2026 ecosystem assessment.

## 1. Scope & Bounds

**In scope — six workstreams, roughly in dependency order:**

- **W1. Layer migration (ADR 0034).** Assign every skill a layer
  (core / lang / framework / domain / host-overlay). Resolve the discovery
  mechanics question first (nested dirs vs. name prefixes vs. plugin
  packaging — ADR 0034 §5). Update routing (which-*), the activation
  manifest, `find-perimeter-gaps`, contracts `_index`, and skill-catalog to
  be layer-aware. ADR 0024 (rename completeness) and 0028 (path
  verification) govern the move commits.
- **W2. De-flavoring incidentally-coupled skills.** The plan-* chain,
  refactor-subsystem, prevent-regression and similar skills whose
  *procedure* is universal but whose examples/defaults are Django: examples
  move to a binding or appendix; `language:`/`framework:` frontmatter
  corrected to declared-honest values (ADR 0032's honesty rule).
- **W3. Concept+binding extraction.** For the high-value detectors and
  extract-* skills whose concept generalizes (stringly-state→enum,
  read-mutates, unguarded dispatch, implicit relation→explicit FK, handler
  LOC budget): framework-neutral body in core + thin `bindings/django.md`.
  One exemplar first (extract-enum is the candidate — its concept/binding
  seam is the cleanest), then the pattern is repeated only after the
  exemplar survives review.
- **W4. Class B/C de-baking.** Execute `.claude/tasks/classbc-recon.md`:
  descriptor-driven component profile for the cotton inventory hard-fail,
  neutral surface labels in `product_health.py`, scope integration for the
  two Class C detectors — `find-route-sprawl` is the established clean
  exemplar. Class A is already landed and tested.
- **W5. ADR embodiment sweep.** Build or formally defer the decided/
  proposed-but-unbuilt backlog, in this order: 0026 (lint-allow marker —
  lint infra), 0027 (wire-identifier preservation — lint + refactor-skill
  rule), 0028 (asset-path verification — refactor verification step),
  0029/0030 (detector bands in route-sprawl / propose-boundary), 0003
  (findings ledger — schema + outcome field, feeds the effectiveness-audit
  response). Each lands with its ADR's `embodied_by` updated (ADR 0033).
- **W6. On-ramp + distribution.** Onboarding-flow doc (the funnel as one
  diagram), lite-mode doc ("three skills standalone; governance optional;
  cost of skipping each"), per-stack skill portfolios, and the packaging
  decision (plugin manifest / versioned install vs. folder-copy) — the
  packaging *choice* is a §6 open decision, not assumed here.

**Out of scope / non-goals:**

- Building full TypeScript (or other-language) adapters beyond what W3's
  exemplar and `find-omnibus`'s existing JS adapter already prove. The
  portability roadmap's trigger (a real second-stack host) still governs.
- Redesigning the effectiveness/telemetry system beyond the 0003 schema
  work (the activity≠outcome response is its own thread).
- Renaming or consolidating the detector fleet (the 30→12 consolidation
  idea stays an idea; this plan moves skills between layers, it does not
  merge them).
- Any host-project (`host:`-scoped) content.

## 2. Success Criteria

Observable outcomes, not milestones:

1. **Layer-aware install works:** on a non-Django fixture repo, installing
   core-only yields a catalog with zero framework/django skills listed by
   the routers, and `find-perimeter-gaps` reports coverage honestly (no
   detector claims a language it cannot scan).
2. **No framework leakage in core:** no SKILL.md under the core layer names
   Django/Celery outside a `bindings/` file; enforced by a diff-scoped lint
   (the W3 exit guard), not by review memory.
3. **The exemplar binding round-trips:** extract-enum's framework-neutral
   body + django binding produces the same proposal on the Django fixture
   it produced before the split (behavior-preserving migration, proven by
   the existing dogfood case).
4. **Embodiment backlog visibly shrinks:** `decisions.py link-check` lists
   strictly fewer `pending:`/empty-embodiment ADRs than at plan start
   (baseline: 0026-0031 unbuilt, 0003 open), and none regress.
5. **Time-to-first-value documented and short:** a newcomer following the
   onboarding-flow doc reaches a first useful skill run in ≤20 minutes
   without reading the kernel doc; the lite-mode doc names the 3-skill
   starter explicitly.
6. **All moves are reference-clean:** post-migration, `skill_meta.py lint`,
   contracts `_index` regeneration, `find-skill-artifact-drift` Band A, and
   the decisions audit all run green — no dangling skill names anywhere in
   docs, routers, or contracts.

## 3. Impact Map

_To be completed by `/impact-feature`. Known major surfaces: every
SKILL.md path (move or de-flavor), `.claude/contracts/skills/*` (paths +
`_index` regeneration), `scripts/skill_meta.py` (layer awareness),
which-skill / which-shape / which-cleanup (catalog walks), skill-catalog
and CLAUDE.md doc references, `.engineering/manifest.json` schema,
`find-perimeter-gaps` + `find-skill-intent-drift` (path assumptions),
`.claude/skills/_common/` (binding loader conventions)._

## 4. Blast Radius

_To be completed by `/impact-feature`. Known behaviors to preserve: every
skill remains invocable under its existing name (or a recorded alias) so
host muscle memory and the contracts' provenance chains survive; dogfood
cases in contracts keep passing; the pre-commit skill-artifact-drift gate
stays green through every move commit._

## 5. Architecture Fit

_To be completed by `/architecture-fit`. Pre-known conformance: ADR 0032
(adapter pattern, honesty rule), 0033 (embodiment updates per workstream),
0034 (the layering itself), 0024/0028 (move-commit discipline), 0006 (the
N=1 contract-boundary exception is scoped in 0034 §3)._

## 6. Open Decisions

- **Packaging/distribution mechanism** (W6): plugin manifest vs. versioned
  folder-copy vs. both. Needs its own `/decide` — it constrains the layer
  mechanics answer (ADR 0034 §5).
- **Discovery mechanics** (W1): nested skill dirs vs. name prefixes vs.
  packaging-level namespacing — verify what the harness actually supports
  before the first move commit; record the answer in 0034's embodiment
  update.
- **Binding loader convention** (W3): how a core skill's body references
  its binding at run time (frontmatter field vs. conventional path) —
  decide at the exemplar, not before.

## 7. Promotion Notes

_Filled by `/plan-spec` when promoted._
