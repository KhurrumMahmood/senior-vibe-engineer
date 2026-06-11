---
id: "0031"
namespace: core
title: A value-graph + next-step router is the toolkit's after-phase convergence gate
status: proposed
date: 2026-06-09
provenance: "Lifted from a sibling creative-tooling project where it was designed and validated on paper but never built — an unbuilt, unenforced design, not implemented or battle-tested here. Offered to core as the convergence primitive for its recurring decided-but-unbuilt / activity-not-outcome failure mode."
assumes: ["the toolkit's recurring failure is convergence — work fans out into more activity instead of closing on a named outcome — and no existing skill names, after a phase, the single next necessary move and an explicit stop condition"]
revisit_when: ["a third skill needs an after-phase next-step gate (a shared router earns extraction over each skill re-deriving 'what is the next necessary move?'), or reader/outcome telemetry exists in the toolkit to feed the router a judged-outcome signal instead of a self-assessed gate"]
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [ai-docs/decisions/]
tags: [convergence, routing, closure, next-step, stop-condition, primitive]
related_smell: null
related_pattern: null
---

# A value-graph + next-step router is the toolkit's after-phase convergence gate

## Context

This toolkit's recurring, documented failure mode is convergence failure:
work is *decided-but-unbuilt*, effort becomes *activity-not-outcome*, and a body
of work fans out into more interesting moves instead of closing on the outcome it
was meant to produce. The pattern is consistent across the suite: after a phase
(a refactor, a cleanup sweep, a design pass) the system does *the next available
interesting thing* rather than *the next necessary thing*, and nothing forces a
stop.

Several existing skills route *into* work — they pick which skill or operating
loop fits a task or situation at the *start*. What is missing is the symmetric
move at the *end*: after any phase, a pass that looks at the work-in-progress and
names (a) which part is weakest, (b) the single next necessary action, (c) the
condition under which work on this thread should stop, and (d) what explicitly
must *not* be done next. Without that pass, "are we done?" is answered by whoever
has momentum, and the cheap-but-shiny next move wins over the one that actually
advances the outcome.

A sibling creative-tooling project hit the identical wall and designed a
primitive for it — a **value-graph + next-step router**. That project can produce
abundant artifacts (drafts, reviews, generated boards, repair tickets) but, after
each one, still needs to decide *what the next best move is*. Its answer was to
model the work as a graph of distinct value dimensions that must all hold at once,
and to run a short router pass after every meaningful artifact that emits a fixed,
structured verdict: artifact status, strongest/weakest nodes, the single next
step, why that step, the success gate, the stop condition, and an explicit
do-not-do-next list. That design was validated on paper but **never built** — so
this ADR proposes the primitive on the strength of the diagnosis, not on a track
record. It is the convergence/closure machinery this toolkit's failure mode calls
for, generalized away from any one domain.

## Decision

Adopt a **value-graph + next-step router** as the toolkit's canonical
**after-phase convergence gate**: a short, structured pass that runs after a
meaningful phase of work and routes effort toward the next *necessary* move rather
than the next *available* one. It has two parts.

**1. The value graph.** The work-in-progress is modelled as a small set of
distinct **value dimensions** that must all hold for the work to be "done" —
named per domain, not fixed by this ADR. For an engineering change such
dimensions might be, illustratively, *correctness*, *the change is actually wired
in and reachable*, *tests/guards exist*, *no parallel write path was introduced*,
and *the outcome is demonstrated, not just asserted*. The graph's job is to make
"done" mean **every dimension holds at once**, so a phase that polished one
dimension while another stayed unproven is not mistaken for finished.

**2. The next-step router.** After a phase, a router pass reads the
work-in-progress plus the latest verdicts and the current weak dimensions, and
emits a fixed verdict. The shape (illustrative — the *fields* are the commitment,
not these example values):

```json
{
  "phase_status": "advance | repair | branch | park | discard",
  "strongest_nodes": ["correctness"],
  "weakest_nodes": ["wired-in-and-reachable"],
  "next_step": "the single next necessary action",
  "why_this_step": "names the weakest node this step closes",
  "stop_condition": "the observable condition under which work on this thread stops",
  "do_not_do_next": ["the tempting-but-not-necessary moves to refuse now"]
}
```

The five statuses give the router a small, total vocabulary for what to do with a
phase's output:

- **advance** — the phase passed its gate; move to the next-weakest node.
- **repair** — promising, but a specific node is weak; fix *that* before anything
  new.
- **branch** — multiple genuinely distinct routes exist and choosing now would
  discard value worth keeping; split deliberately rather than by accident.
- **park** — useful later, not necessary now; shelve it explicitly so it is
  neither lost nor pursued prematurely.
- **discard** — expensive or clever but does not advance any value node; stop.

The router's deliverable is exactly the four things the convergence failure mode
lacks: **weakest node**, **single next step**, **stop condition**, **do-not-do-next**.
Naming the stop condition and the do-not-do-next list is what makes work
*converge* — they are how the gate refuses fan-out, not just suggests a direction.

