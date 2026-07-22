---
id: "0022"
namespace: core
title: "Generated-detector lifecycle: synthesize -> propose -> accept -> freeze -> gate"
status: proposed
date: 2026-05-22
deciders: []
supersedes: []
superseded_by: null
applies_to: [".claude/skills/find-frontend-duplication/scripts/cotton_inventory.py", ".claude/skills/find-standard-gaps/scripts/scan_coverage.py", ".claude/skills/orient/"]
tags: [detectors, lifecycle, synthesis, gating, enforcement, coverage-ratchet, freeze, crystallization, advisory, generated-vs-curated]
related_smell: null
related_pattern: null
---

# Generated-detector lifecycle: synthesize → propose → accept → freeze → gate

## Context

Code-quality detectors must fit each host's conventions. The trigger is concrete:
`find-frontend-duplication`'s cotton scanner hardcodes one host's layout
(`app/_components/cotton`, `templates/`, `static/js/`). A portable, open-source
toolkit can't assume that — different hosts put primitives in different places,
and some use component systems we have never seen. Even with a single internal
host today, open-sourcing means *other* adopters bring layouts and stacks we
didn't anticipate.

That yields two sourcing paths for a detector:

- **Curated / parameterized** — a maintained detector whose host-specific knobs
  (the cotton root, the template/js dirs) are read from a committed convention
  descriptor (ADR 0021). Stable, reviewed, deterministic.
- **Generated / synthesized** — for the long tail: the system discovers a host
  need and *fits* a candidate detector to it (the suspect/discover end — the same
  generative move as field-extraction's agent-derived targets, where the agent
  sets the target shape from samples rather than from hardcoded prose).

The tension: a freshly *generated* detector hasn't been reviewed and may be
non-deterministic, so it can't be trusted as a hard gate the instant it is born.
But the opposite blanket rule — "generated detectors are advisory forever" —
strands real value: a developer can reasonably look at a well-evidenced generated
rule and decide to enforce it. And the rest of the ecosystem is already
**propose-not-impose**: inference proposes a project-state transition and the human
disposes (ADR 0020); `/orient` confirms; harvest proposes standards. Gating should
follow the same grain — *the developer chooses, and the system makes its case* —
not a provenance-based ban.

## Decision

A detector progresses through a lifecycle, and **enforcement is gated on human
acceptance, not on provenance**:

1. **Synthesize / select.** Discover the host need (this converges with
   `/orient`'s host introspection) and produce a candidate detector — generated
   for the long tail, or selected + parameterized from the curated library against
   the host's convention descriptor.
2. **Run advisory + assemble an evidence packet.** The candidate runs
   **read-only** and the system builds the *case for it*: hit count, estimated
   false-positive rate, runtime cost, and — the key empirical move — a
   **git-history replay**: "would have fired on these N past commits; fired zero
   times across the last M unrelated ones." Evidence, not "trust me."
3. **Propose an enforcement level.** The system **advocates** — it recommends a
   specific rung on the *existing coverage-ratchet dial* (changed-files **hard
   gate** / registry-wide **advisory** `::warning::` / **off**), justified by the
   packet.
4. **Developer accepts** (or declines, or picks a different rung). The decision —
   rung + the detector it applies to — is recorded in `.engineering/` (committed
   zone, ADR 0021). This is the authorization step; nothing gates without it.
5. **Freeze.** On acceptance the detector is **snapshotted: versioned, pinned,
   deterministic, re-runnable** — never re-synthesized per run. Freeze is what
   makes a *generated* detector safe to gate on: without it the gate would
   silently change shape run-to-run and flake.
6. **Gate.** The frozen artifact enforces at the accepted rung.

**Invariant:** anything that gates is **frozen + deterministic**, and
**acceptance + freeze — not provenance — is the toll to cross into gating.** A
frozen generated detector and a curated one are equivalent at the gate;
"generated" only changes the path *to* acceptance (it must show its evidence), not
what enforcement requires. Determinism is *necessary* (freeze) but it is not the
*authorization* — the developer's accept, informed by the packet, is.

**Crystallization (the far end).** A frozen detector that recurs and proves out
across hosts is a candidate to **graduate** from per-host generated artifact into
a parameterized entry in the curated library — the harvest / ledger → pattern →
skill arc. Graduation is *earned by cross-host evidence*, not pre-built; this is
the discover → guard pipeline closing the loop (generative synthesis at the
suspect end, a crystallized reusable detector at the guard end).

## Alternatives considered

- **Generated detectors are advisory-only, forever.** Rejected (this was an
  earlier framing here): it strands real value. A developer can reasonably enforce
  a well-evidenced generated rule; the system's job is to make the case, not to
  forbid the choice.
- **Generated detectors may auto-gate when confidence is high.** Rejected: no human
  authorization, and re-synthesis makes the gate non-deterministic and flaky.
  Acceptance + freeze is the safeguard — confidence informs the *proposal*, it
  doesn't replace the *accept*.
- **Pre-build parameterized detectors for every anticipated convention.** Rejected
  as speculative: you can't enumerate every host's stack. Build curated for what's
  seen, generate for the tail, crystallize what proves out.
- **Trust-by-determinism alone** (gate as soon as a detector is deterministic).
  Superseded by trust-by-acceptance: determinism via freeze is *necessary but not
  sufficient*; the authorization is the developer's evidence-backed choice. This
  refines, not contradicts, ADR 0019's deterministic trust boundary — the boundary
  still requires determinism; it now *also* requires an explicit accept before
  enforcing.

## Consequences

- **Easier:** generated detectors gain a safe, explicit path to enforcement; the
  gate/advisory dial is recorded and auditable; the case for a gate is empirical
  (history replay) rather than asserted; curated and generated detectors converge
  at one gate definition; reuses the coverage-ratchet rungs already in
  `scan_coverage.py` instead of inventing a new enforcement vocabulary.
- **Harder:** must build the evidence-packet + git-history-replay machinery, the
  freeze/versioning step, and the acceptance-record store (lands in
  `.engineering/`, ADR 0021); crystallization criteria (how much cross-host
  evidence earns graduation) need tuning.
- **First instance:** the cotton scanners. The **curated half** is concrete and
  near-term — parameterize them against a committed convention descriptor
  (django-cotton's `templates/cotton/` as the default, with a host override),
  closing the hardcoded-layout / argument-hint gaps the
  SKILL.md already advertises. The **generative half** handles the next host whose
  component system we haven't seen.

## Verification

- A candidate detector can run advisory and emit an evidence packet including a
  git-history replay (past-commit hits + unrelated-commit quiet record).
- An acceptance decision (rung + frozen-detector reference) persists in
  `.engineering/` and drives enforcement; nothing gates without one.
- A frozen detector is byte-stable across runs (no re-synthesis); a gate built on
  it is reproducible.
- **Proposed** until: one detector traverses synthesize → propose → accept →
  freeze → gate end-to-end — the cotton parameterization as the curated half, and
  one generated candidate carried through acceptance + freeze as the generative
  half. Pairs with ADR 0021 (`.engineering/` stores the decisions + frozen
  detectors), ADR 0020 (enforcement rungs = the lifecycle × stakes activation
  dial; `/orient` = the discovery pass), and ADR 0019 (the determinism half of the
  trust boundary this refines).
