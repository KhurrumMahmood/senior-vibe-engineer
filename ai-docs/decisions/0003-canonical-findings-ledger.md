---
id: 0003
title: Skill outputs land in a canonical findings ledger
status: proposed
date: 2026-05-03
deciders: [khurrum]
supersedes: []
superseded_by: null
applies_to: [reports/_meta/, scripts/log_effectiveness.py, .claude/skills/]
tags: [skill-ecosystem, ledger, batching, observability]
related_smell: null
related_pattern: null
---

# Skill outputs land in a canonical findings ledger

## Context

The skill ecosystem under `.claude/skills/` has grown to 30+ skills
across the maintenance loop (map → suspect → explain → refactor →
guard) and the planning chain (decide → scope-feature → impact-feature
→ architecture-fit → plan-spec → refactor-subsystem). Each skill
writes per-skill outputs to `reports/<skill>/scan-<TS>/` and appends a
run-level row to `reports/_meta/effectiveness.jsonl` (34 entries
today). The effectiveness row carries `{skill, scan_id, ts, target,
findings_total, buckets}` with **per-skill open `buckets` vocabulary**
— `dormant.certain_delete`, `duplication.dedup`, `implicit-state.
extract_enum_candidate` etc. live in disjoint namespaces.

Three real consequences of this shape have shown up in recent work:

1. **No cross-skill join.** `app/proxy_services.py` carried a
   silent-catch shape (find-duplication ast-0008), a dead-defensive
   try-block (no skill detected it), and a coverage gap (no skill
   detected it either). They batched into commit `d427bc19` only
   because a human held them in working memory. There is no query for
   "all open findings on file F."
2. **No fix→finding linkage.** `/fix-workflow`'s effectiveness entry
   uses `cluster-<sha>` as scan_id; the originating finding ID lives
   in free-text `notes` if at all. There is no query for "which
   commit closed finding ast-0008."
3. **No batching substrate.** The skill-batching-protocol exploration
   at `reports/skill-batching-design/scan-20260503-050948/exploration.
   md` identifies three batching seams (intra-shape across files,
   intra-target across shapes, wave execution) — all three depend on
   a shared finding identity that survives across skills. Today's
   ledger cannot answer "all open findings of shape `silent-catch`"
   without per-skill custom code.

There are already two "registries" in the repo: the **decision**
registry (`ai-docs/decisions/`, this file is part of it) and the
**workflow** registry (per the "Unified AI workflow registry"
canonical pattern). The findings ledger is the missing third sibling,
sitting at the skill-output layer.

## Decision

Adopt a single canonical findings ledger at
`reports/_meta/findings.jsonl` with the following shape:

- **Format**: append-only JSONL. Source of truth, git-diffable,
  human-readable, no toolchain.
- **Per-finding row**:
  - `finding_id` — durable identifier (e.g. `ast-0008`, `dormant-0012`,
    `SC-7`, `LV-2`). Stable across re-scans.
  - `shape` — closed vocabulary (initial 12 names; see below).
  - `target` — file or symbol path the finding pertains to.
  - `status` — `open | landed | deferred-with-reason | in-wave-N`.
  - `discovered_by` — `{skill, scan_id, ts}`.
  - `closed_by` — `{skill, scan_id, ts, commit_sha}` when status is
    `landed`; null otherwise.
  - `notes` — free-text, optional.
- **Closed `shape` vocabulary** (initial 12, growth via ADR
  amendment): `silent-catch`, `dead-defensive`, `shadow-helper`,
  `pure-dedup`, `extract-enum`, `introduce-fk`, `extract-state-type`,
  `dormant-delete`, `query-mutation`, `frontend-global-sprawl`,
  `route-sprawl`, `bare-int-on-request`.
- **REFACTOR-skill effectiveness rows** gain a `closes:
  <finding_id>` field linking the run to the finding it closed. Lets
  `git log --grep` + ledger join answer "which commit closed X."
- **Per-work markdown summaries** continue to live at
  `reports/<skill>/scan-<TS>/summary.md` (already partially done by
  several skills) — these are the "work record" surface; they remain
  the primary git-diff surface for human review of what a run did.
- **Speed escape hatch**: a SQLite cache at
  `reports/_meta/findings.sqlite` MAY be materialized on-demand by
  `/triage-debt` or future batching skills when the JSONL scan
  becomes a bottleneck. The cache is gitignored and regenerable from
  the JSONL in one pass; it is never the source of truth.

Producers: every SUSPECT skill emits one row per finding to the
ledger (in addition to its existing per-skill `findings.json`).
Consumers: `/triage-debt` joins, future `/fix-workflow shape:<name>`
batches, future `/fix-target <file>` bundles, future `/run-wave <N>`
orchestrators, eventual UI.

## Alternatives considered

