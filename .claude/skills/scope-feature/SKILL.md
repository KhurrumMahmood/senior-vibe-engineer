---
name: scope-feature
description: First skill in the System-tier chain. Scaffolds an `ai-docs/plans/<name>.md` plan if needed, reads decisions / canonical-patterns / smells, then drives clarifying questions to fill §1 (Scope & Bounds) and §2 (Success Criteria) of the plan. Advances plan status to `scoped`. Designed for System-tier work — new subsystems, cross-subsystem features, multi-week initiatives — where the judgment pause between scoping and impact analysis is the whole point.
argument-hint: "<plan-name>  (kebab-case slug, becomes ai-docs/plans/<name>.md)"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: system
job: plan
best_for: |
  System-tier work — a new subsystem, a feature crossing 2+ workflows,
  or a multi-week initiative where the scoping pause must happen
  BEFORE any impact analysis. Examples: "build a new ingestion
  pipeline for X", "merge the A and B workflows into one", "extract
  the Y subsystem from the omnibus module".
not_for: |
  Feature-tier work that touches one workflow / 1-3 day scope (use
  /plan-feature). Bug fixes (use /fix-workflow). Trivial changes
  (proceed directly; use /decide if a real choice is being made).
  Authoring an ADR (use /decide).
escalate_to: |
  None — this is the first skill in the System-tier chain. Escalation
  is only relevant in the opposite direction: if /scope-feature reveals
  the work is actually Feature-tier (one workflow, 1-3 days), abandon
  the plan and recommend /plan-feature instead.
