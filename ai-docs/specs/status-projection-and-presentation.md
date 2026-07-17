---
id: status-projection-and-presentation
title: "Status Projection And Presentation"
status: draft
last_audited: 2026-06-12
motivating_decision: "0037"
# `coverage` scans Python `# spec:<id>::IM-N` markers inside
# these roots only. Doc / skill / script / ADR IM items will
# never auto-tick here; track them via the spec checklist and
# audit-only `<!-- spec: -->` markers in the changed files.
code_roots:
  - scripts/
  - tests/
  - .claude/skills/which-shape/
  - .claude/skills/extract-enum/
  - .claude/skills/unify-shadows/
---

# Status Projection And Presentation

# Provenance

Promoted from plan `status-projection-and-presentation`
(`ai-docs/plans/status-projection-and-presentation.md`), motivating
decision ADR 0037 (`status-projection-schema`).
- Plan §1-2 → Goals
- Plan §3, §5 → Architecture
- Plan §4, §3 → Implementation (test-first)
- Plan §5, §6 → Exceptions

## Goals

**Problem.** Project state — structural health, proposals awaiting
approval, in-flight chains, artifact staleness — lives scattered
across `reports/` directories, plan/spec frontmatter, the idea
ledger, and `.engineering/` state files with no single machine- or
human-readable projection; users and fresh agent sessions cannot see
where the project stands or what needs action, which costs dropped
approvals, work based on stale artifacts, and the routing bootstrap
failure.

**Success criteria** (plan §2, verbatim contract):

1. **Projection runs cold in seconds, agent-free** — `status.py`
   emits schema-valid `status.json` in <5s, zero model calls; CI
   validates the schema and asserts per-section degradation (each
   source removed → section absent, exit 0).
2. **Pending approvals are detected and cleared** — seeded unapproved
   proposal dir appears with chain id + age; adding the closure
   artifact and regenerating removes it.
3. **Input-drift staleness works** — artifact with `scope.json` whose
   scoped path is touched by a later commit flags stale; untouched
   sibling does not.
4. **Dashboard renders standalone** — generated HTML opens from
   `file://` in headless Chromium with zero console errors and zero
   network requests, rendering every section present.
5. **Router grounding degrades cleanly** — with `status.json`
   present, `/which-shape` rationale cites ≥1 projection signal;
   absent, output byte-identical to today's.
6. **Queue contract round-trips** — staged packet file → session-start
   hook reports pending count; documented manual-pickup command lists
   the same item.

## Architecture

**Decision frame.** ADR 0037 pins the contract: outputs live under
`.engineering/local/` (status.json, queue/, rendered HTML); the
schema is versioned (`schema_version`, `generated_at`) with a closed
section vocabulary (`lifecycle`, `structural_health`,
`pending_approvals`, `in_flight`, `staleness`, `queue`, reserved
optional `goals`) and per-section `{"available": false, "reason"}`
degradation; the sweep-manifest read is pinned to the digest-tier
field subset (finding ids, rule names, severity, per-rule counts,
totals, timestamp); the queue is the first ADR-0036 packet
implementation; the projection is derived and advisory, never
authoritative.

**Conformance carried from plan §5:** ADR 0004 (reuse loaders, never
re-derive), ADR 0021 (local-zone placement, agent-neutral queue
JSON), ADR 0036 (digest tier only; never invoke `sweep.py` — ratchet
mutates its baseline), ADR 0023 (absent source → absent section,
exit 0), ADR 0033/0025 (the schema ADR carries embodiment +
assumes/revisit_when), ADR 0003 (one reader seam for the future
findings ledger), ADR 0013/0020 (ledger and lifecycle read through
existing loaders), ADR 0031 (projection surfaces state; `/converge`
gates — no verdict emission here).

**Call graph** (plan §3):

```
status.py ──reads──> plans.py:load_plans / decisions.py:load_decisions
          ──reads──> _common/ideas_lib.py (project/project_all — NEVER reimplemented)
          ──reads──> subsystems.py:load_registry, reports/_meta/effectiveness.jsonl
          ──reads──> engineering_home → .engineering/ (project-state, adapter)
          ──reads──> sweep manifest/ratchet artifacts (path-resolver indirection; file reads ONLY)
          ──reads──> reports/<chain>/ proposal dirs (skill→dir map; mtime-based)
          ──emits──> .engineering/local/status.json (versioned schema)
renderer  ──reads──> status.json ONLY (never recomputes — smell 5)
route.py  ──reads──> status.json (optional; --status override; degrade silently)
hook      ──reads──> .engineering/local/queue/ (agent-neutral JSON)
```

**Shape rules.** `status.py` stays one thin composer with one private
function per section, uniform `(sources) -> section | absent`
contract; decompose only past the ≥3-sibling threshold. Section
names, staleness states, and approval statuses are closed
vocabularies referenced via constants/enums, not bare literals.

## Implementation

Ordered test-first: each IM lands its test(s) in the same change.

### Characterization invariants (AR)

- **AR-1** `ideas_lib` owns ledger projection — `status.py` calls
  `project_all`, never re-derives (ADR 0004).
- **AR-2** Registry-optional degradation: every absent source →
  section marked absent, exit 0; unknown extra sections tolerated.
- **AR-3** The projection never writes into, renames, or normalizes
  any skill's `reports/` dir; test fixtures are synthetic `tmp_path`
  trees only.
- **AR-4** Scan-dir names are opaque — age/staleness use mtime or
  embedded timestamps, never name parsing.
- **AR-5** `route.py --json` stays a `sort_keys` envelope —
  byte-identity when `status.json` is absent (forbids even an added
  constant key); projection signals are additive-only telemetry
  extras.
