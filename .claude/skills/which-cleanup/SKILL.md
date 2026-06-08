---
name: which-cleanup
description: Diff-driven, scope-tiered closeout router. Given what changed (files / --staged / --changed-from REF / --commit SHA / --range A..B / --area NAME / --since SPEC), it sizes the change and recommends which code-quality skills to run at task closeout — bucketed pre-baseline / post-sweep / guard-tail — escalating from an advisory checklist (small) to a multi-agent scoped scanner fan-out (medium) to a runnable closeout plan / Workflow + spec stub (large). Also runs backward as a coverage audit over a commit range. Advisory and read-only against production code.
argument-hint: "[paths… | --staged | --changed-from REF | --commit SHA | --range A..B | --area NAME | --since SPEC]"
allowed-tools: Bash, Read
user-invocable: true
tier: cross-cutting
job: meta
language: any
framework: any
best_for: |
  End-of-task / post-commit closeout: "I changed these files (or made these
  commits); which cleanup + GUARD skills should I run, scaled to how big the
  change is?" Also a backward coverage audit ("over the last N commits, which
  touched subsystems have no recent scan of an implied skill?").
not_for: |
  Forward task routing before work starts (use /which-shape then /which-skill).
  A global, periodic "what debt is accumulating" sweep over cached reports (use
  /triage-debt). The verification-tier / test-obligation check (complementary —
  use /find-test-obligation-drift). Running or fixing anything: this is advisory
  and read-only against production code. Invoking with no scope to scan the whole
  repo — it requires a diff / paths / area / since scope.
escalate_to: |
  /triage-debt for the global picture once the diff-scoped closeout is done;
  /refactor-subsystem to execute a large-band closeout plan from the spec stub.
delegate_from: |
  /which-shape (the task-closeout shape points here).
lanes: [routing]
stage: verify
entrypoint: true
consumes: [changed_paths, commit_range, area_name]
produces: [closeout_recommendation, coverage_audit]
risk_triggers: [post-change, multi-file, cross-subsystem, missing-guard]
max_overhead: "Trivial scope: one-line advice, no scan dir. Small: checklist only, no fan-out."
---

# /which-cleanup

The **diff-driven** sibling of `/which-skill` (text → skill) and `/which-shape`
(situation → operating loop). Those answer "what am I about to do?"; this answers
**"I just changed this — what cleanup do I owe, and how hard do I go?"** It is the
subsystem registry's planned closeout consumer (ADR 0023). The registry is
project-supplied: with no `.claude/subsystems.yaml`, it degrades to the universal
floor + scope-band sizing (no subsystem-specific scanners), the same way
`/which-shape` degrades when project state is absent.

Advisory and read-only: it recommends and, for large scope, *emits a plan* — it
never edits production code or runs the skills it names. The only writes are under
`reports/which-cleanup/` and an opt-in spec stub under `ai-docs/specs/`.

## Forms

```bash
/which-cleanup                       # the working-tree diff (uncommitted changes)
/which-cleanup --staged              # the staged diff
/which-cleanup --changed-from main   # everything since a ref
/which-cleanup --commit <sha>        # one commit (commits often happen mid-work)
/which-cleanup --range A..B          # a commit range
/which-cleanup --area site_intelligence   # a whole subsystem surface
/which-cleanup --since 3.days.ago    # everything touched since a time spec
/which-cleanup app/services/extraction/field_chat.py  # explicit paths
```

Backward (coverage audit):

```bash
.venv/bin/python .claude/skills/which-cleanup/scripts/coverage.py audit --last 50
.venv/bin/python .claude/skills/which-cleanup/scripts/coverage.py audit --since 2026-05-01
```

## How it works

```
resolve scope ─► classify band ─► select tiered roster ─► escalate by band
(diff_resolution)  (classify.py)   (subsystems.yaml +       (closeout.py)
                                    each skill's job:)
```

The roster is read **live** from the registry: each touched subsystem contributes
its `related_skills` plus the `/find-*` scanners its `adjacency` smell tokens imply,
bucketed into point-in-time tiers by reading each skill's own `job:` frontmatter
(`map` → pre-baseline, `suspect`/`explain`/`refactor` → post-sweep, `guard` →
guard-tail). A small universal floor (`find-comment-drift`,
`find-test-obligation-drift`, `prevent-regression`; plus `find-doc-link-rot` on doc
changes and `find-concept-divergence` on large rename-prone shapes) is always added.

## Pipeline

```bash
.venv/bin/python .claude/skills/which-cleanup/scripts/run.py <scope args> [--json] [--max-scouts N]
```

