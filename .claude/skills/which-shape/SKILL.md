---
name: which-shape
description: Recommend the right problem-solving loop before choosing individual skills. Reads the explicit shape registry plus project adapter/profile state, then returns an advisory route such as project-intake, bug-fix, legacy-stabilization, health-audit, refactor-execution, regression-prevention, or decision-capture. Use when the user describes a messy situation and should not need to understand the skill catalog.
argument-hint: "<situation or task description>"
allowed-tools: Bash, Read
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  Strategic routing when the user or agent is unsure what kind of
  problem-solving loop to run. Especially useful for unknown projects,
  messy inherited code, broad health questions, recurring failures,
  or ambiguous prompts where a single skill recommendation is too
  tactical.
not_for: |
  Picking between two already-known skills (use /which-skill). Running
  a skill automatically. Tiny obvious edits where direct implementation
  is cheaper than any routing. Replacing human judgment about project
  goals; missing intent should route to /project-interview.
language: any
framework: any
lanes: [routing]
stage: frame
entrypoint: true
consumes: [situation, project_profile, adapter]
produces: [shape_recommendation]
risk_triggers: [unknown-project, legacy, missing-profile, recurring-failure]
max_overhead: "Return one shape, a first next step, and a stop/reassess condition; do not invoke the skills."
---

# /which-shape

Recommend an operating loop, not a single tool. `/which-skill` answers
"which skill?" after the work shape is clear. `/which-shape` answers
"what kind of work are we doing?"

This is advisory-only in v1. It never invokes the recommended skills.

## Forms

```bash
/which-shape "this inherited repo feels slow and chaotic"
/which-shape "unknown project; where should an agent start?"
/which-shape "this bug keeps coming back"
```

The script form:

```bash
.venv/bin/python .claude/skills/which-shape/scripts/route.py \
  "this inherited repo feels slow and chaotic"
```

Use `--json` for machine-readable output and `--skip-log` for tests.

## Output

The recommendation includes:

- shape id and title;
- confidence and rationale;
- first next command;
- short loop sequence;
- stop/reassess condition;
- alternatives.

## Registry

The explicit shape registry lives in `shapes.yml`. Keep it small and
loop-level. Do not mirror the whole skill catalog.

When adding or materially repurposing skills, run
`/check-ecosystem-consistency` and review whether `shapes.yml` needs an
update. Add a skill to a shape only when it changes the operating loop;
purely tactical skills can stay out after that review is captured in the
ecosystem state.

V1 shapes:

- `project-intake`
- `direct-change`
- `bug-fix`
- `feature-shaping`
- `legacy-stabilization`
- `health-audit`
- `refactor-execution`
- `regression-prevention`
- `decision-capture`

## Project Context

The router reads `.claude/project/adapter.yml`,
`.claude/project/profile.yml`, and `.claude/project/open-questions.md`
when present.

Missing project context is a routing signal, not a universal blocker.
Broad unknown-project prompts should route to `project-intake`; narrow
typos and concrete bugs should still route directly.

## Telemetry

The router logs `event_kind: recommendation` events to
`.claude/skill-use/log.jsonl`. Projection and compaction keep these
separate from actual skill-run useful rates.

To record human feedback on a recommendation, rerun the same route with:

```bash
.venv/bin/python .claude/skills/which-shape/scripts/route.py \
  "this inherited repo feels slow and chaotic" \
  --outcome overridden \
  --human-override "wrong-shape: should have started with project-intake"
```

## Relationship To `/which-skill`

Use `/which-shape` first when the operating mode is unclear. Use
`/which-skill` once the shape is known and the question is tactical.

Bad pattern: asking `/which-skill` to decide how to onboard or stabilize
an unknown repo. That is exactly what `/which-shape` exists to handle.
