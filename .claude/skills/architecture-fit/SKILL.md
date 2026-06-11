---
name: architecture-fit
description: Third skill in the System-tier chain. Reads an `impacted`-status plan, walks the impact map against the decision registry, canonical-patterns, and architectural-smells; surfaces every material fork that needs an ADR (suggests `/decide` candidates inline); fills §5 (Architecture Fit) and §6 (Open Decisions) of the plan. Advances plan status to `architected`. The last judgment pause before promotion to spec.
argument-hint: "<plan-name>  (must already be ai-docs/plans/<name>.md with status=impacted)"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: system
job: plan
best_for: |
  Third stage of System-tier planning — an `impacted`-status plan that
  needs architectural judgment before promotion to spec. Surfaces
  material forks (build vs buy, sync vs async, FK vs enum, new model
  vs extend, new subsystem vs absorb), decision conformance, and
  smells avoided / created.
not_for: |
  Plan with status != impacted (use the matching next-stage skill).
  Authoring an ADR — this skill *recommends* /decide candidates but
  does not write ADRs itself. Implementation (use /refactor-subsystem
  after promotion).
escalate_to: |
  None — handoff is forward to /plan-spec. If a material fork can't
  be resolved by a single ADR (it would need a multi-decision graph),
  the plan stays at `architected` until the user invokes `/decide`
  for each fork; this skill does not create ADRs.
delegate_from: |
  /impact-feature recommends /architecture-fit once §3-4 are filled
  and status is impacted.
language: python
framework: django
---

# /architecture-fit

You are the **orchestrator** for the **third** skill in the System-
tier planning chain. The deliverable is the same plan at
`ai-docs/plans/<name>.md` with §5 (Architecture Fit) and §6 (Open
Decisions) populated and `status: architected`. You do NOT scaffold
the spec — that's `/plan-spec`. You do NOT author ADRs — that's
`/decide`.

This is the final judgment pause before the plan becomes a spec. A
plan that reaches `architected` with unresolved P0 forks in §6 is
expected; `/plan-spec` will require those to be resolved (via
`/decide`) before it will promote.

## Core beliefs

1. **Conformance > novelty.** Default is to follow existing decisions
   and patterns. A new shape is only justified when an existing
   decision is wrong-for-this-case (`/decide --supersede`) or the
   pattern doesn't cover the situation.
2. **Material forks are explicit, not buried.** Every choice with 2+
   defensible answers gets surfaced in §6. The threshold from
   `/decide`: a fork is material if it (a) constrains future work,
   (b) excludes an alternative explicitly, or (c) sets an expiration.
3. **Smells avoided are as load-bearing as patterns followed.** If
   the natural shape of the work would create an omnibus module / a
   stringly-state / a layer violation, §5 says so and §6 records the
   fork "do this anyway and accept the smell" vs "redesign to avoid".
4. **Inline /decide invocations are encouraged.** If you can write
   the ADR Decision sentence right now without speculation, invoke
   `/decide <slug>` inline and capture the assigned id. Otherwise,
   record the fork in §6 with `(decision pending)`.

## Scope (this skill itself)

- **Project root:** this worktree's root.
- **Python:** `python3` (stdlib-only).
- **Read:** `ai-docs/plans/<name>.md`, `ai-docs/decisions/` (full),
  `.claude/docs/canonical-patterns.md`,
  `.claude/docs/architectural-smells.md`.
- **Write:** `ai-docs/plans/<name>.md` (§5-6 + status bump).
- **MAY invoke:** `/decide <slug>` for forks that can be authored
  inline.

## Pipeline

### Stage 0 — Setup

```bash
PLAN_NAME="<arg>"
PLAN_PATH="ai-docs/plans/${PLAN_NAME}.md"
```

Verify plan exists and `status: impacted`. If status is `draft` or
`scoped`, abort and recommend the matching earlier-stage skill. If
status is `architected+`, abort and recommend the next-stage skill.

### Stage 1 — Load constraints

```bash
python3 scripts/decisions.py audit --json
python3 scripts/decisions.py list --json
```

Read `.claude/docs/canonical-patterns.md` and
`.claude/docs/architectural-smells.md` end-to-end. Read every ADR file
under `ai-docs/decisions/` whose `applies_to:` overlaps with the
subsystems in the plan's §3.

### Stage 2 — Walk the impact map

For each touched piece in §3 (subsystem, model, route, service):