It resolves the scope, classifies the band, builds the tiered roster, writes
`reports/which-cleanup/scan-<TS>/closeout.{json,md}` (+ `latest`), and logs one
line to `reports/_meta/effectiveness.jsonl`. Read `closeout.md` and act on it.

## Escalation by band

| Band | Thresholds (OR, highest wins) | What you get |
|---|---|---|
| **trivial** | 1 file, ≤1 subsystem, <30 LOC | One line: run the touched test; optional `/decide`. No scan dir. |
| **small** | 2–5 files, 1 subsystem, <200 LOC | A 3-tier checklist. You run what's relevant. |
| **medium** | 6–20 files, 1–2 subsystems, <1500 LOC | Checklist **plus** a fan-out roster — dispatch the post-sweep scanners as concurrent read-only scouts (below). |
| **large** | >20 files **OR** ≥3 subsystems **OR** ≥1500 LOC | A sequenced MAP→SUSPECT→EXPLAIN→REFACTOR→GUARD plan in `closeout.md`; with `--emit-plan`, also a `/refactor-subsystem` spec stub + a Workflow script. |

**Medium — dispatch the fan-out (multi-agent).** The `fanout` list in `closeout.json`
is the capped (`--max-scouts`, default 5) post-sweep roster, each command already
**scoped to the changed files**. Dispatch them as concurrent read-only scouts —
e.g. one `_common/dispatch_scout_cheap.sh` invocation per scanner sent in a single
message (the `find-duplication` / `find-omnibus` pattern) — then triage the union.
Scope to the changed files only; never re-scan the whole repo.

**Large — hand off, don't auto-run.** The sequenced plan is always in `closeout.md`.
With `--emit-plan`, a spec stub (`ai-docs/specs/<area>-closeout-<TS>.md`) is written for
`/refactor-subsystem`, plus a Workflow script under the scan dir that fans the
post-sweep scanners out as agents for users who opt into the Workflow tool.
`/which-cleanup` never auto-runs a multi-scanner sweep.

## Backward coverage audit

`coverage.py audit` runs the same selection in reverse over a commit range: it finds
the touched subsystems, computes the skills they imply, and subtracts the skills with
a recent scan in `effectiveness.jsonl` — surfacing **gaps**, with **GUARD-tier gaps
highlighted**. The effectiveness `target` field is free-form, so the join is
best-effort (a host project can extend the path normalization); anything
un-joinable lands in an explicit `unmappable_targets` section — never silently
dropped. `coverage.py check` is the referential-integrity guard (every recommendable
skill resolves to a real skill dir); it is wired into CI (`.github/workflows/ci.yml`).

## Non-goals

- **Not a forward planner.** Before work starts, use `/which-shape` then `/which-skill`.
- **Not `/triage-debt`.** That is global + periodic over cached reports; this is
  diff-scoped + forward and runs fresh selection. Large-band closeout *hands off* to
  `/triage-debt` for the global picture rather than duplicating its scoring.
- **Not `/find-test-obligation-drift`.** That answers "what *tests*"; this answers
  "what *cleanup skills*". FTOD is one entry in the universal floor.
- **Never edits or runs.** Advisory only; writes under `reports/` and the opt-in
  spec stub.

## When things go sideways

| Symptom | Action |
|---|---|
| No scope given and working tree clean | Prints "no changes detected"; not an error. Pass a scope to audit something specific. |
| `--area` name unknown | Exits 2 with the bad name; run `.venv/bin/python scripts/subsystems.py list`. |
| Many `unmatched` files | The registry doesn't cover those paths — extend `.claude/subsystems.yaml` (they still count toward the band). |
| Medium fan-out feels expensive | Lower `--max-scouts`, or treat the checklist as advisory and run the highest-value scanner only. |
| Audit shows many `unmappable_targets` | Expected — effectiveness targets are free-form. They are surfaced, not counted as coverage. |

## Repository layout

```
.claude/skills/which-cleanup/
├── SKILL.md            # this file — orchestrator
└── scripts/
    ├── run.py          # forward closeout orchestrator
    ├── classify.py     # scope-band thresholds (tunable knobs)
    ├── select_scanners.py  # registry adjacency + job-tier → roster
    ├── closeout.py     # ranking, render, large-band plan/spec/workflow
    ├── coverage.py     # backward audit + referential-integrity check
    └── smoke.py        # detector smoke test
```

Shared substrate (not reinvented): `scripts/query_planner.py` (`report_for_files`),
`.claude/skills/_common/diff_resolution.py` (scope resolution, shared with
`/find-test-obligation-drift`), `scripts/subsystems.py`, and each skill's `job:`
frontmatter via `scripts/_lib/yaml_frontmatter.py`.
