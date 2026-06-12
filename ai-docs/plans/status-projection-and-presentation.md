---
name: status-projection-and-presentation
title: "Status Projection And Presentation"
status: scoped
date: 2026-06-12
authors: [khurrum, claude-code]
motivating_decision: null
successor_spec: null
subsystems: [scripts, reports, engineering-state, skills-routing]
workflows: []
---

# Status Projection And Presentation

## 1. Scope & Bounds

**Problem.** Project state — structural health, proposals awaiting
approval, in-flight chains, artifact staleness — lives scattered across
`reports/` directories, plan/spec frontmatter, the idea ledger, and
`.engineering/` state files with no single machine- or human-readable
projection; users and fresh agent sessions cannot see where the project
stands or what needs action, which costs dropped approvals, work based
on stale artifacts, and the routing bootstrap failure (nothing grounds
the routers in actual project state).

**In scope.**
- **Projection-schema ADR** (via `/decide`): versioned `status.json`
  schema, file placement (see open fork below), and the server-tier
  ladder (static → stdlib localhost → hosted) recorded as
  alternatives-considered. Declares `embodied_by` per ADR 0033.
- **`scripts/status.py`** — deterministic, stdlib-only projection
  composing existing sources, each section degrading cleanly when its
  source is absent (registry-optional doctrine, per ADR 0023's
  degradation precedent): lifecycle state (`.engineering/`
  project-state/adapter), structural health (sweep manifest + ratchet
  baseline where present), pending approvals, in-flight work
  (plans/specs `status:` frontmatter; idea-ledger projection),
  coverage/staleness signals (latest relevant `reports/*/latest`), and
  `schema_version`.
- **Pending-approvals section** — per-chain detection rules for
  proposal-emitting skills (`unify-shadows`, `extract-*`,
  `prevent-regression`, `propose-*`): proposal artifact present, no
  execution/closure artifact, with age.
- **`scope.json` convention** — additive sidecar spec (paths an
  expensive artifact covered), a shared helper in `scripts/_lib/`,
  adoption in two exemplar skills, and input-drift staleness
  (commits touching scoped paths since artifact write) computed in
  `status.py`. Cheap detector reports are exempt — they re-run instead.
- **Lens renderer v0** — deterministic script emitting self-contained
  HTML from `status.json` (data inlined, design-token CSS inlined,
  vanilla web components; zero network, zero agents); the standing
  dashboard is the first lens; actions render as copy-paste commands.
- **Packet/queue directory contract** — file format for staged work
  items (ADR 0036 packet-compatible) plus a Claude Code session-start
  hook reporting pending count; documented manual-pickup floor for
  other agents.
- **`/which-shape` grounding read** — `route.py` consumes
  `status.json` as an additional routing signal when present; output
  unchanged when absent.
- **Tests + CI wiring** for all of the above (stdlib, fixture-based,
  joining the existing `coverage.py check` pattern in CI).

**Out of scope.**
- The stdlib localhost API server (POST→queue, SSE refresh) — deferred
  until the copy-paste interaction floor proves insufficient.
- Hosted / Next.js / multi-project / auth product tier.
- The non-technical translation layer (cheap-model plain-language
  finding cards; ledger: `nontechnical-translation-layer`).
- Full `/which-shape` v2 interactivity (consent-to-invoke, button
  forks; ledger: `which-shape-v2-grounded-router`).
- Skill-catalog reorganization and naming — owned by the
  `shareable-core-reorganization` plan (W1, ADR 0034).
- The ADR 0003 findings-ledger schema itself — owned by
  `shareable-core-reorganization` W5; this plan ships one reader seam
  so the projection adopts whatever 0003 lands.
- Track B composition machinery (operator/lens/pattern cards,
  composition ledger, TOC goal router — ledger:
  `operator-composition-ledger` and siblings).
- Metered headless agent execution triggered from any UI.

**Non-goals.**
- Not a second source of truth: the projection is derived, read-only,
  regenerable at will; no skill ever writes to it or reads it as
  authoritative over its sources.
- Not an agent-spawning surface: the presentation tier runs zero
  agents and spends zero tokens.
- Not a replacement for `/triage-debt` or `/which-cleanup` scoring —
  the projection composes their outputs; it does not re-rank.
- Not a report-format redesign: `scope.json` is strictly additive.
- Not a live web service: v1 is generate-and-open static artifacts.

