---
id: "0017"
title: Staged boundary rearchitecting — when to extract, when to phase, when to refuse phasing
status: proposed
date: 2026-05-14
deciders: []
supersedes: []
superseded_by: null
applies_to:
  - .claude/skills/propose-boundary/
  - .claude/skills/refactor-subsystem/
  - .claude/docs/architectural-smells.md
tags: [refactor, boundary-design, decomposition, staged-extraction, phasing, scoping]
related_smell: missing-boundary
related_pattern: null
---

# Staged boundary rearchitecting — when to extract, when to phase, when to refuse phasing

> **Template ADR.** Adopters: fill in your project's calibration values
> (the N thresholds in Rule 1, Rule 2, and Rule 4), wire the `deciders:`
> field, and promote `status: proposed` → `accepted` after your first
> boundary refactor lands under the framework. Numbers below are
> starting points calibrated against typical AI-grown Python project
> shapes; expect to supersede this ADR with a 0018 if your repo's pain
> points diverge.

## Context

The skill ecosystem has a complete **map → suspect → explain → refactor
→ guard** loop for tactical cleanup, plus a System-tier planning chain
(`/scope-feature` → `/impact-feature` → `/architecture-fit` →
`/plan-spec`). The new smell 9 (`missing-boundary`) in
`architectural-smells.md` and its detector `/propose-boundary` close the
*identification* gap — naming when distinct concerns live side-by-side
without a contract.

But identification doesn't answer the framing questions a boundary-
rearchitecting pass actually faces:

1. **When is this work the right move at all?** The detector will
   surface candidate seams on anything large enough to have prefixes
   and call edges. Without a trigger threshold, every 400-LOC file
   becomes a refactor candidate.
2. **When does a refactor require phasing rather than a single-shot
   extract?** `/refactor-subsystem`'s seven-phase orchestrator assumes
   a single behavior-preserving move with shim coverage. Real coupling
   sometimes forces a multi-PR sequence — caller migration first,
   then extraction, then dead-shim cleanup — and the chain has nowhere
   to record phase predecessors / verification gates / partial-revert
   plans.
3. **What gates close at each phase boundary?** Without explicit gates,
   "phased" becomes "perpetually mid-extraction with two parallel
   call paths" — strictly worse than not starting.
4. **When should we refuse to phase?** Phasing has a real coordination
   tax. Applied to small refactors it adds overhead without benefit;
   applied as deferral of a hard decision it produces stalled
   migrations that rot in the repo. The detector cannot judge this;
   the human needs a refusal rule.

## Decision

**Four rules, applied in order.**

### Rule 1 — Trigger threshold (when to start a boundary-design pass)

A boundary-design pass is warranted when **any two** of the following
hold on the target:

| Signal | Threshold (default — calibrate per project) |
|---|---|
| File LOC (single-file target) | ≥ 300 LOC |
| Distinct documented or detected domains in one file | ≥ 2 |
| Sibling files reaching into each other's `_private` helpers across a package | ≥ 3 cross-private import sites |
| Change-amplification — same N files co-edited in feature commits over the last 90 days | ≥ 3 files appear together in ≥ 4 commits |
| Test friction — setup for exercising one cluster requires fixturing N siblings | N ≥ 2 |
| Cross-cluster call-edge density (from `/map-subsystem`) | < 0.15 (low density between proposed sides) |

One signal alone is not enough. Two signals reflect that the smell is
real (the code has both shape and pain). Three+ signals make
`/propose-boundary` the obvious next move. Fewer than two signals → log
the observation in your lessons file, do nothing else.

### Rule 2 — One-shot vs staged extraction

**Default: single-shot.** A behavior-preserving two-commit refactor
under `/refactor-subsystem`'s standard discipline (extract + shim +
caller-migrate + dead-shim-remove, all in one PR sequence on one
branch) is the path of least coordination cost.

**Phase the extraction when any of these conditions hold:**

| Condition | Why |
|---|---|
| Single-shot affected files > 8 OR call sites > 25 | Review burden + merge-conflict risk too high; reviewer cannot hold the whole change in head |
| In-flight feature branch touching the same surface | Single-shot merges will conflict every rebase; phase to land caller-migration first, gate extraction on the feature shipping |
| Backward-compat shim not viable | E.g. external API contract, or a callsite outside the repo (vendor template, customer-managed config); phase so the caller-side migration coordinates with the external owner |
| Coordination dependency outside the engineer's control | E.g. a partner-team-owned consumer of the API; phase 1 publishes the new interface, phase 2 deprecates the old after the partner cuts over |

When phasing, the canonical sequence is:

1. **Phase 0 — Pre-move pin tests.** Characterization tests on every
   public-API symbol the boundary will surface. Must pass on `main`
   before any phase lands.
2. **Phase 1 — Caller migration.** Existing callers reaching into
   *private* helpers across the proposed boundary get rewritten to
   use the proposed public API surface. Lands as its own PR. No code
   movement yet.
3. **Phase 2 — Extraction.** Move the cluster behind the new boundary;
   ship the backward-compat shim (`__init__.py` re-exports) for any
   callers still using the old import path. Lands as its own PR
   driven by `/refactor-subsystem` in decomposition mode.
4. **Phase 3 — Dead-shim cleanup.** Remove the shim once no caller
   imports through the old path. Lands as its own PR. Gated on
   `grep`/import-analysis showing zero old-path importers.

### Rule 3 — Phase verification gates

Each phase boundary closes only when **all** of the following hold:

