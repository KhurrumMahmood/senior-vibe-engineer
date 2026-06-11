---
id: 0004
namespace: core
title: Parallel writers of the same output shape route through a shared helper
status: accepted
date: 2026-05-03
assumes: ["no standard shared helper exists for the divergent shape yet"]
revisit_when: ["a shared helper for the shape becomes the project norm"]
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [host:app/]
embodied_by: ["doctrine:.claude/docs/architectural-smells.md"]
tags: [format-equivalence-gap, refactor, structural-rule, share-utilities]
related_smell: format-equivalence-gap
related_pattern: parallel-writers-shared-producer
---

# Parallel writers of the same output shape route through a shared helper

## Context

Recurring duplication clusters evidence the same shape: two or more
code paths producing conceptually-equivalent output (same model rows,
same dict shape, same export columns), with one path silently
divergent on a critical guard or shape detail. Typical incidents:

- Triplicated queryset builders where one variant drops a brand-filter
  clause silently.
- CSV vs. XLSX writers for the same export, where one spreads
  serialization kwargs differently and loses a column.
- Two case-handling variants of the same list view (`__iexact` vs
  `__in`) producing different result sets on the same input.
- Validation that fires in one ingestion path and not its sibling,
  silently storing malformed values.
- Two builders that walk the same source tuple with the same branching
  but different separators / dedupe / source ordering.

The fix shape is identical in every case: extract a canonical
producer (helper / queryset builder / iterator generator) that holds
the guard, then route every parallel writer through it.

A narrow AST lint can guard a single recurring output shape — but
each new format-equivalence-gap cluster involves a *different* output
shape (different model rows, different export columns, different
query kwargs). A single AST lint cannot generalize across all
clusters; a structural convention can.

This ADR records the structural convention so the rule survives
beyond any specific lint.

## Decision

**When two or more code paths produce conceptually-equivalent output
on shared inputs (same model rows, same dict shape, same export
columns), they MUST route the output construction through a single
canonical producer (helper, service method, queryset builder).**

The discriminator: would a characterization test be able to assert
that, on the same input, both paths produce identical output? If yes,
the paths are parallel writers of the same output shape and the rule
applies. If no — because the bodies are intentionally different
(transport adapters, library-specific ports, cross-DB connectors with
different driver semantics) — the paths must instead carry sibling
pointers in their docstrings naming the divergence and its load-bearing
rationale (the `keep_separate_document_why` shape).

The interface-depth gate (`.claude/skills/_common/interface-depth.md`)
remains the test for whether extraction is correct — a helper that
fails the deletion / caller-knowledge-removed / adapter-reality checks
is the wrong abstraction even when the rule says one is required. In
that case the doc-why escape hatch applies.

## Alternatives considered

- **AST lint per output shape.** Narrow per-shape lints work, but only
  for one shape. Rejected as a general solution because each new
  format-equivalence-gap cluster would need a new AST rule (different
  model, different keys, different guard). Lint count grows linearly
  with shapes; structural conventions don't.

- **Code review enforcement only.** Rejected. Recurrence proves the
  convention isn't sticking on its own. Silent divergence on a guard
  hides in subtle key/value differences that pass casual review.

- **Mandatory characterization tests at every parallel writer.**
  Rejected as the primary mechanism. Too heavy: most parallel writers
  are co-located in the same service file and are obvious refactor
  targets without a paired test. Characterization tests remain the
  right tool for proving the shared producer is behavior-preserving
  during the actual refactor (per `/fix-workflow` Step 2 playbooks),
  not for pre-emptively guarding every shape.

- **No enforcement (status quo).** Rejected. The growth pattern of
  these clusters demonstrates the shape is recurrent, not exceptional.

## Consequences

**Easier:**
- New writers naturally find the canonical producer when grep-ing for
  the output shape they want to emit.
- `/find-semantic-duplication` clusters that flag this shape have a
  single resolution path: extract or document.
- The `/fix-workflow` `share_utilities` triage gate becomes binary —
  passes interface-depth → extract; fails → doc-why.
- Future `/prevent-regression` proposals that try to lint a specific
  shape can cite this ADR as their motivating context.

**Harder:**
- More upfront design when adding a second writer for an existing
  output shape — the author must locate or extract the canonical
  producer rather than copy-paste-modify.
- `keep_separate_document_why` annotations require care: a sibling
  pointer that goes stale is worse than no pointer at all (it claims
  a divergence rationale that no longer holds).

**Now expected / now disallowed:**
- **Disallowed**: adding a second code path that builds the same
  output shape (model defaults, export columns, export row dicts,
  cache-freshness gates, queryset filters) without routing through
  the canonical producer in the same module.
- **Expected**: any new producer of an existing output shape either
  (a) calls the canonical helper, or (b) carries a docstring sibling
  pointer naming the canonical implementation and the load-bearing
  divergence rationale.
- **Reviewers and AI agents**: when reviewing a diff that adds a new
  producer of an existing output shape, ask "is there a canonical
  producer in this module?" before approving. If the answer is yes
  and the new code re-spreads the construction inline, request a
  refactor.

## Verification

- **Tooling**:
  - Per-shape AST lints land via `/prevent-regression cluster:<id>`
    after a recurring instance justifies them. One rule per recurring
    output shape, not one rule for the whole convention.
  - No general structural lint exists for this rule (the same
    "structural rules without lints" category as "Job identity is an
    explicit FK"). Enforcement relies on review + agent skills + per-
    shape lints landing reactively.

- **Doc backrefs (landed in this ADR's commit)**:
  - **`architectural-smells.md`**: smell 5 "Format-equivalence gap"
    inserted between Layer violation and Product-topology drift (the
    latter renumbered to smell 6). Carries `**Decided in:** 0004
    (parallel writers shared helper).` and a paired cross-pattern
    bullet "Parallel writers route through a shared producer".
  - **`canonical-patterns.md` "Structural rules without lints"
    section**: new bullet "Parallel writers route through a shared
    producer", sibling of "Job identity is an explicit FK", carrying
    `-- Decided in: 0004` backref.

- **Existing artifacts**: Per-cluster learnings live in
  `reports/duplication/learnings.md` (host-project specific). Each
  cluster entry records the canonical producer that resolved it and
  the divergence-rationale doc pointer for cases that stayed apart.
