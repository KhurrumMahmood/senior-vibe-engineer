---
id: "0030"
namespace: core
title: Co-locate a deliberately-coupled module trio as one canonical workflow unit
status: proposed
date: 2026-06-09
provenance: "Promoted from a private host adaptation where this pattern is accepted and enforced; offered to core as a calibrated default."
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [host:app/, .claude/docs/folder-organization.md]
tags: [cohesion, colocation, workflow]
related_smell: null
related_pattern: null
---

# Co-locate a deliberately-coupled module trio as one canonical workflow unit

## Context

A codebase usually organizes modules by layer or domain. Most modules slot cleanly into one
of those buckets. But occasionally a small set of modules is *deliberately coupled*: they
govern a single lifecycle and almost always change together. A canonical example is a
**status + workflow + checklist trio** governing one entity's lifecycle:

1. a **status** module — the transition rules and the set of valid states for the entity.
2. a **workflow** module — the state machine (steps, gates, predecessors) that drives
   transitions and calls into the status module.
3. a **checklist** module — the human-facing surface that reads the workflow and renders
   progress (a pill, a step list) on some screen.

When the dominant domain split has no obvious bucket for such a trio, the path of least
resistance is to scatter the modules by best-fit layer — status into one folder, workflow
into another, checklist into a third. This ADR exists because scattering a
deliberately-coupled trio is usually the wrong default.

The cohesion is load-bearing for two reasons. First, the modules **co-evolve**: a
transition-rule change in the status module almost always pairs with a step edit in the
workflow module and a display edit in the checklist module. Scattering them makes a
single-purpose lifecycle change touch three folders. Second, the trio together is the
**canonical writer** of the entity's lifecycle state. Scattering invites a new contributor —
who has no single obvious home for "lifecycle state" — to introduce a fourth, parallel write
path in whatever folder they happen to be working in, rather than routing through the trio.

## Decision

When a small set of modules (the illustrative case is a trio) is deliberately coupled and
co-evolves to govern one lifecycle, **co-locate them under a single cohesive home** named for
the entity or lifecycle they serve, rather than scattering them across the domain split.

The co-located unit is treated as **one canonical workflow**:

- The modules live together in one folder; imports between them stay local and a reader can
  follow the chain (status → workflow → checklist) without leaving the folder.
- The unit is the **canonical writer** of the entity's lifecycle state. New code that reads or
  writes that state MUST go through one of the co-located modules. Introducing a fourth,
  parallel write path elsewhere is disallowed.
- The folder has a **single named owner** responsible for the lifecycle, so co-evolution
  changes have one accountable home.

Co-location is the default; a future *split* of the unit requires re-justification —
specifically a written argument, backed by evidence (commit history showing single-purpose
changes that touch only one module of the set), that the co-evolution coupling has genuinely
weakened. Absent that evidence, the unit stays co-located.

## Alternatives considered

- **Scatter by best-fit layer.** Rejected: splits a deliberately-coupled set across folders,
  turning the dominant single-purpose lifecycle change into a multi-folder edit. Worse, it
  normalizes "this lifecycle state lives in several places," so the next contributor adding a
  state field has no obvious home and may introduce a parallel writer.
- **Wrap the set in a deeper sub-package** (e.g. a `lifecycle/` sub-folder nesting each
  module). Rejected at the trio scale: three same-domain modules sit at — not above — the usual
  threshold for earning a sub-package. Premature sub-packaging adds a navigation hop without
  earning it. (If the set grows well past three, revisit.)
- **Merge the set into a single file.** Rejected: each module is an independently navigable
  concern (transition rules, workflow steps, rendering surface — three different reader
  intents). Merging trades cohesion for an omnibus module a reader must skim end-to-end to find
  one concern.

## Consequences

**Easier:**
- Single-purpose lifecycle changes touch one folder; the co-evolution coupling already visible
  in commit history is mirrored by file location.
- "One obvious home for lifecycle-state writes" is structurally easy to enforce — any second
  write site is visibly anomalous.
- A new contributor who finds one module can follow imports to the rest of the unit without
  leaving the folder.

**Harder:**
- The co-located folder is named for an entity/lifecycle rather than a domain, so it does not
  perfectly mirror the dominant domain split — a reader scanning the top of the tree sees one
  folder that breaks the naming pattern. This minor inconsistency is the price of cohesion.
- The "canonical writer" claim is enforced by **review, not lint**: there is rarely a
  mechanical signature for "this writes lifecycle state," so reviewers must catch attempts to
  add a fourth writer.

**Now expected / now disallowed:**
- New code that reads or writes the entity's lifecycle state MUST go through one of the
  co-located modules.
- Introducing a lifecycle module (or a parallel writer) outside the unit is disallowed without
  a superseding ADR explaining why the cohesion has weakened.

## Verification

- **Top-of-file marker**: each module in the unit carries a comment declaring it part of the
  canonical lifecycle writer and citing this ADR, so the cohesion is discoverable from the
  source itself.
- **Single owner recorded**: the co-located folder names one owner (a code-owners file or a
  folder-level README), making the accountable party for co-evolution explicit.
- **Characterization test (best-effort)**: a test asserts that every write to the
  lifecycle-state field lives in a file within the unit's folder. This catches obvious scatter
  (direct field writes); logic that constructs a state value elsewhere and passes it in will
  not be caught, so it supplements rather than replaces review.
- **Doc backref**: the folder-organization doc records this unit as a deliberate exception to
  the domain split, with a pointer to this ADR, so the naming inconsistency is documented
  rather than surprising.
- **Split requires re-justification**: any later change that scatters the unit must link a
  superseding ADR presenting the commit-history evidence that co-evolution has weakened.