**Prior constraints.**
- Decision 0023 — registry-optional degradation is the precedent for
  every projection section; and its "no parallel area→skill table"
  rule generalizes: the projection must read live sources, never
  author a second copy of any state.
- Decision 0036 — the sweep manifest/ratchet is the structural-health
  source; agents read digests (the projection *is* the digest); the
  queue contract must stay packet-compatible; detector-tier staleness
  is handled by re-running, not tracking.
- Decision 0021 — `.engineering/` is the portable cross-agent state
  home; constrains where the queue directory and any persisted
  projection output may live (open fork below).
- Decision 0033 — the new ADR must declare its embodiment
  (`scripts/status.py` + renderer + hook).
- Decision 0020 / `project-state.json` — maturity×stakes is the
  lifecycle section's source.
- Decision 0013 — the idea ledger (projection rules in
  `idea-ledger.md`) is the in-flight-ideas source.
- Decision 0003 (proposed) — coordination point, not conflict: single
  reader seam so the findings-ledger schema slots in when W5 lands.
- Pattern "Parallel writers route through a shared producer"
  (Decided in 0004) — `status.py` is the canonical producer; the lens
  renderer consumes `status.json` and never recomputes state.
- Smell 5 (format-equivalence gap) — the shape this plan must not
  introduce between projection and renderers.
- Verification policy (UI row) — the rendered dashboard requires a
  headless-browser check, no console errors.
- **Open fork for `/architecture-fit` → `/decide`:** placement of the
  generated `status.json` and queue dir — `reports/` (derived-output
  convention) vs. `.engineering/` (ADR 0021 state home) vs. gitignored
  hybrid.
- Background exploration
  (`reports/scope-feature/scan-20260612/exploration.md`): clean
  greenfield — no existing `status.py`, no naming collision, no scope
  overlap with the other two active plans. Reusable substrate
  confirmed: `plans.py` / `decisions.py` / `ledger.py` /
  `subsystems.py` all emit JSON; `which-shape/scripts/route.py`
  already reads `.engineering/project/` via `engineering_home`;
  the sweep manifest's stable-id shape is the diffability pattern to
  reuse. Two hazards for `/impact-feature`: the sweep manifest schema
  is undocumented (inferred from code), and the idea ledger has no
  standalone projection helper (read-back lives in skill scripts —
  `status.py` must reuse `_common/ideas_lib.py`, not fork it, per the
  parallel-writers pattern).

## 2. Success Criteria

- **Projection runs cold in seconds, agent-free:** `python3
  scripts/status.py` on this repo emits schema-valid `status.json` in
  <5s with zero model calls; a CI test validates the schema and
  asserts per-section degradation (each source removed → section
  marked absent, exit code still 0).
- **Pending approvals are detected and cleared:** fixture test — a
  seeded unapproved proposal directory appears in the projection with
  chain id and age; adding the execution/closure artifact and
  regenerating removes it.
- **Input-drift staleness works:** fixture test — an artifact with
  `scope.json` whose scoped path is touched by a later commit is
  flagged stale; an untouched sibling artifact is not.
- **Dashboard renders standalone:** the generated dashboard HTML opens
  from `file://` in headless Chromium with zero console errors and
  zero network requests, rendering every section present in
  `status.json` (verification-policy UI row).
- **Router grounding degrades cleanly:** with `status.json` present,
  `/which-shape`'s rationale cites ≥1 projection-derived signal on a
  fixture; with it absent, output is byte-identical to today's
  (registry-optional regression test).
- **Queue contract round-trips:** a staged packet file in the queue
  directory causes the session-start hook to report a pending count;
  the documented manual-pickup command lists the same item.

## 3. Impact Map

_Filled by `/impact-feature`. Subsystems, models, routes,
services touched. Reach-and-blast analysis._

## 4. Blast Radius

_Filled by `/impact-feature`. Call sites and behaviors that
must be preserved across the change._

## 5. Architecture Fit

_Filled by `/architecture-fit`. Decision conformance, canonical-
pattern alignment, new smells introduced or avoided._

## 6. Open Decisions

_Filled by `/architecture-fit`. Material forks not yet decided —
candidates for `/decide`._

## 7. Promotion Notes

_Filled by `/plan-spec` when promoted. What sections of the spec
were derived from which sections of the plan; any deltas._
