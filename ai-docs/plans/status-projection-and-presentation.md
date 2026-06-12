---
name: status-projection-and-presentation
title: "Status Projection And Presentation"
status: architected
date: 2026-06-12
authors: [khurrum, claude-code]
motivating_decision: "0037"
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
- **`scripts/status.py`** — deterministic, venv-python
  (stdlib-preferred) projection
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

Full synthesis: `reports/impact-feature/latest/impact.md` (six scouts,
all passed). Condensed here.

**Touched subsystems.**
- `scripts-core` — `status.py` home; reuses `plans.py:load_plans:67`,
  `decisions.py:load_decisions:81`, `_common/ideas_lib.py`
  (project/project_all), `subsystems.py:load_registry:36`.
- `reports-and-proposals` — pending-approvals over 9 chains;
  `scope.json` sidecar (helper named `artifact_scope.py` —
  `_common/scope.py` collision); exemplar adopters extract-enum +
  unify-shadows.
- `engineering-state-and-queue` — ADR 0021 zones; agent-neutral JSON
  queue; session-start hook (no hooks exist today; house pattern is
  `scripts/agent_policy/hook.py`).
- `which-shape-routing` — seam is `project_context_state()`
  (route.py:117-145); needs `--status` path override.
- `sweep-manifest` — file-reads only via one path-resolver indirection;
  digest tier only.
- `ci-tests-hooks` — ~6 new test modules (zero CI edits); one new CI
  step: Playwright+chromium renderer smoke (first browser harness in
  repo); nothing in pre-commit.

**Constraint corrections for §5:** (a) §1's "stdlib-only" cannot hold —
the mandatory-reuse loaders are PyYAML-backed; recommend "venv-python,
stdlib-preferred". (b) ADR 0036 packets are prose-only — the queue
contract is the first packet implementation. (c) The sweep manifest
schema is unversioned/untested and scheduled for revision; the schema
ADR must pin the consumed field subset.

## 4. Blast Radius

**Behaviors to preserve** (11 total — full list in impact.md; the five
load-bearing ones):
- `ideas_lib` owns ledger projection — call, never re-derive (0004).
- Registry-optional: absent source → absent section, exit 0; the
  projection never writes into any skill's report dir.
- `route.py --json` is a sort_keys envelope — byte-identity when
  status.json absent forbids even an added constant key.
- NEVER invoke sweep.py from the projection — `ratchet` rewrites its
  baseline in place on a clean run (sweep.py:260); a read would mutate
  GUARD state.
- Pending-approvals honesty: closure detectable for only 2 of 9 chains
  (prevent-regression, propose-boundary); the rest report "pending
  until explicitly dismissed".

**Test surfaces.** New: `tests/test_status.py`,
pending-approvals/scope-staleness (first tmp-path `git init` in suite),
renderer smoke, queue hook, sidecar helper (NOT `test_scope.py` —
taken). Extend: `tests/test_which_shape.py` (byte-identity regression).
Patterns: `test_which_cleanup.py` (subprocess+overrides),
`test_project_adapt.py` (seed repo). `test_skill_detector_reads.py`
auto-covers new readers.

**Files to touch (estimate).** ~20 across 6 areas: ~12 new (status.py,
artifact_scope.py, renderer + assets, hook, queue doc, schema ADR, 6
test modules), ~8 modified (route.py + tests, two exemplar skill
collect scripts, ci.yml, example settings).

**Affected workflows.** None (`.claude/docs/workflows/` absent).

## 5. Architecture Fit

**Decision conformance.**
- ADR 0004 (parallel writers → shared helper) — `status.py` reuses
  `plans.py` / `decisions.py` / `_common/ideas_lib.py` /
  `subsystems.py` loaders verbatim; it never re-derives any
  projection rule. This **resolves the §3 stdlib-only correction**:
  the loaders are PyYAML-backed, and vendoring a parallel frontmatter
  reader to preserve "stdlib-only" would itself be the smell-5 shape
  ADR 0004 exists to block. §1 amended to "venv-python,
  stdlib-preferred".
- ADR 0021 (`.engineering/` state home) — supplies the doctrine for
  the placement fork (§6 P0): new toolkit per-project state may not
  land at repo root or under `.claude/`; the commit-policy seam
  ("per-run, machine-local scratch" → `.engineering/local/`) covers
  both the regenerable `status.json` and the queue. Queue files are
  plain agent-neutral JSON per the cross-tool rule; the session-start
  hook is a Claude-side convenience reader over neutral data.