| Gate | What it means |
|---|---|
| Always-suite green | The repo's standard quick test suite passes |
| Targeted suite green for the affected subsystem | The slower per-subsystem suite passes |
| Pin tests green | The pre-move characterization tests authored in Phase 0 pass — before AND after the move |
| No new cross-private imports | A `grep`/import-scan shows no new caller reaches into a private helper across the new boundary |
| Shim coverage complete (Phase 2 only) | Every caller that used the old import path still resolves through the shim; no `ImportError` regressions |
| Old-path import count = 0 (Phase 3 only) | Repo-wide search confirms no caller still imports through the deprecated path |

A phase that ships without these gates closed is a regression in
disguise. If a gate cannot close, the phase aborts and the prior PR is
reverted (or held), not "patched forward."

### Rule 4 — When to refuse phasing

Phasing has a real coordination tax (multiple PRs, multiple reviews,
partial-state code-in-repo windows). Refuse phasing when **any** of
these hold:

| Condition | Why refuse |
|---|---|
| Small refactor: ≤ 5 affected files AND ≤ 10 call sites | Coordination overhead exceeds single-shot review cost |
| Phase 1 would leave callers in a broken state for > 3 days | The partial state itself is a hazard; do single-shot or pause |
| Proposed "Phase 2" has no concrete trigger, owner, or deadline | Partial extractions that never finish are worse than not starting — the codebase carries the cost of two parallel paths indefinitely |
| Phasing exists only to defer a hard decision | The decision still has to be made; phasing as decision-avoidance is hidden tech debt |
| The phasing plan has no rollback strategy | Each phase must be independently revertable; if it isn't, the refactor isn't behavior-preserving and phasing won't fix that |

When refusing phasing, the choices are: (a) do it single-shot under
`/refactor-subsystem`, (b) shrink scope until single-shot fits, or (c)
defer the refactor entirely and document the deferral with a re-
evaluation trigger.

## Alternatives considered

**A. Leave it to author judgment per refactor.** Rejected — author
judgment is exactly what the existing chain assumes, and the gap
(partial extractions that stall, refactors that shouldn't have started)
is what motivated this ADR. The whole point of an ADR registry is to
make recurring judgment calls answerable from prior reasoning rather
than re-debating per case.

**B. Build a separate `/plan-phased-refactor` skill first, then
back-fill the decision framework from skill experience.** Rejected for
sequencing — the skill bakes in calibration assumptions, and without an
ADR to cite, the calibration is invisible.

**C. Fold this into the folder-organization ADR.** Rejected — folder
topology and boundary identification answer different questions. The
folder-organization ADR says *how* code is grouped on disk. This ADR
says *when* a grouping warrants extraction at all and *how* the
extraction phases. The two pair (the boundary proposal often surfaces a
folder-organization decision), but bundling them dilutes both. They
cross-reference; they don't merge.

**D. Single phasing threshold instead of the four-condition table in
Rule 2.** Rejected — phasing is triggered by qualitatively different
forces (review burden, external coordination, in-flight feature
conflicts, external-API contract). A single LOC or file-count
threshold conflates them. The table maps each force to its own gate.

**E. Refuse phasing only when "Phase 2 has no trigger/owner/deadline."**
Rejected as too narrow — the stalled-Phase-2 case is the most visible
failure mode, but the others (small refactor with phasing overhead,
broken-caller-window > 3 days, decision-deferral) are real failure
modes too. Folding them in keeps the rule honest.

## Consequences

**Easier:**

- `/propose-boundary` cites this ADR in its proposal frontmatter; the
  human reviewing a proposal has a four-rule framework to apply rather
  than a free-form judgment call.
- Stalled "phase 2 someday" extractions become a refusal condition by
  default, not an oversight. The Rule 4 trigger/owner/deadline check
  forces explicit commitment before phasing starts.
- Reviewers of a single-shot extraction PR can quickly check Rule 2 to
  confirm phasing wasn't warranted; reviewers of a phased PR can check
  Rule 3 gates per phase.

**Harder:**

- Authors must collect the Rule 1 evidence (file LOC, domain count,
  cross-private import sites, change-amplification, test friction, call-
  edge density) before invoking `/propose-boundary`. The detector
  surfaces some of this automatically; the rest is human inspection.
- Phasing requires Phase 0 characterization tests *before* any code
  movement. This is real upfront work and was previously sometimes
  skipped on small phased refactors.
- Phase 3 dead-shim cleanup is now mandatory, not optional.

**Now disallowed:**

- Starting a boundary-rearchitecting pass on a target with fewer than
  two Rule 1 signals firing. Log the observation and stop.
- Phasing a refactor that fits Rule 4's refuse conditions.
- Marking a phase complete without all Rule 3 gates closed.
- Authoring a phasing plan with no per-phase rollback strategy.

## Verification

- `/propose-boundary` proposal frontmatter cites ADR 0017.
- `architectural-smells.md` smell 9 (`missing-boundary`) carries
  `Decided in: 0017` backref.
- A boundary-refactor PR description includes the Rule 1 signals fired,
  the Rule 2 single-shot-vs-phased choice with reasoning, and (if
  phased) the Rule 3 gate status per phase.
- `scripts/decisions.py audit` passes (status proposed, no broken
  supersedes, link-check clean).
- This ADR ships as `proposed`. It promotes to `accepted` after the
  first non-trivial boundary refactor lands under its framework. If the
  first run surfaces calibration drift (threshold values off),
  supersede this ADR with a 0018 that captures the new numbers rather
  than editing in place.

## Calibration record

Initial threshold values are starting points; calibrate by supersession
after ≥ 3 boundary refactors complete. The framework's value is the
*shape* of the rules, not the specific N — Rule 2 phasing-trigger
thresholds (8 files / 25 call sites) reflect a typical upper bound of
what fits a single PR review cycle, but team norms and reviewer
capacity vary. Pick the N that matches your team's review ceiling and
adjust from there.
