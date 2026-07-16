---
id: "0023"
namespace: core
title: /which-cleanup is the diff-scoped, registry-optional closeout consumer
status: proposed
date: 2026-06-08
deciders: [khurrum]
supersedes: []
superseded_by: null
revisit_when: ["a second closeout consumer needs diff-scoped cleanup routing or dogfooding shows registry-optional fallback changes the intended recommendations"]
applies_to: [".claude/skills/which-cleanup/", "scripts/query_planner.py"]
embodied_by: ["skill:which-cleanup"]
tags: [skills, routing, cleanup, closeout, coverage, registry-optional]
related_smell: format-equivalence-gap
related_pattern: null
---

# /which-cleanup is the diff-scoped, registry-optional closeout consumer

## Context

Routing into the code-quality skill suite (MAP → SUSPECT → EXPLAIN → REFACTOR →
GUARD) is forward and diff-blind: `/which-skill` matches a typed task,
`/which-shape` routes an operating loop from a situation, and `/triage-debt`
aggregates *cached* `find-*` reports on a periodic, whole-repo cadence. None reads
a diff. So at the end of a body of work, nothing tells an agent which cleanup
skills the change just made relevant — and large multi-file efforts (renames, mass
externalizations) each need *several* cleanup kinds, not one.

The substrate for closing this gap already exists in this ecosystem: `query_planner.py`
resolves `paths → subsystem → adjacency + related_skills`, and every skill declares a
`job:` (map/suspect/explain/refactor/guard) that tiers it. What was missing is the
diff-scoped consumer that the subsystem registry was designed for. Because this is the
portable ecosystem — host projects supply their own `.claude/subsystems.yaml` — that
consumer must work **with or without** a registry, the same way `/which-shape` degrades
when project-adapter state is absent rather than crashing.

This decision records what that consumer is, where its boundary sits relative to
`/triage-debt`, the registry-optional default, and the policy for the coverage join —
so future work doesn't re-litigate the boundary or grow a parallel source of truth.

## Decision

`/which-cleanup` is **the diff-scoped, scope-tiered closeout consumer** of the subsystem
registry, and it is **registry-optional**:

- **It owns the diff-scoped lane.** It reads what changed (files / `--staged` /
  `--changed-from` / `--commit` / `--range` / `--area` / `--since`), sizes a scope band,
  and recommends registry-derived skills tiered by point-in-time (pre-baseline /
  post-sweep / guard-tail). `/triage-debt` keeps the global, periodic, cached-report
  lane and never reads a diff; `/which-cleanup` never re-implements its recurrence
  scoring. A large-band closeout *hands off* to `/triage-debt` for the global picture.
- **No registry is a supported state.** With no `.claude/subsystems.yaml`, it degrades
  to the universal floor + scope-band sizing (no subsystem-specific scanners) instead of
  erroring — mirroring `/which-shape`'s `state: missing` degradation. A host project
  that ships a registry lights up the adjacency-derived recommendations.
- **It reuses the registry as-is; no parallel writers.** The area→skill mapping is read
  live from `related_skills` + `adjacency`, bucketed by each skill's own `job:`
  frontmatter. No second area→skill table is authored, and `subsystems.yaml`'s schema is
  not extended; a tiered `cleanup:` block would require its own follow-up ADR.
- **It is advisory and read-only against production code.** It never edits or runs the
  skills it recommends; writes are confined to `reports/which-cleanup/` and an opt-in
  spec stub under `ai-docs/specs/` (`--emit-plan`). The large band emits a sequenced plan,
  never an auto-run multi-scanner sweep.
- **The backward coverage join is honest about un-mappable targets.** Joining
  `reports/_meta/effectiveness.jsonl` `target` ↔ subsystem id is best-effort (the field
  is free-form; host projects can extend the path normalization). Anything un-joinable
  goes into an explicit `unmappable_targets` section — never silently dropped. The
  "recent scan" side counts only scanner skills, so meta/routing runs never count as
  coverage.

## Alternatives considered

- **Extend `/triage-debt` to read diffs.** Rejected: it is a pure aggregator over cached
  reports; teaching it to run fresh diff-scoped selection blurs its single job and yields
  two scoring models in one skill.
- **Author a parallel `.claude/docs/which-cleanup.yaml` area→skill table.** Rejected: a
  second area→skill source beside `related_skills` is the format-equivalence gap (smell 5)
  — two writers that silently diverge. Read the one registry instead.
- **Require a registry (error when absent).** Rejected for the portable ecosystem: a
  generic toolkit must be useful before a project supplies its own registry; the
  universal-floor + band degradation is.

## Consequences

**Easier:**
- End-of-task cleanup becomes a single diff-driven command instead of remembered prose.
- The "every cleanup ends in a guard" doctrine becomes measurable — the backward audit
  surfaces touched areas with no `guard`-tier scan.

**Harder:**
- Scope-band thresholds are a human-tuned knob, pending recalibration against
  `effectiveness.jsonl` once runs accumulate.
- The coverage join inherits the free-form-`target` hazard; host projects may need to
  extend the path normalization.

**Now expected / now disallowed:**
- New diff-scoped cleanup routing extends `/which-cleanup` (or the registry it reads),
  not a parallel table and not `/triage-debt`.
- A tiered `cleanup:` block on `subsystems.yaml` requires a follow-up ADR.
- Coverage reports must carry an `unmappable_targets` section; dropping un-joinable rows
  silently is disallowed.

## Verification

- **Tooling**: a referential-integrity check (`coverage.py check` — every
  registry/floor-recommended skill resolves to a real `.claude/skills/<name>`) wired into
  `.github/workflows/ci.yml`; `tests/scripts/test_which_cleanup.py` asserts band
  classification, job-frontmatter tiering, the registry-optional degradation, and the
  un-mappable bucket.
- **Doc backref**: `.claude/docs/architectural-smells.md` smell 5 (format-equivalence gap)
  carries `Decided in: 0023` for the "no parallel area→skill table" half.
- **Existing artifacts**: `scripts/query_planner.py` (`report_for_files` seam), the shared
  `_common/diff_resolution.py` (also consumed by `find-test-obligation-drift`).
