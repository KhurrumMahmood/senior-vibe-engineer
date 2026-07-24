# Vision — the state this ecosystem transforms a project into

`README.md` says what the skills *do*. The mantra in `.claude/CLAUDE.md`
("continuously convert hidden structure into explicit structure, and one-off
discoveries into repeatable guardrails") says the *engine*. This document says
the **destination**: the end-state a codebase should converge toward once this
ecosystem has done its work.

Scope here is deliberately the **maintainability / shape side**. The broader
intent — transforming the experience of AI development ("vibe coding") away
from "got it done" code that quietly erodes system health — is the surrounding
frame (see `.claude/docs/quality-coordination-kernel.md`); this doc is the
concrete, measurable slice of it.

## The destination

AI-generated code drifts toward duplication and accreted, intent-obscuring
structure. The target is the opposite. A project the ecosystem has worked on
should converge toward a state where:

1. **The real ideas are explicit and de-duplicated (DRY).** Every meaningful
   capability the system provides is named once, its value stated, and its
   duplicates collapsed. You can enumerate what the project actually *does* and
   *why* — the ideas, not just the files.

2. **The right ideas are standards.** Ideas that should always hold for a given
   job or situation are promoted to standards and *activated* automatically
   (lint / test / guard / skill), not re-decided each time or left to memory.
   Activation is keyed to job, situation, and stakes — not effort or
   recollection (lifecycle × stakes; ADR 0020, `orient`, `which-shape`).

3. **The shape is the ideal shape (SOLID).** Folder structure and file
   boundaries follow the ideas and the jobs, with minimal surprise, so the
   structure *mirrors the intent* rather than the order code was written in
   (`folder-organization.md` / ADR 0006; `propose-boundary`,
   `propose-folder-reorganization`).

4. **It is instantly legible — to humans and to AI agents.** A new developer,
   or a fresh agent, can land on the project and grasp what is going on almost
   immediately, because the shape, the names, and the orientation docs carry the
   intent. Developer experience and orientation are first-class *outcomes*, not
   afterthoughts. The consumer's need (onboarding vs. grounding vs. changing)
   shapes what documentation is produced.

5. **Comprehension is maintained, not one-shot.** Documentation tracks the code
   under one-way docs→code authority; drift is detected and repaired, so
   legibility does not rot back to opacity.

A one-line test: **could a competent newcomer (human or AI) jump on this
project and almost instantly understand what it does, why it is shaped this way,
and where to make a change safely?**

## How the ecosystem gets a project there

The maintenance loop is the engine; the stages map onto the destination:

- **Extract the real ideas + their value** — the idea ledger,
  `extract-existing-ideas`, `query-patterns` (→ destination 1).
- **Decide which ideas are standards** — `harvest-learnings`,
  `find-standard-gaps`, lifecycle × stakes activation (→ destination 2).
- **Re-compose for DRY / SOLID** — the `find-*-duplication` family,
  `propose-boundary`, `unify-shadows`, `refactor-subsystem`, `triage-debt`
  (→ destinations 1, 3).
- **Arrive at the ideal shape** — `propose-folder-reorganization`,
  `find-folder-topology-drift`, and the still-unbuilt `audit-project-shape` /
  `map-project` / `propose-architecture` intakes (→ destination 3).
- **Make it legible + keep it legible** — `orient`, `map-subsystem`,
  `ONBOARDING.md`, plus the docs-drift detectors (→ destinations 4, 5).

## Status

- This is the maintainability slice, articulated in the 2026-05-25 design
  dialogue. The constructive / greenfield and outward-facing (product UX)
  halves are tracked separately in the idea ledger.
- **The ecosystem must embody this destination in its own structure** — that is
  the strongest test of whether the skills work. The 2026-07 productization pass
  established the three-router installation, bounded 13-language support, and a
  measured read-only batching journey. The remaining vision gaps are evaluated
  through the idea ledger and explicit backlogs rather than an obsolete sandbox
  status note.
