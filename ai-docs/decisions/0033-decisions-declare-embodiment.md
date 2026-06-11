---
id: "0033"
namespace: core
title: Accepted decisions declare their embodiment (embodied_by)
status: accepted
date: 2026-06-11
deciders: [khurrum, claude-code]
assumes: ["the registry's recurring failure is decided-but-unbuilt: decisions flow INTO ADRs and stop, instead of flowing THROUGH them into an executable surface (skill / lint / script / hook)"]
revisit_when: ["the embodied_by existence checks produce more rename-churn noise than drift signal (then weaken to advisory), or a registry of embodiment kinds beyond skill/lint/script/hook/doctrine/contract/pending is needed"]
supersedes: []
superseded_by: null
applies_to: [ai-docs/decisions/, scripts/decisions.py]
embodied_by: ["script:scripts/decisions.py"]
tags: [decisions, embodiment, convergence, guardrail, provenance]
related_smell: null
related_pattern: null
---

# Accepted decisions declare their embodiment (embodied_by)

## Context

The skill contracts already enforce one direction of decision↔artifact
linkage: a contract's `embodies_decisions.adr` names an ADR only when the
bidirectional signal holds (the skill cites the ADR AND the ADR names the
skill back). But the ADR side has no field to name anything back, so the
"AND" half of that rule has nothing machine-checkable to bind to.

The cost is the registry's documented failure mode: **decided-but-unbuilt**.
The history is consistent — every accepted ADR to date was implemented, and
the healthy pattern (ADR and its artifact landing together: 0020→/orient,
0023→/which-cleanup, 0024→/rename-concept, 0025→decisions.py) already
exists. But nothing *enforces* it, and proposed ADRs that are really
skill/lint backlog items wearing ADR clothes accumulate without any surface
saying "this is waiting to be built."

In the wider agent-tooling world the dominant currency is the skill
(repeated behavior → skill/hook/rule-line), and ADRs are rare. The two are
not substitutes: a skill is a *procedure* and is bad at recording why and
what was rejected; an ADR is a *constraint with rationale* and does nothing
unless something downstream embodies it. The relationship to encode:
**skills are the executable surface; ADRs are the provenance layer behind
the load-bearing ones; an ADR without an embodiment is a backlog item
mislabeled as a decision.**

## Decision

ADR frontmatter gains an optional, typed `embodied_by:` list. Each entry is
`<kind>:<ref>` with kinds:

- `skill:<name>` — a `.claude/skills/<name>/` skill realizes the decision
- `lint:<rule>` — a `scripts/lint/<rule>.py` rule enforces it
- `script:<path>` — a runtime script implements it
- `hook:<id>` — a harness hook activates it (existence advisory — hooks may
  live in host settings this repo cannot see)
- `doctrine:<path>` — a docs file is the deliberate, prose-only embodiment
  (allowed, but the choice to stop at prose should be defensible)
- `contract:<path>` — a contract/schema file carries it
- `pending:<ref>` — the decision is accepted but the build is tracked
  elsewhere (a plan file, a spec, an issue). `pending:` entries ARE the
  decided-but-unbuilt backlog, greppable as one list.

**Audit rule (hard):** an `accepted` ADR with an empty or missing
`embodied_by` is drift — name the executable surface, the deliberate
doctrine-only choice, or a `pending:` ref. `proposed` ADRs may leave it
empty (that is precisely the not-yet-built state) or pre-fill it when the
embodiment already exists.

**Link-check rule:** every entry must parse as `kind:ref` with a known
kind; `skill:`/`lint:`/`script:`/`doctrine:`/`contract:` refs must resolve
on disk (anchors after `#` ignored); `pending:` refs are listed as an
advisory "decided-but-unbuilt" backlog rather than failed.

**Skill-side footer convention:** a skill (or lint/script header) created
as the embodiment of an ADR carries a one-line footer:

> Source decision: `core:<slug>` (ADR NNNN) — provenance, not required
> reading; do not load the ADR during execution.

The footer is for the human/reviewer; execution-time behavior must be fully
specified in the artifact itself, so the agent never needs to navigate to
the ADR mid-task. Together with the contract's `embodies_decisions.adr`,
this completes the bidirectional link the contract schema already demands.

**Routing rule for new decisions** (which embodiment a decision should get):

- a procedure with a trigger and judgment steps → **skill**
- a checkable always/never invariant → **lint / test / hook**
- a vocabulary, threshold, or constraint other artifacts consume →
  **doctrine / contract**
- not built yet but accepted → **pending:** with the tracking ref

## Alternatives considered

- **Keep the mapping in contracts only.** Rejected: one-directional; the
  contract schema's own rule demands the ADR name the artifact back, and a
  prose mention in the ADR body is not machine-checkable.
- **A separate decision→artifact registry file.** Rejected: a parallel
  writer for facts the ADR and the contract already own — the
  format-equivalence smell this registry exists to catch.
- **Require embodiment at acceptance (no `pending:` kind).** Rejected: it
  would forbid accepting a decision before its build lands, recreating ADR
  0031's dilemma in reverse and incentivizing either premature builds or
  eternally-proposed status.
- **Make the accepted-without-embodiment check advisory.** Rejected: the
  decided-but-unbuilt failure mode is exactly the one good intentions have
  not fixed; an advisory note is the layer that already failed.

## Consequences

- **Easier:** decided-but-unbuilt becomes mechanically visible — `grep
  pending:` over decisions is the build backlog, and the audit refuses an
  accepted ADR that names nothing at all.
- **Easier:** the bidirectional skill↔ADR link is now checkable from both
  ends; `find-skill-intent-drift` and the contracts gain a counterpart.
- **Harder:** renames must update `embodied_by` refs or link-check fails —
  `/rename-concept` and refactor closeouts must treat decision refs as a
  rename surface (this is consistent with ADR 0024's completeness rule).
- **Harder (small):** authoring overhead of one frontmatter line per ADR;
  backfill of the existing accepted set ships with this ADR.
- **Honest limit:** `embodied_by` asserts that an artifact exists, not that
  it is sufficient. Whether a lint actually enforces the full decision
  remains a judgment (and a candidate for the contract's dogfood evidence).

## Verification

- `scripts/decisions.py audit` flags an accepted ADR with empty
  `embodied_by`; `link-check` flags unknown kinds and unresolvable refs and
  lists `pending:` refs as the advisory backlog. Covered by tests in
  `tests/test_decisions.py`.
- All previously-accepted ADRs (0001, 0002, 0004, 0005, 0013, 0021, 0032)
  are backfilled in the same commit; the pre-commit decisions-audit hook
  stays green, proving the gate and the backfill agree.
- This ADR's own `embodied_by` names `script:scripts/decisions.py` — the
  decision is self-embodying and the link resolves.
