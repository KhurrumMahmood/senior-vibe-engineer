---
type: "always_apply"
---

# Engineering Skills Ecosystem

## Project Overview
This repository hosts a project-agnostic, AI-grown skill ecosystem for
keeping a codebase healthy as senior engineers work on it: a maintenance
loop (`map -> suspect -> explain -> refactor -> guard`), a planning
ladder (Quick / Feature / System / Maintenance), and a diff-scoped lint
catalogue. It is mirrored from a Django host project but is being
generalized to stand alone.

**Working principle:** Optimal tooling for an AI-grown codebase
continuously converts hidden structure into explicit structure, and
one-off discoveries into repeatable guardrails.

## What lives here

- `.claude/skills/` -- the skills that drive maintenance, planning, and
  decision work. Each has a `SKILL.md` (the agent decision contract),
  optional `agents/` (scout briefs), `scripts/` (detection / collapse /
  report), `knowledge/` (host overlays), and `fixtures/` (illustrative
  examples for detectors).
- `.claude/docs/` -- canonical reference: `canonical-patterns.md`
  (positive law), `architectural-smells.md` (negative form),
  `linting.md`, `testing.md`, `development-workflow.md`,
  `senior-engineer-posture.md`, `quality-coordination-kernel.md`,
  `folder-organization.md`, `language-support-development.md`,
  `installation-and-on-demand-library.md`, `sub-agents.md`,
  `cross-tool-agent-governance.md`, `skill-catalog.md`, `precedents.yml`.
- `scripts/lint/` -- diff-scoped lints (silent-catch, stringly-status,
  query-mutation, fat-view, safe-dispatch, comment-drift,
  codegen-emits-new-paths). Host projects extend by adding a new
  `RuleSpec` to `scripts/lint/run.py`.
- `scripts/` -- supporting tooling: `decisions.py` (ADR registry),
  `precedents.py`, `specs.py`, `plans.py`, `ledger.py`,
  `skill_meta.py`, `log_effectiveness.py`, `skill_effectiveness.py`.
- `ai-docs/decisions/` -- the ADR registry. Target 2-5 entries per
  quarter; scaffold with `python3 scripts/decisions.py init <slug>`.

## Maintenance loop

The five-job loop is the spine: **map -> suspect -> explain -> refactor
-> guard**. Skipping MAP or EXPLAIN is fine when the target is already
understood. **Skipping GUARD is a mistake** -- it turns every cleanup
into a recurring tax. See `.claude/docs/skill-catalog.md` for the full
skill list and `.claude/docs/architectural-smells.md` for the six
architectural smells the SUSPECT skills target.

`/which-shape` chooses the operating loop when the task shape is unclear;
`/check-ecosystem-consistency` keeps that router, the skill catalog, and
public skill counts aligned after significant skill changes.

## Planning ladder

Plan complexity should be tiered to task stakes:

- **Quick** -- one-line / one-file. Just do the work.
- **Feature** -- 1-3 day scope, touches one workflow. Use
  `/plan-feature`.
- **System** -- multi-week or new-subsystem. Use the System chain:
  `/scope-feature` -> `/impact-feature` -> `/architecture-fit` ->
  `/plan-spec`.
- **Maintenance** -- the find/fix loop above.

Judgment pauses at the System tier are the point; do not collapse them.

## Decisions and precedents

When a real choice is being made (architectural fork, constraining
choice, or one that excludes alternatives), record an ADR under
`ai-docs/decisions/` via `/decide`. ADRs preserve historical decisions;
`precedents.yml` describes the current law-as-applied with canonical
examples, guards, exceptions, and a supersession path.

## Lints

The diff-scoped lint catalogue lives in
`.claude/docs/canonical-patterns.md`. Active rules: `silent-catch`,
`stringly-status`, `query-mutation`, `fat-view`, `safe-dispatch`,
`comment-drift`, `codegen-emits-new-paths`. Host projects extend the
catalogue by adding a script under `scripts/lint/`, appending a
`RuleSpec` to `scripts/lint/run.py`, mirroring into
`.pre-commit-config.yaml`, and adding a Canonical Patterns entry plus
bad/good fixtures under `tests/lint/`.

## Workflow Discipline

- Plan before ambiguous / risky / multi-file / architectural work.
- Use `/diagnose` for concrete bugs that lack a trusted
  reproduction loop or root-cause explanation.
- Use `/plan-skill` before creating or materially revising a repo
  skill; tiny wording fixes can be edited directly.
- Run `/check-ecosystem-consistency` after significant skill ecosystem
  changes; review `/which-shape` impact before updating its stored state.
- Apply `.claude/skills/_common/interface-depth.md` before adding
  helpers, services, module splits, abstractions, or adapters.
- Verify changed behavior before calling work done. State exactly what
  was not run and why.
- Capture lessons in the right surface: `.claude/tasks/lessons.md`
  (diary), `.claude/docs/known-issues.md` (current-state gotchas),
  `.claude/docs/precedents.yml` (case law), `ai-docs/decisions/`
  (ADRs).

## Detailed Documentation

See `.claude/docs/` for comprehensive reference:

- `canonical-patterns.md` -- positive law and lint catalogue
- `architectural-smells.md` -- negative form of every pattern
- `development-workflow.md` -- test-first / call-path / service / view
  prose
- `senior-engineer-posture.md` -- problem-class framing for non-trivial
  work
- `skill-catalog.md` -- the maintenance loop's skill list
- `linting.md` -- install, escape-valves, full scans, rule-set roadmap
- `testing.md` -- coverage map and tiered verification policy
- `folder-organization.md` -- intra-folder placement convention
- `sub-agents.md` -- cross-tool agent bridging
- `cross-tool-agent-governance.md` -- editing agent rules,
  cross-tool sync, executable guardrails
- `quality-coordination-kernel.md` -- kernel architecture, ROI,
  productization
- `precedents.yml` -- implementation case law
</content>
</invoke>
