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

## How success is judged

The frontmatter's `evidence_required` list IS the verdict — the run
passes when `evidence.json` satisfies `scripts/evidence_gate.py` on all
four items:

- `skill_problem` — Stage 1's one-sentence problem class, with a
  durable artifact named (or a recommendation against the skill).
- `trigger_contract` — Stage 3 frontmatter draft with `best_for` /
  `not_for` naming adjacent skills.
- `validation_plan` — `validation-plan.md` with at least one dogfood
  case and its commands.
- `adversarial_review` — `adversarial-review.md` recording Stage 2's
  seven attacks and the accepted/rejected objections.
Write toward these gates from Stage 1.

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

Answer the placement decision at this stage, before body prose:

Which shipping layer owns the concept, and if the content is
language/framework-flavored, why is this concept+binding rather than native?
If domain is proposed, name at least three cohesive members.

Use a registered layer and primary binding from
`_common/capability-registry.yml`. A language, framework, or host shipping
contract may be a valid singleton; a domain cohesion folder requires at least
three members. Record catalog readiness separately from capability support:
`deferred-to-wp8` and `inventory-only` describe migration state and never imply
`capability_contract`, `experimental`, or `verified` support. Do not promote a
row merely to make the new skill appear portable.

Two contract rules, both learned from execution failures:

- **Declared verdict.** The skill body opens with a compact "How
  success is judged" block naming the gates the executor will face.
  Executors optimize toward announced verdicts; a gate revealed only
  at the end shapes nothing.
- **Load-bearing or delete.** Every mandated verification or
  reporting stage names its consumer (a later stage, the reply
  contract, or a gate). A stage whose output nothing consumes gets
  skipped under load at ~100% — wire it or remove it. Likewise,
  "read X" instructions need an un-fakeable acknowledgment (one line
  that cannot be written without the read), and gates must test the
  artifact's property, never just its existence.

## Stage 4 - Implementation Shape

Pick the narrowest mechanism that works:

- prompt-only for judgment workflows;
- helper script for deterministic detection, parsing, scaffolding, or
  validation;
- fixtures for anything that should not regress;
- reference files only when they prevent `SKILL.md` from getting bulky.

Use progressive disclosure. If `SKILL.md` approaches 500 lines, split
rarely-read detail into one-level references.

Contracts must be executable as written, on hosts the skill was not
written on:

- a sub-agent dispatch names an agent type that can actually produce
  the demanded outputs (a read-only type cannot satisfy a
  write-three-files contract), and its allowed-tool list includes
  what the outputs require;
- template placeholders state their fallbacks (detached HEAD, no
  venv, no branch);
- "always in scope" convention sources state an absence fallback —
  host-adapter slots must cover total absence, not just substitution,
  and worked examples naming origin-project helpers are marked as
  illustration so they cannot be harvested as false rules.

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

For execution-heavy skills, the binding dogfood is a **real-host run**:
execute the skill against a codebase it was not written on, under
hostile-but-realistic conditions (missing convention docs, no venv,
detached HEAD, commits forbidden). Scenario probes and document review
both miss the unexecutable-against-reality defect class by
construction. The dogfood log — each friction citing the text it was
following, each fix, and the scenario that should now pass — is the
skill's replay case; keep it.

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

For a **material revision** of an existing skill, the gate set is the
repair loop (see `/repair-skill`): frame review against the rubric, a
scout that verifies the review's claims before any edit, an
independent non-context-sharing verifier after, and an A/B probe at
the headline defect site at the weakest supported model tier. When
judging probes, score the grounding, not just the behavior — an
executor can produce the right behavior while citing mandates that do
not exist, which inflates the old-condition score and hides
brittleness.

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
