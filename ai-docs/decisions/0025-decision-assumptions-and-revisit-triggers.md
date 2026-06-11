---
id: "0025"
namespace: core
title: Decisions record load-bearing assumptions and revisit triggers
status: proposed
date: 2026-06-09
provenance: "Promoted from a private host adaptation where this pattern is accepted and enforced; offered to core as a calibrated default."
assumes: ["the assumes/revisit_when fields are tolerated as optional extras, not yet required"]
revisit_when: ["decisions.py enforces required assumes/revisit_when on constraining decisions"]
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [ai-docs/decisions/, scripts/decisions.py]
embodied_by: ["script:scripts/decisions.py"]
tags: [decisions, hygiene, invalidation]
related_smell: null
related_pattern: null
---

# Decisions record load-bearing assumptions and revisit triggers

## Context

A decision constrains future work because of conditions that held when it was
made — and those conditions can later become false. When they do, the decision
should be re-opened, but nothing makes that obvious: the assumption was implicit,
so the rule silently outlives the rationale that justified it.

For example, a decision might mandate an inline error-handling guard at every
read site and deliberately decline to route those sites through a shared helper.
That choice is sound *only while* no standard shared helper exists. If such a
helper later becomes the norm, the convention should flip to "call the helper."
But without recording *that condition*, a future reader sees only the
inline-guard rule and treats it as timeless — applying it long after the premise
that justified it has dissolved.

A "how to migrate" note (where one exists) answers *how* to move off a decision
once it is superseded. It does not answer *when to start looking*: you migrate
only after judging a decision stale, and nothing tells you when to make that
call. That gap is the load-bearing assumption itself — the falsifiable condition
the decision rests on.

## Decision

A decision that constrains future work records its load-bearing assumption(s) as
two explicit, distinct fields:

- **`assumes:`** — the condition(s) the decision rests on, stated so they are
  *falsifiable* ("X holds because Y is true").
- **`revisit_when:`** — the observable change that should re-open the decision
  ("if Y stops being true, revisit"). A trigger, not a calendar date.

These fields are distinct from any "how to migrate" note: that note is the
*how*; `revisit_when` is the *when*.

**Cite something checkable.** A trigger names the evidence it can be evaluated
against — a file, a helper, a capability, a measurable threshold — so the
trigger can be *checked* rather than guessed. A trigger phrased as "revisit if
circumstances change" is not actionable; "revisit when a shared `X` helper
exists in the toolkit" is.

This applies to decision records under `ai-docs/decisions/`. Where a decision
has a genuine environmental dependency, include the fields; where a decision is
unconditional, omit them rather than inventing a vacuous trigger.

## Alternatives considered

- **Rely on prose or memory.** Let the rationale live in someone's head or in
  scattered summary text. Rejected: that is precisely what rots — not checkable,
  not co-located with the rule, gone after a context reset or a personnel change.
- **Use only a "how to migrate" note.** Rejected: it conflates *how to migrate*
  with *when to revisit*. Migration is the action you take after judging a
  decision stale; the trigger is what tells you to judge. Folding them hides the
  trigger inside how-to prose, where no detector can ever find it.
- **Build a full docs-to-code dependency graph now** that propagates
  invalidation automatically. Rejected as premature: `assumes`/`revisit_when`
  is the cheap, manual, per-decision instance of one edge of that graph (an
  upstream assumption → downstream decision dependency). Ship the manual edge
  now; let an automated graph harvest these fields later.

## Consequences

- **Easier:** invalidation becomes visible and checkable — when a fact about the
  environment changes, searching `revisit_when` across the decision corpus
  surfaces every decision that fact threatens.
- **Easier:** seeds a future docs-to-code dependency graph. Each
  `assumes`/`revisit_when` pair is a hand-authored upstream→downstream edge that
  tooling could later read to fire when a recorded assumption changes.
- **Harder:** authors must name a *falsifiable* trigger, not a vague "revisit
  periodically." This is the point — a trigger that cannot be observed cannot
  fire.
- **Discouraged:** recording a constraining decision while leaving a real
  environmental dependency implicit when one demonstrably exists.
- **Deferred:** making the decisions tooling *require* these fields. Today the
  fields are tolerated as optional extras; required-field enforcement waits until
  adoption is high enough not to generate noise.

## Verification

- `scripts/decisions.py rebuild` and `audit` still pass with the fields present —
  they are tolerated as optional extras today; required-field enforcement is an
  explicit deferred step, not a silent omission.
- At least one decision in `ai-docs/decisions/` carries `assumes:` +
  `revisit_when:` as a worked example, so the convention has a concrete referent.
- Searching the decision corpus for `revisit_when` returns every decision that
  declares an environmental dependency, confirming the triggers are co-located
  with the rules and machine-discoverable.
