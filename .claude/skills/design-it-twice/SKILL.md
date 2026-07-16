---
name: design-it-twice
description: Resolve a material design fork by parallel-divergent fan-out — spawn 3 designer sub-agents with deliberately different binding constraints, then synthesize a comparative analysis with a recommendation. Use when a P0 fork from /architecture-fit (or any planning skill) has 2+ defensible answers and the cost of being wrong is high relative to the cost of fanning out. Writes one comparative-design document under reports/design-it-twice/scan-<TS>/; does NOT author the ADR — /decide is the downstream step.
argument-hint: "<fork-slug>  (with a 1-paragraph fork description via stdin or follow-up)"
allowed-tools: Bash, Read, Write, Edit, Agent
user-invocable: true
tier: cross-cutting
job: decide
best_for: |
  A material design fork (architecture, interface shape, data model,
  build vs buy, sync vs async, FK vs enum) where (a) 2+ alternatives
  are defensible, (b) you can't write the ADR Decision sentence yet
  without speculation, and (c) being wrong means rewriting later.
  The classic surfacing path is a P0 fork in §6 of an `architected`-
  status plan from `/architecture-fit`.
not_for: |
  Forks with an obvious answer (just commit; don't pay the fan-out
  cost). Implementation strategy questions inside an already-resolved
  choice (use /plan-spec). Forks already covered by an existing decision
  record (read it; if it's wrong-for-this-case, use /decide --supersede).
  Trivial preferences with no future-binding effect.
escalate_to: |
  /decide <slug> — once the comparative analysis is written, the
  natural next move is to author the ADR with the analysis as evidence.
  If the fan-out reveals a third option no axis explored, re-run with
  the new axis triplet.
delegate_from: |
  /architecture-fit recommends this when a P0 material fork surfaces
  in §6 that can't be authored inline via /decide. /scope-feature or
  /plan-feature may also recommend it for forks discovered earlier.
language: any
framework: any
scout_model: careful
---

# /design-it-twice

_Pattern inspired by [mattpocock/skills](https://github.com/mattpocock/skills)
("design-it-twice"). Adapted to this ecosystem's planning-skill chain (handoff
from `/architecture-fit`, output as evidence for `/decide`)._

You are the **orchestrator** for a parallel-divergent design
exploration. The deliverable is a comparative-design document at
`reports/design-it-twice/scan-<TS>/<fork-slug>.md` that summarizes 3
deliberately divergent designs, names where they agreed, names where
they diverged, and recommends an axis with a stated trade.

You do NOT author the ADR — that's `/decide`. You do NOT implement
the design — that's the planning chain after the ADR lands.

## How success is judged

- Three designs exist under `reports/design-it-twice/scan-<TS>/`, each
  committed hard to a genuinely different binding constraint — three
  near-identical "balanced" designs is a failed run.
- The comparative document at `<fork-slug>.md` separates where the
  designs agreed (real constraints) from where they diverged (the
  actual design space), and recommends an axis with the trade named.
- The chosen axes are stated and justified in the Stage 1 section.
- No ADR authored, nothing written outside the scan dir — the handoff
  is `/decide <slug>` with this analysis as evidence.
Write toward these gates from Stage 0.

## Core beliefs

1. **Divergence is the point.** Each design must commit hard to its
   binding constraint. A "balanced" design from each agent defeats
   the purpose — you want the pure form of each axis so the trade is
   visible. Soft-pedaling the constraint produces three near-identical
   designs and zero signal.
2. **Synthesis > individual design.** No single design is "the
   answer". The output is the comparative analysis: where they agreed
   (the real constraints — the fork is *not* about these), where they
   diverged (the design space — the fork *is* about these), and a
   recommendation with the trade named.
3. **Cheap to fan out, expensive to redo.** This skill exists because
   parallel design exploration costs ~3 sub-agent runs and ~30 min of
   orchestrator time, while a wrong design choice costs weeks of
   rework. Don't use it for trivial forks. Do use it when "we'll find
   out if this was right by rewriting it later."
4. **Judgment-tier sub-agents, not cheap scouts.** The fan-out uses
   the `Agent` tool with `subagent_type: general-purpose` (Sonnet-
   tier) — design work needs judgment, not read-and-classify. Do not
   use `dispatch_scout_cheap.sh` for these designers; that wrapper is
   for read-only classification fan-out.

## Scope (this skill itself)

- **Project root:** this worktree's root.
- **Read:** the fork description (from stdin or follow-up), any plan
  the fork came from, `CONTEXT.md`, `.claude/docs/canonical-patterns.md`,
  `.claude/docs/architectural-smells.md`, and ADRs whose `applies_to:`
  overlaps the fork's subsystem.
- **Write:** ONLY under `reports/design-it-twice/scan-<TS>/` (3 design
  files + 1 comparative analysis).
- **MAY invoke:** `Agent` tool with `subagent_type: general-purpose`,
  3 in parallel for the design fan-out.

## Pipeline

### Stage 0 — Confirm the fork is well-defined

Before spending sub-agent time, the orchestrator must have:

1. A 1-paragraph fork description (what's being decided).
2. The constraints in tension (what makes it a real fork — e.g. "easy
   to learn vs covers all cases", "throughput vs latency", "build now
   vs buy time").
3. 2+ defensible alternatives (named, not vague).

If any of those are missing, **abort** and ask the user to clarify.
Don't fan out 3 designers against a vague prompt — they'll diverge on
*interpretation* of the prompt, not on the design axis.

```bash
TS="$(date +%Y%m%d-%H%M%S)"
FORK_SLUG="<arg>"
SCAN_DIR="reports/design-it-twice/scan-${TS}"
mkdir -p "${SCAN_DIR}"
```

### Stage 1 — Pick the divergence axes

Identify 3 axes that capture the real tradeoff space for *this
specific fork*. Some defaults to consider:

| Fork shape | Axes |
|---|---|
| Interface design | minimize-interface / maximize-flexibility / optimize-common-case |
| Build vs buy | cost-minimize / time-minimize / control-maximize |
| Data shape | normalize-aggressively / denormalize-for-read / optimize-write-throughput |
| Coupling | decouple-aggressively / pragmatic-coupling / domain-cohesion |
| Sync vs async | latency-minimize / throughput-maximize / observability-maximize |
| FK vs enum vs string | type-safety-maximize / flexibility-maximize / migration-cost-minimize |

If none of these triplets fit, write your own three axes that capture
the real tension. State the chosen axes (and why) in the report's
Stage 1 section so the synthesis is grounded — a reader should be able
to ask "would axis X have produced a different design?" and see why
you didn't pick it.

**Bad axes** (defeat the purpose):
- "good design" / "great design" / "excellent design" — no divergence.
- Three variations of the same axis — no divergence.
- Axes the codebase already constrains (e.g. "use the standard repository
  abstraction" vs "issue raw queries" after the project has standardized
  on the repository) — not actually a fork.

### Stage 2 — Fan out 3 designers

Spawn 3 sub-agents **in parallel** via the `Agent` tool. Each gets a
self-contained brief (sub-agents don't inherit your context):

```
You are designer N of 3 for a parallel-divergent design exploration.
Your binding constraint: <axis name>. This means: <1-line interpretation
of the axis for this specific fork>.

The fork: <1-paragraph description>

Repo conventions to honor:
- /CONTEXT.md (domain glossary)
- .claude/docs/canonical-patterns.md (existing patterns)
- .claude/docs/architectural-smells.md (smells to avoid)
- ADRs under ai-docs/decisions/ that apply to <subsystem>

Your job: produce a 1-page design that commits HARD to your axis. Do
not produce a balanced compromise — that's not your job. Other agents
are exploring different axes; the orchestrator will synthesize.

Output: write your design to `${SCAN_DIR}/design-axisN-<axis-slug>.md`
with sections:

  ## Design
  <interfaces, data shapes, flow — concrete enough to implement>

  ## Strengths under this axis
  - 3 bullets — where committing to <axis> makes this design good

  ## Weaknesses where this axis hurts
  - 3 bullets — where committing to <axis> makes this design bad

  ## What you'd change if asked to soften the axis
  - 1-2 bullets — what trade you'd make to recover one of the weaknesses

Keep it ≤1 page. Concreteness > comprehensiveness.
```

Three sub-agents, three separate `Agent` calls in the same message
(parallel). Wait for all three before proceeding.

### Stage 3 — Synthesize

Read all 3 designs. Write the comparative analysis at
`${SCAN_DIR}/<fork-slug>.md`:

```markdown
# Design It Twice: <fork-slug>

## Fork
<1-paragraph description, verbatim from Stage 0>

## Divergence axes
- **Axis 1: <name>** — what it optimizes for
- **Axis 2: <name>** — what it optimizes for
- **Axis 3: <name>** — what it optimizes for

(_Why these three: <1-2 sentences on why this triplet captures the
real tension; what other axes were considered and skipped._)

## Designs
- [Design 1: <axis 1 name>](design-axis1-<slug>.md)
- [Design 2: <axis 2 name>](design-axis2-<slug>.md)
- [Design 3: <axis 3 name>](design-axis3-<slug>.md)

## Where they agreed
_These are the real constraints. The fork is **not** about these — they
were going to land the same way regardless of axis._
- <bullet>
- <bullet>

## Where they diverged
_This is the design space. The fork **is** about these._
- <bullet — what each design did differently and why their axis forced
  it>

## Recommendation
**Axis: <chosen axis>**. <2-3 sentences on why this axis wins for this
specific fork in this specific codebase, and what trade you're
accepting.>

## Not chosen — why
- **<axis 2>**: <1 sentence on the deal-breaker for this fork>
- **<axis 3>**: <1 sentence on the deal-breaker for this fork>

## Hand-off
Next: `/decide <fork-slug>` with this analysis as the Context section
of the ADR. The Decision sentence writes itself from the
Recommendation above.
```

### Stage 4 — Hand off

Report to the user in ≤8 lines:

- Path to the comparative analysis.
- The 3 axes explored.
- The recommended axis (1 sentence why).
- Top 2 agreements (the real constraints — not the fork).
- Top 2 disagreements (the design space — the fork).
- Recommended next command: `/decide <fork-slug>` with the analysis
  as evidence.

## Non-goals

- Authoring the ADR (that's `/decide`).
- Implementing the design (that's the planning chain after `/decide`).
- More than 3 designers by default — fan out to 4-5 only if the user
  explicitly asks. Synthesis cost grows superlinearly; 3 is the sweet
  spot for "see the trade".
- Choosing axes that don't actually diverge (defeats the purpose).
- Using cheap-scout dispatch for the designers — design work is
  judgment, not read-and-classify. Use `Agent` with
  `subagent_type: general-purpose`.
- Writing the analysis without reading all 3 designs first. The
  synthesis IS the value; skipping it produces a document that just
  rehashes one design.

## When things go sideways

| Symptom | Action |
|---|---|
| Fork description is vague or has only 1 defensible answer | Abort; ask user to clarify, or skip this skill entirely |
| Two of the 3 designs converged on the same shape | Axes weren't actually divergent for this fork — pick a different triplet and re-fan |
| All 3 designs were rejected by you on read | Synthesize anyway — the rejection rationale IS the analysis. The output is "none of these; here's what we learned about the constraints" |
| Sub-agents need codebase context to design | Pass relevant SKILL.md / canonical-patterns / impact-map paths in the brief; don't expect them to grep the whole repo themselves |
| The recommended axis matches what you'd have picked without fan-out | Still useful — the synthesis named the trade explicitly, which the ADR will need anyway |
| Fan-out produces 3 designs that all violate an existing ADR | Stop; the fork is masking a `/decide --supersede` question. Surface it; don't recommend an axis |
