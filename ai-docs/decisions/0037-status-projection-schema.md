---
id: "0037"
namespace: core
title: Project status is one versioned, derived status.json under .engineering/local/, with a packet-compatible work queue
status: accepted
date: 2026-06-12
deciders: [khurrum, claude-code]
assumes: ["the sweep manifest schema remains unversioned (the projection is its first programmatic consumer and pins a field subset)", "copy-paste command actions are a sufficient interaction floor for the presentation tier (no localhost server needed yet)"]
revisit_when: ["ADR 0036 productization versions the sweep manifest schema (re-derive the pinned field subset against it)", "the copy-paste interaction floor proves insufficient in dogfooding (build the deferred stdlib localhost server tier)", "a second host project consumes the projection (re-examine schema_version migration policy against real cross-repo drift)"]
supersedes: []
superseded_by: null
applies_to: [scripts/, .engineering/, ai-docs/plans/status-projection-and-presentation.md, .claude/skills/which-shape/]
embodied_by: ["script:scripts/status.py", "script:scripts/render_status.py", "script:scripts/queue_status.py", "script:scripts/_lib/status_schema.py", "script:scripts/_lib/artifact_scope.py", "doctrine:.claude/docs/queue-contract.md"]
tags: [projection, status, dashboard, queue, packets, engineering-folder, schema-versioning, degradation, presentation]
related_smell: format-equivalence-gap
related_pattern: parallel-writers-shared-producer
---

# Project status is one versioned, derived status.json under .engineering/local/, with a packet-compatible work queue

## Context

Project state — structural health, proposals awaiting approval,
in-flight plans and ideas, artifact staleness, lifecycle posture —
lives scattered across `reports/` scan directories, plan/spec
frontmatter, the idea ledger, sweep manifests, and `.engineering/`
state files. No single machine- or human-readable projection exists,
which costs dropped approvals, work based on stale artifacts, and the
routing bootstrap failure (nothing grounds `/which-shape` in actual
project state). The `status-projection-and-presentation` plan
(architected 2026-06-12) ships the producer (`scripts/status.py`), a
lens renderer, a `/which-shape` grounding read, and a staged-work
queue — and its `/architecture-fit` pass routed every materially open
fork into this one decision so placement, schema, and packet
compatibility land coherently rather than as fragments.

Three constraints shape the contract. ADR 0021 disallows new toolkit
per-project state at repo root or under `.claude/`, and splits
`.engineering/` by commit policy (durable team knowledge committed;
per-run machine-local scratch under gitignored `.engineering/local/`).
ADR 0036 forbids agents (and by extension dashboards) from consuming
raw finding lists — digests only — and specifies prose-only "packets"
that nothing yet implements. And the sweep manifest, the projection's
structural-health source, is unversioned and scheduled for revision at
`scripts/` promotion, so its first programmatic consumer must pin what
it reads.

## Decision

One producer, one contract, five sub-rules:

1. **Placement: the gitignored local zone.** The generated projection
   lives at `.engineering/local/status.json`; the staged-work queue at
   `.engineering/local/queue/`; rendered presentation artifacts (the
   dashboard HTML) beside them in the same zone. Rationale: all three
   are derived, regenerable, per-run outputs — exactly ADR 0021's
   local-zone seam — while consumers (renderer, `route.py`, the
   session-start hook) need a stable well-known path that `reports/`'
   opaque timestamped scan dirs cannot provide. Nothing here enters
   the committed zone, which also sidesteps ADR 0021's open
   derived-knowledge merge-conflict problem.

2. **The schema is versioned and degradation-shaped.** `status.json`
   carries a top-level integer `schema_version` and `generated_at`
   timestamp. Section names form a closed vocabulary (initial set:
   `lifecycle`, `structural_health`, `pending_approvals`,
   `in_flight`, `staleness`, `queue`, plus a **reserved optional
   `goals` section** so the goal-layer work lands without a version
   bump). Every section is independently absent-tolerated: a missing
   source yields `{"available": false, "reason": ...}` for that
   section and exit code 0 (the ADR 0023 degradation precedent).
   Consumers must tolerate absent sections and unknown *additional*
   sections; removing or renaming a section or field requires a
   `schema_version` bump.

