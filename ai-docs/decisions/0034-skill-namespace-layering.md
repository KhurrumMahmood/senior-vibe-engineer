---
id: "0034"
namespace: core
title: Skills are namespaced by coupling layer and domain (core / lang / framework / domain)
status: accepted
date: 2026-06-11
deciders: [khurrum, claude-code]
assumes: ["what transfers across host projects is the loop, the scanner toolbox, and the process skills — not 72 individually named flat skills; the flat namespace hides which skills a given host can actually use", "the named layer set and example folders are a rendering of TODAY'S corpus (Python/Django-derived, one domain family on the horizon) — the durable commitment is the placement discipline, not this specific tree"]
revisit_when: ["the harness's skill discovery cannot express the layering even via name prefixes or packaging (then the taxonomy lives in frontmatter + manifest only)", "a second host adoption or a corpus shift shows the layer boundaries were drawn in the wrong place — the tree is re-derived from the corpus then, not defended", "periodically at catalog-review time: does the current tree still mirror the actual coupling profile?"]
supersedes: []
superseded_by: null
applies_to: [.claude/skills/]
embodied_by: ["pending:ai-docs/plans/shareable-core-reorganization.md"]
tags: [skills, namespace, portability, coupling, domain, structure]
related_smell: null
related_pattern: null
---

# Skills are namespaced by coupling layer and domain

## Context

The skill catalog is a flat namespace of ~72 names. That flatness conflates
three orthogonal axes:

- **job** (find- / extract- / plan- / which-) — already encoded in naming;
- **coupling** (universal → language-bound → framework-bound → host-bound) —
  recorded only in `language:`/`framework:` frontmatter, invisible in
  structure;
- **domain** (code maintenance, frontend, product topology, AI-systems
  engineering, the ecosystem itself) — not encoded anywhere.

The measured coupling profile: 32 skills declare `python|django`, 14
`python|any`, 6 `any|django`, 20 `any|any` — but the declared coupling
overstates the *conceptual* coupling. Most "Django skills" decompose into a
universal concept plus a framework idiom (stringly-state→enum is universal;
TextChoices is the Django binding). Only a small residue is irreducibly
framework-native. Meanwhile a host project has no structural way to install
"just what applies to me," and a genuinely distinct skill family (e.g.
AI-harness engineering) has no home that isn't the maintenance namespace.

ADR 0032 already established the concept/adapter split at the *detector
implementation* level. This ADR lifts the same move to the *catalog* level.

## Decision

**1. Four-layer namespace plus host overlay.** Every skill belongs to
exactly one layer:

```
core/                universal process + judgment skills, and concept
                     skills whose body is framework-neutral
lang/<language>/     irreducibly language-bound machinery (e.g. Python
                     AST tooling internals)
framework/<name>/    irreducibly framework-native skills (e.g. a
                     component-system extractor with no analog elsewhere)
domain/<area>/       genuinely distinct skill families (ai-systems,
                     frontend, ...) that are not general code maintenance
(host overlay)       host-project adaptations — live in the host repo,
                     never shipped with core
```

**2. Concept + binding is the default shape for framework-flavored skills.**
A skill whose *concept* generalizes but whose *idiom* is framework-specific
lives in `core/` with a framework-neutral body, plus thin
`bindings/<framework>.md` files holding the idiom and the detector-adapter
pointer. Bindings are idiom sheets, not skill clones — a binding that
restates the procedure is drift. Only skills whose concept itself has no
cross-framework analog go under `framework/<name>/`.

**3. Contract boundaries earn structure at N=1.** ADR 0006's ≥3-siblings
rule governs cohesion grouping; it does not apply here. A coupling layer is
a *shipping contract* ("what installs into whom"), and a contract boundary
deserves its folder even with one member — `framework/django/` with a
single irreducibly-Django skill is correct, not premature. Domain folders,
by contrast, ARE cohesion groupings and DO follow the ≥3 rule
(`domain/ai-systems/` is created when three skills exist for it, not
speculatively).

