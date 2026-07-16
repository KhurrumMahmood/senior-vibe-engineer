---
id: portable-host-profile-routing
title: "Portable host profiling and capability-aware routing"
status: draft
last_audited: 2026-07-16
motivating_decision: "0038"
# `coverage` scans Python `# spec:<id>::IM-N` markers inside
# these roots only. Doc / skill / script / ADR IM items will
# never auto-tick here; track them via the spec checklist and
# audit-only `<!-- spec: -->` markers in the changed files.
code_roots:
  - scripts/project_adapt.py
  - scripts/manifest.py
  - .claude/skills/which-skill
  - .claude/skills/which-shape
  - .claude/skills/which-cleanup
  - .claude/skills/find-perimeter-gaps
---

# Portable host profiling and capability-aware routing

## Provenance

Promoted from `ai-docs/plans/portable-host-profile-routing.md`, which is the
dependency-sized execution plan for WP2 and AC-2.1–AC-2.6 of
`ai-docs/plans/portable-skill-ecosystem-completion.md`. The master plan remains
the completion ledger and controls if this spec is ambiguous. This spec adds
implementation detail without narrowing any acceptance criterion.

## Goals

- Produce one deterministic, schema-valid host profile for Python/Django,
  TypeScript/Node/React, Rust, Go, and mixed-monorepo fixtures, with roots,
  exclusions, commands, and evidence for every assertion (AC-2.1).
- Make project adaptation consume that profile, emit only registry-valid IDs,
  require an unbypassable perimeter audit, preserve host ownership, and remain
  idempotent (AC-2.2).
- Make skill routing capability-, layer-, and binding-aware, with an explanation
  for every material inclusion or exclusion (AC-2.3).
- Give `/which-shape`, `/which-cleanup`, activation manifests, and
  `/which-skill` one shared activation decision for a profile (AC-2.4).
- Require installed, version-compatible, executable evidence for perimeter
  coverage and keep accepted exclusions visible; whole-codebase conclusions
  must invoke that audit first (AC-2.5).
- Complete the inherited Class B/C de-baking work while preserving the pinned
  Class A and route-sprawl baselines (AC-2.6).

## Architecture

The canonical profile is a versioned, serializable description of host roots,
stack assertions, component inventory, commands, exclusions, and the evidence
that justifies each assertion. Multi-root repositories compose root profiles;
consumers do not infer a global stack from one marker. Profile validation uses
the WP1 registry vocabulary and support semantics rather than defining another
language, framework, capability, layer, or binding enum.

The flow is profiler → validated profile → adaptation and shared activation
resolution → routers/manifests → perimeter evidence. Adaptation merges with
host-owned files and cannot report success until the profile-derived perimeter
result is covered or visibly reports coverage gaps. A shared activation-decision API
returns active/inactive plus reasons, so every router and manifest projects the
same answer instead of maintaining its own predicate.

Class B/C consumers receive roots, component profiles, surface labels, and
ignore-first scopes from the profile. An undeclared component inventory is
empty, not seed-host-derived. Coverage is a join between a profile requirement
and installed/version-compatible executable evidence. Missing or invalid
evidence is a coverage gap, never a clean scan.

## Implementation

- [ ] AR-1: **Current-host oracle.** Record the current Python/Django
  adaptation result before changing profile or routing behavior.
- [ ] AR-2: **Host ownership oracle.** Pin merge/no-overwrite behavior for
  existing instruction and identity files, plus adaptation rerun idempotency.
- [ ] AR-3: **Registry oracle.** Pin rejection of unregistered identifiers at
  every profile/adaptation boundary.
- [ ] AR-4: **Class A oracle.** Inventory the already-landed Class A tests and
  retain their exact green command/output evidence.
- [ ] AR-5: **Route-sprawl oracle.** Capture ignore-first discovery, selected
  roots/extensions/markers, and clean-exemplar output before Class C changes.
- [ ] AR-6: **Honest-coverage oracle.** Pin missing, incompatible, uninstalled,
  and non-executable evidence as coverage gaps rather than zero findings.
- [ ] AR-7: **Exclusion oracle.** Pin accepted exclusions as reason-bearing and
  visible in human- and machine-readable output.
- [ ] AR-8: **Shared-routing oracle.** Characterize the current active-set
  answer from all four routing/manifest surfaces before consolidation.
- [ ] IM-1: **Profile contract.** Implement the versioned profile schema,
  deterministic serialization, validation, per-assertion evidence, and
  multi-root composition. <!-- spec:portable-host-profile-routing::IM-1 -->
- [ ] IM-2: **Five-host profiler.** Add Python/Django,
  TypeScript/Node/React, Rust, Go, and mixed-monorepo fixtures with good/bad
  profile oracles for roots, exclusions, commands, and evidence.
  <!-- spec:portable-host-profile-routing::IM-2 -->
- [ ] IM-3: **Profile-driven adaptation.** Make `project_adapt.py` consume the
  profile, reject non-registry IDs, preserve host-owned files, and prove
  idempotent reruns. <!-- spec:portable-host-profile-routing::IM-3 -->
- [ ] IM-4: **Mandatory perimeter integration.** Put the perimeter audit on
  the adaptation success path and add a bypass fixture that must fail.
  <!-- spec:portable-host-profile-routing::IM-4 -->
- [ ] IM-5: **Shared activation.** Implement one profile-derived activation
  decision with inclusion/exclusion reasons and migrate `/which-skill`,
  `/which-shape`, `/which-cleanup`, and manifests to it.
  <!-- spec:portable-host-profile-routing::IM-5 -->
- [ ] IM-6: **Honest perimeter.** Join requirements to installed,
  version-compatible executable evidence; retain visible reason-bearing
  exclusions; require whole-codebase routing to invoke it.
  <!-- spec:portable-host-profile-routing::IM-6 -->
- [ ] IM-7: **Profile-selected inventory.** Replace seed-host component and
  product-surface fallbacks with declared inventories and neutral labels;
  undeclared inventory is empty. <!-- spec:portable-host-profile-routing::IM-7 -->
- [ ] IM-8: **Ignore-first Class C migration.** Migrate folder-topology and
  frontend-contract enumeration to the shared scope and prove equivalence to
  the route-sprawl exemplar. <!-- spec:portable-host-profile-routing::IM-8 -->
- [ ] IM-9: **Conformance and regression.** Add good/bad/bypass/idempotency,
  cross-router agreement, negative Django-on-TypeScript, hard-coded-root search,
  Class A, and route-sprawl regression tests.
  <!-- spec:portable-host-profile-routing::IM-9 -->

## Learnings

### User-facing

- Pending implementation and fixture-based usability findings.

### Technical

- Pending implementation findings about profile composition, evidence joins,
  and routing convergence.

## Exceptions

- Framework detection establishes applicability; it does not itself prove
  executable support.
- Physical skill-layer installation, binding loading, and compatibility aliases
  belong to WP3.
- Parser-backed facts and adapters belong to WP4.
- No host-specific fallback or silent missing-evidence behavior is accepted.

---

## Known symbol inventory

No declared Python code root exceeded the scaffold inventory threshold. The
implementation inventory is therefore maintained by the AR/IM checklist and
the audited `code_roots` list above.