- **AR-6** `sweep.py` is never invoked by the projection (`ratchet`
  rewrites its baseline on a clean run); manifest consumption is
  file-reads of the ADR-0037 pinned field subset only.
- **AR-7** ADR 0021 zones respected: outputs in `.engineering/local/`
  (gitignored by the shipped rule); queue files are plain
  agent-neutral JSON; `.engineering` stays scope-walk-invisible.
- **AR-8** Stable finding-id semantics pass through untouched;
  `latest` symlinks usable, never required.
- **AR-9** `effectiveness.jsonl` is append-only and read-only to the
  projection; it records activity, never closure.
- **AR-10** Pre-commit stays diff-scoped and fast — all new checks
  are CI/pytest only.
- **AR-11** Pending-approvals honesty: closure detectable for only 2
  of 9 chains (prevent-regression, propose-boundary); the rest report
  "pending until explicitly dismissed"; the detector must not pretend
  to see execution.

### Implementation targets (IM)

- [x] IM-1: **Schema constants + validator.** Section vocabulary,
  `schema_version = 1`, absent-marker shape, closed status
  vocabularies, as a small module `status.py` and tests share.
  Tests: schema-validity fixtures in `tests/test_status.py`.
- [x] IM-2: **`scripts/status.py` core sections.** `lifecycle` (ADR 0020
  state via existing loader), `in_flight` (plans/specs frontmatter +
  `ideas_lib.project_all`), `structural_health` (manifest digest via
  one path-resolver indirection), `queue` (pending count). Tests:
  per-section presence + AR-2 degradation matrix (each source
  removed → absent, exit 0).
- [x] IM-3: **Pending-approvals detector.** Skill→report-dir map over the
  9 proposal chains, mtime-based age, AR-11 honesty statuses. Tests:
  seeded proposal dir appears; closure artifact clears the 2
  closure-detectable chains; others stay "pending until dismissed".
- [x] IM-4: **`scripts/_lib/artifact_scope.py`.** Sidecar `scope.json`
  read/write helper (named to avoid the `_common/scope.py`
  collision). Tests: new module (NOT `tests/test_scope.py` — name
  taken).
- [x] IM-5: **Exemplar `scope.json` adoption.** `extract-enum/scripts/
  collect.py` and `unify-shadows/scripts/collect_shadows.py` emit
  sidecars via IM-4. Tests: sidecar emitted alongside the report.
- [x] IM-6: **Input-drift staleness.** `status.py` flags artifacts whose
  scoped paths were touched by commits after artifact write — the
  suite's first `tmp_path` `git init` fixture. Tests: success
  criterion 3 both directions.
- [x] IM-7: **Lens renderer v0.** Deterministic script: `status.json` →
  self-contained HTML (data inlined, design-token CSS inlined,
  vanilla web components, copy-paste command actions; zero
  network/agents). Tests: Playwright headless-Chromium smoke —
  `file://`, zero console errors, zero network requests, every
  present section rendered.
- [x] IM-8: **Queue contract + session-start hook.** Packet-compatible
  item format (ADR 0036 fields + `staged_at`/`status`/origin ref) in
  `.engineering/local/queue/`; hook per the house pattern
  (`scripts/agent_policy/hook.py`) reporting pending count; document
  the manual-pickup floor for non-Claude agents. Tests: success
  criterion 6 round-trip.
- [x] IM-9: **`route.py` grounding read.** `--status` path override;
  signals cited in rationale as additive extras; stale projection
  (`generated_at` older than sources) dropped silently. Tests: extend
  `tests/test_which_shape.py` with the AR-5 byte-identity regression
  + grounded-rationale fixture.
- [x] IM-10: **CI wiring.** Playwright+chromium step in
  `.github/workflows/ci.yml` (the repo's first browser harness);
  pytest modules join via existing `testpaths` (zero CI edits for
  them).

## Learnings

### User-facing

_(empty — append from extraction during Phase 2b)_

### Technical

_(empty — append from extraction during Phase 2b)_

## Exceptions

- **Bounded parallel-read in `route.py`** (accepted smell, plan §5):
  the live `.engineering/` read stays authoritative AND the
  projection signal is added — two reads of overlapping facts.
  Accepted because signals are additive-only and stale projections
  are dropped; collapsing route.py onto the projection would invert
  the dependency and break AR-5.
- **`route-grounding-reconciliation`** (deferred from plan §6 P1 —
  resolve during implementation of IM-9): exact staleness comparison
  rule (mtime set vs. generated_at) is an implementation detail; no
  ADR unless it turns out to constrain other consumers.
- **`goals` section** — plan §6 P1 resolved by ADR 0037: reserved in
  schema v1 as optional + absent-tolerated; populating it is W-E's
  work, not this spec's.
- **Pending-approvals honesty limit** (AR-11): 7 of 9 chains have no
  detectable closure artifact — the projection reports them as
  pending-until-dismissed rather than inventing closure heuristics.
- **"stdlib-only" dropped** (impact correction, plan §5): the
  mandatory-reuse loaders are PyYAML-backed; the projection is
  venv-python, stdlib-preferred.
- **ADR 0037 is `proposed`** at promotion time — acceptance is a
  human gate (`/decide --amend 0037`); implementation may proceed
  against it, but a rejection re-opens IM-1/IM-2 placement.

---

## Known symbol inventory (stub — not tabulated)

_(no code root is both a `.py` file and over 1000 LOC — inventory table omitted at_
_scaffold time. Greenfield spec: `scripts/status.py`,_
_`scripts/_lib/artifact_scope.py`, the renderer, and the hook do not_
_exist yet; `/refactor-subsystem` Phase 1.2 expands inventory once_
_code lands.)_