- **SQLite as primary store at `reports/_meta/findings.sqlite`**.
  Better querying out of the box; sub-millisecond `WHERE shape=X`.
  **Rejected** because the binary file is not git-diffable; PR
  reviewers cannot see what changed in the ledger without running a
  CLI; merge conflicts are unresolvable. JSONL with an on-demand
  SQLite cache delivers the speed when needed without losing the
  diff property.
- **DuckDB / parquet at `reports/_meta/findings.parquet`**. Best
  querying for analytical workloads; column-store wins at scale.
  **Rejected** for the same diffability reason, plus extra
  toolchain friction (DuckDB is not stdlib; parquet is binary).
- **Status quo + per-skill convention upgrades**. Add `finding_id`
  and `status` to each skill's per-skill `findings.json`
  independently; no shared ledger. **Rejected** — loses the
  substrate property. Model 1 (shape-shard `/fix-workflow`) and
  Model 2 (target-bundle `/fix-target`) cannot be built on top
  because they require cross-skill joins that per-skill files
  cannot serve.
- **Extend `effectiveness.jsonl` in place**. Add finding-level rows
  alongside the existing run-level rows and discriminate by a
  `level: run|finding` field. **Rejected** — overloads one stream
  with two row shapes; consumers must always filter; the existing
  `triage-debt` consumer would need rewriting.

## Consequences

**Easier:**

- "All open findings of shape `silent-catch`" becomes one JSONL scan
  + `WHERE shape='silent-catch' AND status='open'`.
- "Which commit closed finding `ast-0008`" becomes a ledger join on
  `closed_by.commit_sha`.
- Future UI (per the "would benefit from a UI" design intent) reads
  one substrate, not 30+ per-skill report shapes.
- `/triage-debt` becomes the planning-state surface — it already has
  the data flow; it just gains shape-vocabulary + wave-membership in
  its output.
- Three batching models (Models 1-3 in
  `reports/skill-batching-design/scan-20260503-050948/exploration.md`)
  become buildable without further substrate work.

**Harder:**

- Every SUSPECT skill needs to map its bucket vocabulary to a
  `shape` on emission. Rollout: skills that don't yet emit `shape`
  write `null`; `/triage-debt` treats null as "not yet onboarded"
  and reports onboarding-gap counts.
- Two stores (per-skill `findings.json` + canonical
  `findings.jsonl`) must stay in sync. Mitigation: the skill writes
  both in one transaction (Python script with try/finally); a
  pre-commit hook verifies the canonical ledger has at least as
  many rows as the per-skill files.
- The closed `shape` vocabulary requires an ADR amendment to grow.
  Intentional friction — prevents shape-creep where a fresh skill
  invents `weak-reference-leak` instead of mapping to an existing
  shape.

**Now expected / now disallowed:**

- New SUSPECT skills MUST emit `shape: <one of the 12>` or set
  `shape: null` with a documented onboarding note.
- `/fix-workflow` and any future `/fix-target` MUST set `closes:
  <finding_id>` on their effectiveness row.
- Per-skill `findings.json` files keep their per-skill shape
  (existing skills don't break) but ALSO emit one canonical-ledger
  row per finding.
- Direct edits to `findings.jsonl` are disallowed — append-only via
  `scripts/findings.py append`. (No mutate-in-place; status changes
  go through `scripts/findings.py update --status landed
  --commit-sha SHA`, which appends a new row with the same
  `finding_id` superseding the prior status row.)

**Expiration:**

- If the ledger grows past 5K entries before the SQLite cache
  materializes, JSONL-only scan time may become the dominant
  triage-debt cost. Re-evaluate at that threshold; the cache
  upgrade is a one-day add and does not change the ADR.

## Verification

- **Tooling**: `scripts/findings.py audit` (new — flags unknown
  shape values, broken `closes` references, malformed finding_ids,
  duplicate finding_ids without supersession). Add to pre-commit +
  CI when the ledger crosses 100 entries (deferred until then to
  avoid a noisy hook for a 0-entry file).
- **Doc backref**: a new entry under `.claude/docs/canonical-patterns.md`
  ("Skill outputs land in the canonical findings ledger") with
  `Decided in: 0003`. Authoring the entry is a separate edit task
  post-acceptance — `/decide` does not edit canonical-patterns.md.
- **Existing artifacts**: `reports/_meta/effectiveness.jsonl` (34
  entries) keeps its run-level role; the new `findings.jsonl` is
  finding-level. Both coexist. The `closes:` field on
  effectiveness.jsonl rows is the join key.
- **Skill-batching-protocol ADR (0004, planned)**: will be authored
  on top of this ledger and exercises Models 1-3 from the batching
  exploration doc. The 0004 ADR is the test that 0003's substrate
  is sufficient — if Models 1-3 cannot be expressed against the
  ledger shape decided here, 0003 needs amendment before 0004 lands.
