---
name: portable-host-profile-routing
title: "Portable host profiling and capability-aware routing"
status: promoted
date: 2026-07-16
authors: [khurrum, codex]
motivating_decision: "0038"
successor_spec: portable-host-profile-routing
subsystems: [project-adaptation, skill-routing, perimeter-audit, activation-manifest]
workflows: [host-adoption, skill-routing, whole-codebase-audit]
---

# Portable host profiling and capability-aware routing

## 1. Scope & Bounds

Dependency-sized execution plan for WP2 of
`portable-skill-ecosystem-completion`. It owns AC-2.1–AC-2.6 exactly; the
master plan remains the completion ledger and takes precedence on ambiguity.

In scope: deterministic multi-root host profiles, project adaptation,
capability/layer/binding-aware routing, activation agreement, perimeter
coverage, and inherited Class B/C de-baking. Out of scope: physical layer
moves/installation (WP3), parser implementation (WP4), sweep productization
(WP5), and full catalog conformance (WP8).

## 2. Success Criteria

- **AC-2.1:** Deterministic schema-valid profiles for Python/Django,
  TypeScript/Node/React, Rust, Go, and a mixed monorepo include roots,
  exclusions, commands, and evidence for every assertion.
- **AC-2.2:** Adaptation consumes the profile, emits only registered IDs,
  cannot bypass perimeter audit, reports uncovered/accepted cells, is
  idempotent, and preserves host-owned identity/instructions.
- **AC-2.3:** `/which-skill` filters and explains capabilities/layers/bindings;
  it never recommends a Django-bound skill for the TypeScript fixture.
- **AC-2.4:** `/which-shape`, `/which-cleanup`, activation manifests, and
  `/which-skill` agree on active skills for one profile.
- **AC-2.5:** Perimeter coverage requires installed, version-compatible,
  executable evidence; exclusions remain visible; whole-codebase routing must
  run the audit before presenting a complete conclusion.
- **AC-2.6:** Profile-selected component inventory, ignore-first topology/
  frontend detectors, and neutral product-health labels replace seed-host
  fallbacks. Existing Class A and route-sprawl behavior is recorded first and
  remains green; Class C equivalence fixtures match the exemplar.

Verification and evidence protocol is inherited unchanged from the master.

## 3. Impact Map

| Surface | Change / evidence |
|---|---|
| `scripts/project_adapt.py` | canonical profile production/consumption and idempotent adoption |
| `.claude/skills/which-skill/` | capability-aware explanations and negative routing |
| `.claude/skills/which-shape/`, `which-cleanup/` | shared activation semantics |
| `.claude/skills/find-perimeter-gaps/` | evidence-backed multi-root coverage and visible exclusions |
| `scripts/manifest.py` and activation state | one profile-derived active set |
| Class B/C detector skills and fixtures | de-baked roots, inventories, scopes, and labels |
| tests/fixtures | five target hosts plus good/bad/bypass/idempotency oracles |

## 4. Blast Radius

Preserve current Python/Django adoption and invocation names; merge rather than
overwrite host files; keep ignore-first scope and Class A/route-sprawl output;
never report missing capability/tool evidence as a clean scan; and trace all
profile/manifest readers before changing schemas. Characterize the existing
Class A inventory and route-sprawl fixture/output before implementation.

## 5. Architecture Fit

Conforms to ADR 0038's single registry/support vocabulary and ADR 0034's
layer/binding model. Uses the canonical registry and profile as data, not new
consumer enums. Coverage is a capability/evidence join, not extension
guessing. Keep one profile schema and thin consumer projections; fail visibly
on unavailable evidence. No accepted smell or host-specific exception.

## 6. Open Decisions

No unresolved P0 fork. Profile vocabulary/support semantics are fixed by WP1.
Implementation may choose internal data structures without changing AC meaning
or creating another authored registry.

## 7. Promotion Notes

Promoted to `ai-docs/specs/portable-host-profile-routing.md`. Provenance is the
master plan's WP2 and AC-2.1–AC-2.6. Audited code roots are
`scripts/project_adapt.py`, `scripts/manifest.py`, and the `which-skill`,
`which-shape`, `which-cleanup`, and `find-perimeter-gaps` skill directories.
No acceptance wording was weakened during transcription.
