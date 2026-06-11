---
name: plan-skill
description: Plan and harden a new or revised skill before implementation, including adversarial requirements pushback, trigger design, evidence contracts, dogfood cases, and review gates. Use when creating a new .claude/skills skill or materially changing an existing skill.
argument-hint: "<skill-idea-or-existing-skill>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: cross-cutting
job: plan
best_for: |
  Creating or materially revising a skill. Best when the risk is a skill
  that triggers too broadly, produces no durable artifact, lacks
  validation, duplicates an existing skill, or cannot be dogfooded before
  humans rely on it.
not_for: |
  Installing third-party bundles (use the platform skill-installer).
  Tiny wording fixes to an existing command doc - edit directly and run
  skill_meta.py lint. General feature planning (use /plan-feature or the
  System-tier chain). Code-quality detection work (use find-*).
escalate_to: |
  /decide when the skill establishes durable doctrine; /prevent-regression
  when a deterministic guard should enforce the skill contract; /which-skill
  when trigger overlap with existing skills is unclear.
language: any
framework: any
lanes: [skill-development, quality-kernel]
stage: frame
entrypoint: true
consumes: [skill_idea, existing_skill_context, repo_context]
produces: [skill_brief, adversarial_pushback, validation_plan]
evidence_required: [skill_problem, trigger_contract, validation_plan, adversarial_review]
risk_triggers: [new_skill, existing_skill_rewrite, broad_trigger, no_validation]
max_overhead: "Stop if the skill cannot name a durable artifact and at least one dogfood case."
---

# /plan-skill

You are designing a skill, not writing a long prompt. The deliverable is
a compact skill brief that makes the eventual implementation healthy
from the start.

Write to `reports/plan-skill/scan-<TS>/`:

- `skill-brief.md` - approved scope and contract;
- `adversarial-review.md` - pushback and accepted/rejected objections;
- `validation-plan.md` - dogfood cases, commands, and review gates;
- `evidence.json` - manifest for `scripts/evidence_gate.py`.

Do not implement the skill until the brief survives adversarial
pushback. If the request is just a tiny edit, say so and skip the skill
machinery.

## Stage 1 - Problem Before Skill

Name the problem class in one sentence:

- What repeated failure does this skill prevent?
- Why are docs, a lint, a test, or an existing skill insufficient?
- Which job does it perform: plan, map, suspect, explain, refactor,
  guard, decide, triage, teach, construct, diagnose, or meta?
- What artifact will exist after the skill runs?

If no durable artifact or measurable behavior exists, recommend against
creating the skill.

## Stage 2 - Adversarial Requirements

Before designing the happy path, attack the idea. Record answers in
`adversarial-review.md`.

Ask these directly:

1. What existing skill could absorb this instead?
2. What false trigger would make agents invoke it at the wrong time?
3. What work would a lazy agent skip while still sounding successful?
4. What validation proves the skill worked?
5. What should the skill explicitly refuse to do?
6. What will be stale in three months unless it is generated or tested?
7. What human judgment remains non-mechanical?

If the answers are weak, narrow the skill or stop.

## Stage 3 - Contract

Draft the frontmatter before body prose:

- `description` with concrete triggers;
- `best_for` and `not_for`, with adjacent skills named;
- `escalate_to` and `delegate_from` where relevant;
- `language` / `framework`;
- task-packet fields (`lanes`, `stage`, `consumes`, `produces`,
  `evidence_required`, `risk_triggers`, `max_overhead`).

Then define the artifact contract:

- output directory and filenames;
- required sections;
- whether an effectiveness log entry is required;
- what downstream skill consumes the output;
- stop conditions.

## Stage 4 - Implementation Shape

Pick the narrowest mechanism that works:

- prompt-only for judgment workflows;
- helper script for deterministic detection, parsing, scaffolding, or
  validation;
- fixtures for anything that should not regress;
- reference files only when they prevent `SKILL.md` from getting bulky.

Use progressive disclosure. If `SKILL.md` approaches 500 lines, split
rarely-read detail into one-level references.

## Stage 5 - Dogfood Plan

Every new skill needs at least one dogfood case before it is considered
healthy:

- one realistic prompt that should invoke it;
- one nearby prompt it must reject or route elsewhere;
- one fixture/report/check that proves the artifact shape;
- one matcher expectation if trigger routing matters;
- one adversarial review pass after the first implementation.

Prefer real host-project tasks over invented examples. If a real task is
too expensive, write a small fixture and state the gap.

## Stage 6 - Build Gate

After implementation, run the smallest meaningful gate set:

```bash
.venv/bin/python scripts/skill_meta.py lint --quiet
.venv/bin/python .claude/skills/which-skill/scripts/match.py "<positive prompt>" --json
.venv/bin/python .claude/skills/which-skill/scripts/match.py "<negative prompt>" --json
```

If the skill declares `evidence_required`, also run
`scripts/evidence_gate.py` against a dogfood report directory. If the
skill has scripts, add or update touched tests and run them.

## Evidence Manifest

```json
{
  "skill": "plan-skill",
  "scan_id": "scan-<TS>",
  "evidence": {
    "skill_problem": "skill-brief.md",
    "trigger_contract": "skill-brief.md",
    "validation_plan": "validation-plan.md",
    "adversarial_review": "adversarial-review.md"
  }
}
```

Then run:

```bash
.venv/bin/python scripts/evidence_gate.py check --skill plan-skill --scan-dir reports/plan-skill/scan-<TS>
```