3. **The sweep-manifest read is pinned to a digest-tier field
   subset.** The projection consumes only: stable finding ids, rule
   names, severity, per-rule counts, totals, and the manifest
   timestamp — by file reads through one path-resolver indirection.
   Missing fields degrade the section to absent rather than erroring.
   The projection never invokes `sweep.py` (its `ratchet` subcommand
   rewrites the GUARD baseline in place on a clean run — a "status
   read" would mutate guard state) and never surfaces raw finding
   lists (ADR 0036's disallowed list).

4. **The queue contract is the first ADR 0036 packet
   implementation.** Queue items are plain agent-neutral JSON files,
   one per staged work item, carrying the 0036 packet fields (scope
   file list, recipe, verification command, expected delta, token
   budget) plus queue metadata (`staged_at`, `status`, originating
   chain/proposal ref). The Claude Code session-start hook is a
   convenience *reader* over this neutral data; the documented
   manual-pickup command is the floor for every other agent.

5. **The projection is derived and advisory — never authoritative.**
   No skill writes to `status.json`; no consumer treats it as
   overriding its live sources. `route.py` keeps its live
   `.engineering/` read as authoritative and uses projection-derived
   signals as additive rationale/telemetry extras only, dropped
   silently when `generated_at` predates the sources. With
   `status.json` absent, `route.py --json` output stays
   byte-identical to today's.

## Alternatives considered

- **Place outputs under `reports/`** (derived-output convention).
  Rejected: scan-dir names are opaque and timestamped (no stable
  path), the namespace is owned by skill runs the projection is
  forbidden to write into, and `reports/` carries no cross-agent
  state doctrine; `.engineering/` does.
- **Place outputs in the committed `.engineering/` zone.** Rejected:
  per-run regenerable output fails ADR 0021's committed-zone test
  ("would a teammate cloning this repo need it?" — no, they
  regenerate it in seconds), produces churny diffs, and walks into
  the derived-knowledge merge-conflict open question.
- **Repo root or `.claude/`.** Disallowed outright by ADR 0021.
- **Unversioned schema.** Rejected: an emergent multi-section design
  that will gain fields is exactly the case ADR 0021 already decided
  needs a version + migration path; the projection inherits that
  reasoning.
- **Read the full sweep manifest (or shell out to `sweep.py`).**
  Rejected: raw-findings consumption is on ADR 0036's disallowed
  list, and the `ratchet` mutation hazard makes invocation a
  correctness bug, not a style choice.
- **A bespoke queue format.** Rejected: ADR 0036 already specifies
  packet fields; a second staged-work shape would be a parallel
  writer (smell 5) of the same concept and would block the planner →
  queue → executor pipeline from ever composing.
- **Build the stdlib localhost server now** (POST→queue, SSE
  refresh). Deferred, recorded as the middle rung of the server-tier
  ladder (static self-contained HTML → stdlib localhost → hosted):
  the static tier with copy-paste command actions is the v1
  interaction floor; the server tier activates only when dogfooding
  shows that floor insufficient (`revisit_when`).
- **Defer the `goals` section to a v2 bump.** Rejected: reserving it
  as optional + absent-tolerated costs nothing under the degradation
  doctrine and saves a version bump for already-scheduled work.

## Consequences

**Easier:**
- Every consumer (renderer, router, hook, future host dashboards)
  programs against one stable path and one versioned contract instead
  of five source formats.
- Renderers stay dumb — `status.json` in, HTML out — so presentation
  tiers can multiply without multiplying state readers (smell 5
  stays dead).
- The queue gives ADR 0036's packet concept its first executable
  surface; planner and executor work can now compose against it.

**Harder:**
- The pinned manifest field subset must be re-verified when ADR
  0036's productization lands a versioned schema (named in
  `revisit_when`).
- Gitignored outputs mean every clone/agent regenerates before
  reading — acceptable at <5s cold, but consumers must handle
  "file absent" as a first-class state (they must anyway, per the
  degradation doctrine).
- `schema_version` discipline is now real maintenance: section/field
  removals require a bump and a migration note.

**Now expected / now disallowed:**
- New projection sections declare their absent-degradation behavior
  at introduction; a section that errors on a missing source is a
  regression.
- No skill writes to `status.json`; no consumer treats it as
  authoritative over live sources; `route.py` byte-identity with the
  file absent is a permanent regression test.
- Staged-work items anywhere in the ecosystem use the packet-
  compatible queue format — a second staged-work file shape requires
  superseding this ADR.
- Dashboards and digests render judged/digest-tier data only; raw
  finding lists never flow through the projection (inherits ADR
  0036).

## Verification

- **Tooling**: the plan's §2 criteria are the acceptance tests —
  schema-valid output in <5s with per-section degradation asserted
  (`tests/test_status.py`), pending-approvals round-trip, scope-drift
  staleness, renderer `file://` smoke with zero console errors,
  `route.py` byte-identity regression, queue→hook round-trip.
  `scripts/decisions.py audit && link-check` green over this ADR.
- **Doc backref**: `architectural-smells.md` smell 5
  (format-equivalence gap) gains `Decided in: 0037` for the
  "projection reads live sources; renderers never recompute" half;
  `canonical-patterns.md` `parallel-writers-shared-producer` entry
  gains the same backref when the human lands it.
- **Existing artifacts**: `ai-docs/plans/status-projection-and-
  presentation.md` (§5 conformance walk, §6 charter this ADR
  resolves); `reports/impact-feature/scan-20260612-052409/impact.md`
  (the six-scout evidence for the behaviors this contract preserves).