- ADR 0036 (batch sweep manifests) — the projection consumes the
  digest tier only (counts / totals / id deltas) via one
  path-resolver indirection; it never invokes `sweep.py` (the
  `ratchet` subcommand rewrites its baseline in place — a "status
  read" would mutate GUARD state). The queue contract is the **first
  packet implementation** (0036 specifies packets; none exist) — the
  schema ADR must say so and keep the packet fields
  (scope/recipe/verification/expected-delta/budget) compatible.
- ADR 0023 (registry-optional degradation) — every projection section
  follows the `/which-cleanup` + `/which-shape` precedent: absent
  source → section marked absent, exit 0; and 0023's "no parallel
  area→skill table" rule generalizes — the projection reads live
  sources, never authors a second copy of any state.
- ADR 0033 (decisions declare embodiment) — the new schema ADR ships
  with `embodied_by: [script:scripts/status.py, script:<renderer>,
  hook:<session-start>]`; the hook kind is existence-advisory, which
  fits (hooks may live in host settings).
- ADR 0025 (assumes / revisit_when) — the schema ADR has genuine
  environmental dependencies and must carry both fields: it assumes
  the sweep-manifest schema stays unversioned (pin the consumed field
  subset; revisit when ADR 0036's productization versions it) and
  assumes copy-paste actions are a sufficient interaction floor
  (revisit when that proves false → the deferred localhost server).
- ADR 0003 (findings ledger, proposed) — coordination, not conflict:
  one reader seam so `findings.jsonl` slots in as a projection source
  when shareable-core W5 lands; the projection does not pre-build
  against the unaccepted schema.
- ADR 0013 (idea ledger) — in-flight-ideas section reads through
  `ideas_lib.project_all` only.
- ADR 0020 (maturity × stakes) — lifecycle section reads
  `.engineering/project-state.json` through the existing loader.
- ADR 0031 (`/converge` gate) — adjacency, no overlap: the projection
  is a state *surface*, `/converge` is an after-phase *gate*; the
  projection composes and renders, it never emits verdicts or
  re-ranks (§1 non-goal). The future `goals` section (W-E) renders
  stated-goal-vs-trajectory; gating against it stays `/converge`'s
  job.

**Pattern alignment.**
- `parallel-writers-shared-producer` — `status.py` is the single
  producer; the lens renderer consumes `status.json` only and never
  recomputes state; `route.py` cites projection signals but never
  treats them as authoritative over its live reads.
- `query-methods-are-side-effect-free` — the entire projection path
  is read-only by construction; the one trap (sweep `ratchet`
  auto-tightening) is handled by file-reads-only (above). The
  `--self` lint scope (`silent-catch`, `query-mutation`) applies to
  `scripts/` and should stay green over `status.py`.
- Scan-dir names are opaque (four conventions observed) — staleness
  and age use mtime / embedded timestamps, never name parsing.

**Smells avoided.**
- Smell 5 (format-equivalence gap) — the motivating smell: one
  producer, dumb renderers, no second writer of any section's facts.
- Smell 1 (omnibus module) — `status.py` composes ~6 sections; keep
  one private function per section with a uniform
  `(sources) -> section | absent` contract, composer stays thin. If
  sections grow past the ≥3-sibling threshold, decompose under the
  folder-organization convention — not pre-emptively.
- Smell 2 (stringly state) — section names, staleness states, and
  pending-approval statuses are closed vocabularies pinned in the
  schema ADR; Python comparisons go through enums/constants, not
  bare literals.

**Smells accepted (with justification).**
- A bounded parallel-read: `route.py` keeps its live
  `project_context_state()` read AND gains the `status.json` signal —
  two reads of overlapping facts that can disagree when the
  projection is stale. Accepted because the live read stays
  authoritative and projection signals are additive rationale
  extras only (§6 P1 pins the reconciliation rule); collapsing
  route.py onto the projection would invert the dependency and break
  the byte-identity regression contract.

## 6. Open Decisions

**P0 — must resolve before promotion.**
- `status-projection-schema` — the planned `/decide` (§1 in-scope)
  now has its full charter; **author it next**, before `/plan-spec`.
  It must settle, in one ADR:
  (a) **Placement fork** — `status.json` + queue dir under
  `reports/` (derived-output convention) vs `.engineering/local/`
  (ADR 0021 gitignored zone) vs hybrid. *Recommended:*
  `.engineering/local/` for both — 0021's seam classifies regenerable
  per-run output as local-zone state; the consumers (renderer,
  `route.py`, hook) need a stable well-known path, which opaque
  timestamped `reports/` scan dirs cannot give; and writing into
  `reports/` would add a writer to a namespace the projection is
  forbidden to touch (§4 behavior). Queue stays out of the committed
  zone to avoid 0021's open derived-knowledge merge-conflict problem.
  (b) **Versioned schema** with `schema_version`, closed section
  vocabulary, per-section absent-marker convention.
  (c) **Pinned sweep-manifest field subset** consumed (manifest is
  unversioned; first programmatic consumer).
  (d) **Queue contract as first ADR-0036 packet implementation**
  (packet-compatible field set).
  (e) Server-tier ladder (static → stdlib localhost → hosted) as
  alternatives-considered; `embodied_by` + `assumes`/`revisit_when`
  per ADRs 0033/0025 (see §5).

**P1 — should resolve before implementation.**
- `route-grounding-reconciliation` — how `route.py` treats a stale or
  contradictory `status.json` vs its live `.engineering/` read.
  *Recommended:* live reads stay authoritative; projection-derived
  signals are additive-only rationale/telemetry extras, dropped (not
  errored) when `generated_at` predates the sources' mtimes. Can be
  settled in the spec or at implementation; no ADR needed unless the
  rule turns out to constrain other consumers.
- `goals-section-reservation` — whether schema v1 reserves an
  optional `goals` section (W-E's cheapest embodiment) or defers it
  to a v2 bump. *Recommended:* reserve in v1 as optional +
  absent-tolerated — costs nothing under the degradation doctrine and
  saves a version bump. Fold into the P0 `/decide` as one line.

**Authored inline.**
- None — the single P0 fork is deliberately routed through the
  already-planned `status-projection-schema` `/decide` so placement,
  schema, and packet compatibility land as one coherent decision
  rather than fragments.

## 7. Promotion Notes

_Filled by `/plan-spec` when promoted. What sections of the spec
were derived from which sections of the plan; any deltas._