**4. The layers are load-bearing.** The activation manifest
(`.engineering/manifest.json`) and the routing skills filter by the host's
active layers — a TypeScript host installs `core/` + `lang/typescript/` and
the Django lane does not exist for it. `find-perimeter-gaps` audits that
the installed layers cover the host's actual (code root × language)
perimeter. A layer that routing ignores is decoration; this ADR commits to
layers the routers respect.

**5. Mechanics are subordinate to taxonomy.** If the harness's skill
discovery cannot walk nested directories, the layering is expressed through
name prefixes or plugin packaging instead — the *taxonomy and placement
rule* are the commitment of this ADR; the directory mechanics are verified
at migration time by the reorganization plan.

**6. Scope and durability — what this ADR is NOT.** This ADR governs the
**toolkit's own skill catalog only**. It is not a folder standard for host
projects: a host's code organization stays governed by its own conventions
(ADR 0006 / `folder-organization.md` territory, advisory and
host-calibrated), and nothing in this decision authorizes restructuring a
host's directories. Within the toolkit, the *binding* commitment is the
placement discipline — coupling declared honestly, structure mirroring the
shipping contract, concept+binding over forking, N=1 for contract
boundaries. The *specific tree* (the layer names, the example folders) is
the current rendering of that discipline over today's corpus; it is
expected to be re-derived as the corpus changes, the same way the
maintenance loop periodically re-derives any folder topology rather than
freezing one. A future catalog whose coupling profile looks different
should get a different tree under the same rule — without superseding this
ADR.

**Incidentally-coupled skills are mislabeled, not moved.** A skill whose
procedure is universal but whose examples are Django-flavored (most plan-*
skills) is de-flavored in place in `core/` — examples move to a binding or
an appendix. Relocating it to `framework/django/` would launder example
contamination into a false coupling claim.

## Alternatives considered

- **Keep the flat namespace, rely on frontmatter.** Rejected: frontmatter
  is invisible at browse time, unenforceable at install time, and the
  catalog's discoverability problem (72 undifferentiated names) stays.
- **Move every `python|django`-declared skill into `framework/django/`.**
  Rejected: the declared coupling overstates conceptual coupling; this
  would freeze ~32 generalizable concepts behind a framework label and
  forfeit the concept+binding generalization path.
- **One folder per framework with full skill copies (fork-per-stack).**
  Rejected: recreates the duplication smell at catalog scale; every
  procedural fix would need N edits.
- **Domain folders at N=1 too.** Rejected: domains are cohesion groupings,
  not shipping contracts; speculative domain folders are exactly what ADR
  0006 exists to prevent.

## Consequences

- **Easier:** a host installs only the layers that apply; the catalog a
  user browses shrinks to what is real for them; "is this skill safe for my
  stack" becomes a placement fact instead of frontmatter archaeology.
- **Easier:** porting to a new framework becomes additive (write a binding,
  write an adapter) instead of forking skills.
- **Easier:** new skill intake (`/plan-skill`) gains a placement question
  with a deterministic answer: which layer, and if framework-flavored,
  concept+binding or native?
- **Harder:** the migration itself — every skill needs a placement call,
  incidentally-coupled skills need de-flavoring, and routing/manifest/
  perimeter machinery must learn layers. Tracked by the reorganization
  plan named in `embodied_by`.
- **Harder:** cross-references (which-* routers, skill-catalog, contracts
  `_index`) must survive the moves; ADR 0024's rename-completeness rule and
  ADR 0028's path-verification rule apply to the migration commits.
- **Disallowed:** adding a new framework-flavored skill as a flat clone of
  a core concept; the binding mechanism is the only sanctioned shape.

## Verification

- The reorganization plan (`embodied_by` pending ref) executes the
  migration; on completion this ADR's `embodied_by` is updated to the
  doctrine/contract artifacts that encode placement (and the pending ref is
  removed) — the ADR 0033 audit keeps that honest.
- Post-migration: no skill under `core/` names a framework outside its
  `bindings/`; `scripts/lint/no_host_references.py` stays green; a
  placement rule exists in the skill-authoring doctrine and `/plan-skill`
  asks the layer question.
- `find-perimeter-gaps` + the activation manifest demonstrate layer-aware
  install on at least one non-Django fixture before the migration is called
  done.