- **Decision check.** Is there an ADR that constrains how this can be
  built? If yes, list it; the implementation must conform or the plan
  must include a `/decide --supersede` step.
- **Pattern check.** Does a canonical pattern apply? List the anchor.
  The implementation must follow it.
- **Smell check.** Would the natural shape create a known
  architectural smell? If yes, record the smell name and the
  avoidance strategy.

Build a working list of three columns: `(target, conformance,
smells_to_avoid)`.

### Stage 3 — Identify material forks

For each design decision the implementation will face, classify:

- **Resolved by existing decision.** No fork — record the conformance.
- **Resolved by pattern.** No fork — record the pattern anchor.
- **Material fork — can author inline.** You can write the ADR's
  Decision sentence right now without speculation. Invoke
  `/decide <slug>` and capture the assigned id; add the id to §5
  conformance.
- **Material fork — pending.** Needs more investigation, prototype,
  or stakeholder input. Add to §6 as `(decision pending)`. If 2+
  alternatives are defensible and the cost of being wrong is high,
  recommend `/design-it-twice <fork-slug>` in the §6 entry — it spawns
  3 divergent designers and produces a comparative analysis you can
  feed into `/decide` later.
- **Material fork — supersedes existing.** The natural answer
  contradicts an existing decision. Surface to user; the resolution
  is either (a) `/decide --supersede NNNN`, (b) drop the work that
  caused the conflict (re-run `/scope-feature`), or (c) take an
  exception (record in §5).

### Stage 4 — Write §5-6 of the plan

Edit `${PLAN_PATH}` to fill §5 (Architecture Fit) and §6 (Open
Decisions) from the working list:

```markdown
## 5. Architecture Fit

**Decision conformance.**
- ADR `NNNN` (`<title>`) — _how the implementation conforms_
- ADR `NNNN` (`<title>`) — _exception with one-line justification_

**Pattern alignment.**
- `<anchor>` — _where in the implementation this lands_

**Smells avoided.**
- `<smell-name>` — _avoidance strategy_

**Smells accepted (with justification).**
- `<smell-name>` — _why we accept it (link to §6 fork if pending)_

## 6. Open Decisions

_Material forks not yet resolved. Each blocks `/plan-spec` until
either authored as an ADR or explicitly waived._

**P0 — must resolve before promotion.**
- `<fork-name>` — _alternatives_; _recommended `/decide` slug_

**P1 — should resolve before implementation.**
- `<fork-name>` — _alternatives_; _can be deferred to `/refactor-subsystem`_

**Authored inline.**
- ADR `NNNN` (`<title>`) — _written during this run_
```

### Stage 5 — Advance status

Edit the frontmatter `status:` line to `architected`.

```bash
python3 scripts/plans.py audit
```

### Stage 6 — Summarize

Report to the user in ≤10 lines:

- Path to the plan.
- ADRs conformed-to (count by id).
- Patterns aligned (count by anchor).
- Smells avoided (count) and accepted-with-justification (count).
- ADRs authored inline this run (ids).
- Open P0 forks count + names — these BLOCK `/plan-spec`.
- Open P1 forks count.
- Recommended next command:
  - If P0 forks exist: `/decide <slug>` for each, then
    `/plan-spec <plan-name>`.
  - If clean: `/plan-spec <plan-name>` directly.

## Non-goals

- Authoring ADRs as a side effect — `/decide` is the only way (this
  skill MAY invoke `/decide` inline but never writes to
  `ai-docs/decisions/` directly).
- Scaffolding the spec (that's `/plan-spec`).
- Editing canonical-patterns.md or architectural-smells.md.
- Implementing the feature.

## When things go sideways

| Symptom | Action |
|---|---|
| Plan status is not `impacted` | Abort; recommend the matching stage skill |
| §3 impact map is empty or "MISSING" | Abort; recommend re-running `/impact-feature` to fill the gap |
| A fork would supersede an existing decision | Stop; surface conflict to user; resolution is `/decide --supersede` or re-scope |
| User invokes `/decide` inline but it fails | Record the fork as P0 pending in §6; do not block plan progression |
| Every fork is P0 with 5+ candidates | Plan may be too ambitious — recommend re-running `/scope-feature` to narrow before continuing |
| No applicable patterns / decisions / smells | Note "no constraining priors" in §5; this is fine for greenfield work but worth flagging |