**Scope of this commitment.** This ADR commits to the router as the convergence
primitive and to the *shape* of its verdict. It does **not** commit to a
particular skill, file, schema version, or implementation; building it is
explicitly out of scope here and is gated on the `revisit_when` trigger. Three
**adjacent** primitives from the same sibling project are noted as future
context, **not** adopted here:

- a **decision-ledger** (rejected options + authority + dissent / disagree-and-commit)
  — a partial form of this already exists in this repo as the decisions corpus,
  so the router would *consult* recorded decisions rather than re-derive them;
- **reader / outcome telemetry** as a *judged-outcome* proxy — an external signal
  ("would a user actually accept this?") that could one day feed the router a real
  gate instead of a self-assessed one;
- **serendipity-capture** — a way to preserve an accidental good byproduct of a
  phase even when that phase failed its main job, so the router can park a nugget
  without salvaging the whole artifact.

These are listed so the router is understood in context; each would need its own
ADR before adoption.

## Alternatives considered

- **Keep relying on the existing forward routers.** Rejected: they select work at
  the *start* (which skill / which loop fits this task). None reads a
  work-in-progress *after* a phase to name the weakest node, the stop condition,
  and what not to do next. The convergence gap is precisely the symmetric,
  end-of-phase move they do not make.
- **Rely on a per-skill "definition of done" checklist.** Rejected as
  insufficient alone: a static checklist asserts the *dimensions* but does not
  **route** — it does not pick the single next necessary action among the unmet
  ones, does not emit a stop condition, and does not say what to refuse next. The
  router subsumes the checklist (the value graph *is* the dimensions) and adds the
  decision.
- **Adopt the full machinery now** — router *plus* decision-ledger *plus* outcome
  telemetry *plus* serendipity-capture — as one unit. Rejected as overreach: the
  convergence failure is addressed by the router alone; bundling four primitives
  into one commitment would import three under-justified dependencies. Ship the
  router as the load-bearing piece; let the adjacent primitives earn their own
  ADRs.
- **Build the router skill immediately as part of this ADR.** Rejected: the source
  is a validated *design*, not a tested implementation, and this repo is mid
  overclaim-cleanup. Recording the primitive and its verdict shape is the honest
  unit of commitment now; construction waits for a real pull (the `revisit_when`
  trigger) rather than being asserted as delivered.

## Consequences

- **Easier:** "are we done?" becomes a structured pass with a fixed output
  instead of a judgment call settled by momentum. The weakest node, the next
  necessary action, and the stop condition are named, so a phase can *converge*
  instead of fanning out.
- **Easier:** "done" is redefined as *every value node holds at once*, which makes
  the activity-not-outcome failure visible — a phase that advanced one node while
  another stayed unproven no longer reads as finished.
- **Easier:** the `do-not-do-next` list gives an explicit, recorded basis for
  refusing a tempting-but-unnecessary move, which is the behaviour the convergence
  failure mode most needs and the hardest to enforce by good intentions.
- **Harder:** the value dimensions must be *named per domain*. A router is only as
  honest as its graph; a graph that omits a real dimension will pass work that is
  not actually done. Choosing the dimensions is deliberate work, not a default.
- **Harder / honest limit:** until outcome telemetry exists, the gate is
  **self-assessed** — the same actor judges and is judged. That is a weaker check
  than an external verdict and is the named reason outcome-telemetry is flagged as
  a future feed.
- **Deferred:** the implementation itself — a skill/file, a concrete schema, and
  any enforcement. This ADR commits to the primitive and the verdict shape; the
  build waits on the `revisit_when` trigger so it is pulled by real demand rather
  than asserted prematurely.
- **Discouraged:** treating a phase as finished without naming its weakest node
  and stop condition once this primitive is in use — i.e. closing on momentum
  rather than on a gate.

## Verification

This ADR is **proposed** and records a design; there is **no implementation to
verify**. The checks below are the *acceptance criteria for a future build*, plus
the honesty checks that apply to the ADR as written today.

- **Future — verdict completeness:** any built router emits all of
  `phase_status`, `weakest_nodes`, `next_step`, `stop_condition`, and
  `do_not_do_next` for every phase; a verdict missing the stop condition or the
  do-not-do-next list does not count as a convergence gate.
- **Future — graph is explicit:** the value dimensions for a given workflow are
  written down (not implicit), so "done = all nodes hold" can actually be checked
  against a named set.
- **Future — outcome feed:** when outcome/reader telemetry exists in the toolkit,
  the router consumes it as the success-gate signal instead of a self-assessed
  one (this is one arm of `revisit_when`).
- **Today — honesty of provenance:** `provenance` states the source is a validated
  but **unbuilt** design and that nothing here is implemented or enforced;
  `status: proposed` matches that. The claim and the status do not exceed the
  evidence.
- **Today — host-reference guard stays green:** this ADR names no private host or
  proprietary identifier; `scripts/lint/no_host_references.py` passes over it. The
  router is framed as a general engineering primitive and the source is cited only
  generically as a sibling creative-tooling project.