delegate_from: |
  /which-skill recommends /scope-feature when the task description
  matches System-tier signals (cross-subsystem, "new ...", "merge X
  and Y", "extract Z").
language: python
framework: django
---

# /scope-feature

You are the **orchestrator** for the **first** skill in the System-tier
planning chain (`/scope-feature` → `/impact-feature` →
`/architecture-fit` → `/plan-spec`). The deliverable is a plan at
`ai-docs/plans/<name>.md` with §1 (Scope & Bounds) and §2 (Success
Criteria) populated and `status: scoped`. You do NOT do impact
analysis — that's the next skill's job. You do NOT implement the
feature.

The judgment pause between this skill and `/impact-feature` is the
whole point of the System tier. A scoping conversation that surfaces a
narrower-than-expected scope, a wrong-tool diagnosis, or a missing
prerequisite is a successful run, not a failed one.

## Core beliefs

1. **Scope is contract, not aspiration.** "What's in / out / non-goal"
   must be specific enough that a sub-agent two months from now can
   tell whether a proposed change is in-scope. Vague scope yields
   scope creep.
2. **Success criteria are observable.** "Faster crawls" is not a
   success criterion; "p95 crawl latency drops below 30s on a fixture
   set of 50 sites" is.
3. **Tier-wrong is a real outcome.** If the conversation reveals the
   work is actually Feature-tier (single workflow, 1-3 day scope) or
   Quick-tier (one-line fix), abandon the plan and route to the right
   skill. The cost of a wrong tier is much higher than the cost of
   redirecting now.
4. **Decisions and smells constrain scope before they constrain
   implementation.** A material fork that would violate an existing
   decision narrows scope (we already chose); a smell to avoid narrows
   scope (we know that shape doesn't fit).

## Scope (this skill itself)

- **Project root:** this worktree's root.
- **Python:** `python3` (stdlib-only).
- **Read:** `ai-docs/decisions/`, `.claude/docs/canonical-patterns.md`,
  `.claude/docs/architectural-smells.md`,
  `.claude/docs/subsystems/` (file list only — full reads in /impact-feature).
- **Write:** `ai-docs/plans/<name>.md` (scaffold + §1-2 + status bump).

## Pipeline

### Stage 0 — Setup

```bash
PLAN_NAME="<arg>"
PLAN_PATH="ai-docs/plans/${PLAN_NAME}.md"
```

If the plan does not exist, scaffold it:

```bash
python3 scripts/plans.py init "${PLAN_NAME}"
```

If the plan exists with `status` other than `draft` or `scoped`, abort
and tell the user to use `/impact-feature`, `/architecture-fit`, or
`/plan-spec` for the next stage.

### Stage 1 — Read priors

Load the constraint context:

```bash
python3 scripts/decisions.py audit --json
python3 scripts/decisions.py list --json
ls .claude/docs/subsystems/
```

Read `.claude/docs/canonical-patterns.md` and
`.claude/docs/architectural-smells.md` end-to-end. These are the law-as-
stated; scope must respect them.

### Stage 2 — Drive scoping conversation

Pose the user the following questions in order. Stop after each round
and wait for the answer; do not invent answers.

**For structure-redesign work** (project topology, package
boundaries, multi-app split, framework migration), read
`knowledge/structure-redesign-lessons.md` before Q1 — it adds a
two-zone framing prompt, a latent-design-choice checklist for Q2,
and specific success-criteria patterns for Q5.

1. **One-sentence problem statement.** "Right now, X happens / does
   not happen, and that costs Y." If the user can't write this in one
   sentence, the work is too vague — push back.
2. **In-scope.** What changes belong inside this initiative? List
   concrete artifacts: subsystems, models, routes, services, docs.

   **Once Q2 is answered, kick off background exploration before
   asking Q3.** You now know roughly which subsystems the work
   touches; fire an `Explore` sub-agent in parallel to survey them
   while the rest of the clarification continues. The point is to
   surface unknown unknowns (recent activity in the area, an
   in-progress migration, an undocumented feature flag, a related
   smell) before you write §1, not after.

   ```
   Agent({
     description: "Background scope exploration for <plan-name>",
     subagent_type: "Explore",
     prompt: "Survey these subsystems in the host project repo: <Q2 answers>.
       Look for: recent activity (git log last 30 days), undocumented
       feature flags or overrides, in-progress migrations, related
       work mentioned in commit messages, smells from
       .claude/docs/architectural-smells.md that already have a
       foothold here. Write findings to
       reports/scope-feature/scan-<TS>/exploration.md. Under 300
       words. Bullet form. Do NOT propose changes — surface only.",
     run_in_background: true
   })
   ```

   Do not wait for it. Proceed with Q3.

3. **Out-of-scope.** What is adjacent / tempting / could land along
   with this, but is explicitly NOT part of this initiative? (Empty
   out-of-scope is a smell — there is always something nearby.)
4. **Non-goals.** What this initiative is NOT trying to be. (Different
   from out-of-scope: non-goals are about purpose, out-of-scope is
   about artifacts. "Not a redesign" is a non-goal; "the email
   templates" is out-of-scope.)
5. **Success criteria.** Three to five observable outcomes. Push for
   specificity — numbers, fixtures, before/after metrics. Reject
   "feels better" / "is cleaner".
6. **Tier check.** Re-read the user's answers. Does this look
   System-tier (cross-subsystem, multi-week, new subsystem) or has it
   actually shrunk to Feature-tier? If Feature-tier — STOP, recommend
   `/plan-feature` instead, mark plan `abandoned`.

### Stage 3 — Apply prior constraints

By now the background `Explore` from Stage 2 (Q2 hook) should have
returned. Read its output at
`reports/scope-feature/scan-<TS>/exploration.md` and incorporate its
findings into the constraint check below — especially anything it
flagged about recent activity, undocumented overrides, or smells with
a foothold in the area. If the file doesn't exist (Explore still
running, or it failed), proceed without it and note "background
exploration unavailable" in the §1 **Prior constraints** subsection so
the next-stage skill knows to re-survey.

For each in-scope item, check:

- Does an existing **decision** (ADR) constrain how this can be
  built? (List ids.)
- Does a **canonical pattern** apply? (List anchor names.)
- Does an **architectural smell** describe a shape we must avoid?
  (List names.)
- Did the background **Explore** surface anything new? (Recent
  activity, hidden state, in-progress work — list and resolve before
  Stage 4.)

Surface conflicts to the user before writing the plan. If an in-scope
item would violate an existing decision, the choice is either:
(a) supersede the decision via `/decide --supersede`, (b) drop the
item from scope, or (c) explicitly take an exception (record in §6
later, in `/architecture-fit`).

### Stage 4 — Write §1-2 of the plan

Edit `${PLAN_PATH}` to fill §1 (Scope & Bounds) and §2 (Success
Criteria) with the user's answers and the prior-constraint cross-
references. Use this shape:

```markdown
## 1. Scope & Bounds

**Problem.** _One-sentence problem statement._

**In scope.**
- _Concrete artifact 1_
- _Concrete artifact 2_

**Out of scope.**
- _Adjacent thing not in this initiative_

**Non-goals.**
- _Purpose this initiative is NOT trying to serve_

**Prior constraints.**
- Decision NNNN — _how it constrains the work_
- Pattern `<anchor>` — _how it shapes the integration_
- Smell `<name>` — _what shape to avoid_

## 2. Success Criteria

- _Observable outcome 1 (with metric / fixture)_
- _Observable outcome 2_
- _Observable outcome 3_
```

### Stage 5 — Advance status

Edit `${PLAN_PATH}` to set `status: scoped` (in-place, single
`status:` line in frontmatter).

```bash
python3 scripts/plans.py audit
```

Confirm the plan loads cleanly.

### Stage 6 — Summarize

Report to the user in ≤8 lines:

- Path to the plan (`ai-docs/plans/<name>.md`).
- One-line problem statement.
- In-scope count, out-of-scope count, success-criteria count.
- Active decisions / patterns / smells touched.
- Recommended next command:
  - Normal case: `/impact-feature <name>`.
  - Tier shrunk: `/plan-feature <name>` — plan was abandoned.
  - Decision conflict: `/decide --supersede NNNN` first, then
    `/impact-feature <name>`.

## Non-goals

- Doing impact analysis (that's `/impact-feature`).
- Authoring decisions (that's `/decide`).
- Implementing the feature (that's `/refactor-subsystem` after the
  spec is promoted).
- Editing canonical-patterns.md or architectural-smells.md.

## When things go sideways

| Symptom | Action |
|---|---|
| Plan already exists with `status: impacted+` | Abort; recommend the next-stage skill matching current status |
| User can't write a one-sentence problem statement | Push back; the work is too vague to scope — recommend a `/map-subsystem` or `/explain-code` pass first |
| Out-of-scope list is empty | Push back — there is always something nearby; ask for one item |
| Success criteria are not observable | Push back round-by-round until each is measurable |
| Scope has shrunk to Feature-tier | Mark plan `abandoned`, recommend `/plan-feature` |
| In-scope item conflicts with an existing decision | Stop, surface conflict, ask user to decide (supersede / drop / exception) BEFORE writing the plan |
