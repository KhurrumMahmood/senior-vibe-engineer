---
name: plan-feature
description: Plan a Feature-tier change (1-3 day scope, touches one workflow, needs impact analysis but not new subsystem). Reads subsystem/workflow docs, canonical patterns, architectural smells, and the decision registry; fans out scouts per touched subsystem to map call sites, model touchpoints, and behaviors-to-preserve; surfaces decision stubs for material forks; and scaffolds a proposed-lifecycle spec under `ai-docs/specs/<feature-name>.md` so implementation work can resume from the spec.
argument-hint: "<feature-name> [--subsystems <a,b,c>] [--force]"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: feature
job: plan
best_for: |
  Cross-cutting feature, 1-3 day scope, touches one workflow, needs
  impact assessment but not a new subsystem. Examples: "expose a new
  field on the export", "add a per-site override for the X behavior",
  "wire up the Y pipeline to the existing Z trigger".
not_for: |
  Bug fixes (use /fix-workflow). New subsystems or 2+ workflows (use
  the System-tier chain when it ships: /scope-feature → /impact-feature
  → /architecture-fit → /plan-spec). Trivial changes — one-line fixes,
  field renames, expose-existing-data — proceed directly and use
  /decide if a real choice is being made. If you're not sure of scope,
  ask /which-skill first.
escalate_to: |
  /scope-feature when impact analysis surfaces 2+ subsystems or a new
  domain. The signal: more than one subsystem doc gets opened in
  Stage 1, or the scout reports "no clean integration point exists in
  any current service".
delegate_from: |
  /which-skill recommends /plan-feature when task description matches
  feature-tier signals (single workflow, cross-file, "add" / "expose"
  / "wire up").
language: any
framework: any
scout_model: careful
---

# /plan-feature

You are the **orchestrator** for a Feature-tier plan. The deliverable
is a populated `draft` spec with `lifecycle: proposed` at
`ai-docs/specs/<feature-name>.md` that
implementation work (`/refactor-subsystem`, manual edits, or a future
`/build-feature`) can resume from. You produce the spec; you do NOT
implement the feature.

The four-stage shape (Setup → Impact map → Decision stubs → Spec
scaffold) mirrors `/find-omnibus` but at planning time rather than
audit time. Scouts handle per-subsystem reachability; the orchestrator
synthesizes the cross-subsystem story and decision graph.

You do NOT edit production code in this skill. The only artifacts you
write are:
- `reports/plan-feature/scan-<TS>/impact.md` — the cross-subsystem
  impact synthesis
- `reports/plan-feature/scan-<TS>/scout/<subsystem>.md` — per-subsystem
  scout outputs (findings + extracted-behaviors)
- `ai-docs/specs/<feature-name>.md` — the spec (status: draft after
  fill, lifecycle: proposed, motivating_decision: linked if any)
- One line in `reports/_meta/effectiveness.jsonl`

## How success is judged

- The spec's sections are grounded in `${REPORT_DIR}/context.md`, the
  per-subsystem `scout/<subsystem>.md` outputs, and `impact.md` — a
  transcription of evidence, never an invention.
- Behaviors-to-preserve from the scouts' extracted-behaviors are
  carried into the spec as the contract the feature must respect.
- Every material fork has a decision stub: a `/decide` invocation or
  a `motivating_decision` placeholder — no buried choices.
- Impact crossing 2+ workflows triggers escalation to the System-tier
  chain instead of a widened spec.
Write toward these gates from Stage 0.

## Core beliefs

1. **The spec is the deliverable.** Implementation is downstream. A
   plan that doesn't yield a spec leaves no audit trail and forces the
   next agent to re-derive the impact map from scratch.
2. **Decision stubs > buried choices.** Every material fork (build vs
   buy, sync vs async, FK vs enum, new model vs extend existing) gets
   either a `/decide` invocation (if standalone) or a placeholder line
   in the spec's `motivating_decision` slot. Buried choices in
   implementation become future archaeology.
3. **Behaviors-to-preserve are load-bearing.** Implicit invariants
   (the order of two `.save()` calls, the fact that `task.delay` runs
   on the browser queue, the route's `LoginRequiredMixin`) must be
   captured before the feature touches the surrounding code. The
   scout's `extracted-behaviors.md` is the contract the new feature
   must respect.
4. **One workflow, one feature.** If impact analysis surfaces work
   across two or more workflows, ESCALATE to the System-tier chain.
   Don't widen `/plan-feature`'s scope — the System tier exists for
   exactly this case.
5. **Reuse over invention.** If `.claude/docs/subsystems/<name>.md`
   already documents the integration point, point at it; don't re-
   document. The spec carries deltas, not duplications.

## Scope

- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` for `scripts/specs.py`,
  `scripts/decisions.py`, and `scripts/log_effectiveness.py` (they use
  the repo dependency set even though this skill is read-only against
  production code).
- **Worktree guard:** none required — read-only against the codebase,
  writes only to `reports/plan-feature/` and `ai-docs/specs/`.
- **project-specific defaults** (subsystem naming map, default scout
  budget per subsystem, well-known integration points): in
  `knowledge/` — scouts read it, you don't.

## Argument parsing

Single positional argument: `<feature-name>` — kebab-case slug used as
the spec id and report directory name. Examples:
`export-ttl-override`, `import-dedupe`,
`crawl-job-pause-resume`.

Optional `--subsystems <a,b,c>` — comma-separated subsystem doc names
under `.claude/docs/subsystems/`. If omitted, the orchestrator infers
the candidate subsystems from the feature name and asks the user to
confirm before fanning out scouts (the inference is intentionally
shallow — confirm-before-dispatch is the gate that keeps the scout
budget honest).

Optional `--force` — pass through to `scripts/specs.py init --force`.
Use it only after deciding whether the existing
`ai-docs/specs/<name>.md` should be superseded or extended. If the
feature-name slug already exists and `--force` was not provided, abort
and recommend the user re-run with `--force` only after that decision.

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed. **Post:** `${REPORT_DIR}` exists, `latest`
symlink updated, candidate subsystem list confirmed with user.

```bash
FEATURE_NAME="<feature-name>"
FORCE_FLAG=""  # set to "--force" only when the user passed /plan-feature --force
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/plan-feature/scan-${TS}"
mkdir -p "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/plan-feature/latest
```

If `--subsystems` was not provided:

```bash
ls .claude/docs/subsystems/ | sed 's/\.md$//'
```

Pick 1-3 candidates whose names overlap with the feature slug; present
them and wait for user approval. Approval token contract matches
`/extract-enum` (`approved` / `approve` / `go` / `lgtm` / `proceed` /
`yes`).

### Stage 0.5 — Background exploration (parallel, do not wait)

Once subsystems are confirmed, fire an `Explore` sub-agent in the
background as a cross-cutting safety net. It runs in parallel with
Stages 1-2 and returns by Stage 3 (Synthesize) — its job is to find
things the per-subsystem scouts in Stage 2 won't see (cross-subsystem
activity, adjacent in-progress work, undocumented overrides).

```
Agent({
  description: "Background exploration for <feature-name>",
  subagent_type: "Explore",
  prompt: "Survey the host project repo for cross-cutting context around the
    `<feature-name>` feature, which is expected to touch:
    <subsystems>. Look for: recent activity (git log last 30 days)
    anywhere those subsystems are imported from, undocumented feature
    flags / GlobalSettings overrides / SiteConfig knobs in
    play, in-progress migrations or scaffolds, related but-not-named
    work in adjacent subsystems. Do NOT analyze the named subsystems
    themselves — the scout fan-out in Stage 2 covers those. Write
    findings to ${REPORT_DIR}/exploration.md. Your output will be judged
    by whether that file names cross-subsystem risks and undocumented
    constraints the per-subsystem scouts would miss, with evidence
    paths rather than claims. Under 400 words. Bullet form. Surface only
    — no recommendations.",
  run_in_background: true
})
```

Do NOT wait for it. Continue to Stage 1.

### Stage 1 — Read context

**Pre:** subsystems confirmed. **Post:** `${REPORT_DIR}/context.md`
written summarizing what's already documented, what decisions
constrain the work, and what smells/patterns apply.

Read in this order (skip any missing file gracefully):

```bash
# Per touched subsystem
for sub in ${SUBSYSTEMS}; do
    cat ".claude/docs/subsystems/${sub}.md" 2>/dev/null
    cat ".claude/docs/workflows/${sub}.md" 2>/dev/null  # may not exist
done

# Cross-cutting
cat .claude/docs/canonical-patterns.md
cat .claude/docs/architectural-smells.md

# Decision registry
.venv/bin/python scripts/decisions.py list --json
.venv/bin/python scripts/decisions.py audit --json
```

Write `${REPORT_DIR}/context.md` summarizing:
- Per-subsystem: 3-5 bullets about current responsibility, integration
  points, recent changes (from the doc).
- Applicable decisions (by id + title) — these are the constraints the
  spec must respect.
- Applicable patterns (by anchor) — the "law as stated" the
  implementation must follow.
- Applicable smells — what to actively avoid.

This context is the orchestrator's working memory for Stages 2-4.

### Stage 2 — Impact map (scout fan-out)

**Pre:** context.md exists. **Post:**
`${REPORT_DIR}/scout/<subsystem>.md` for each subsystem (one scout
per subsystem; up to 3 in parallel).

Dispatch one scout per touched subsystem using the brief at
`agents/impact-scout.md`. Each scout returns a single markdown file
with two sections:

- `## Findings` — call sites, model touchpoints, route boundaries,
  test surfaces. The "where would this feature land?"
- `## Extracted behaviors` — invariants the new feature must preserve
  (load-bearing `.save()` order, queue pinning, mixin requirements,
  signal handlers, side-effects). The "what's already true that I
  must not break?"

```bash
# Use claude -p subprocess fan-out for nesting-safety.
for sub in ${SUBSYSTEMS}; do
    out="${REPORT_DIR}/scout/${sub}.md"
    .claude/skills/_common/dispatch_scout.sh \
        .claude/skills/plan-feature/agents/impact-scout.md \
        "$out" \
        subsystem="$sub" \
        feature_name="${FEATURE_NAME}" \
        project_root="$(pwd)" \
        skill_root=".claude/skills/plan-feature" \
        output_path="$out" &
done
wait
```

If a scout fails (no file written) re-dispatch once with the same
brief; if it fails twice, proceed with a partial impact map and flag
the gap explicitly in the spec's `## Architecture` section as
`(<subsystem> impact map MISSING — re-run /plan-feature --subsystems
<sub> to fill)`.

For shallow Agent-tool dispatch (when `/plan-feature` is invoked at
top level, not as a sub-agent), the orchestrator MAY use the Agent
tool with `subagent_type=general-purpose` instead of the
`dispatch_scout.sh` subprocess — same brief, same substitution
parameters, same output contract. Use Agent for top-level invocations
(faster); use `dispatch_scout.sh` when nesting-safe behavior matters.

### Stage 3 — Synthesize impact + decision stubs

**Pre:** scout outputs exist; background `Explore` from Stage 0.5
should have returned by now. **Post:** `${REPORT_DIR}/impact.md`
written; decision-stub list ready for Stage 4.

Read every scout's `<subsystem>.md` AND the background exploration at
`${REPORT_DIR}/exploration.md` (skip gracefully if Explore is still
running or failed; flag "background exploration unavailable" in
`impact.md`'s **Risks / constraints** section so the next-stage skill
knows to re-survey).

Write `impact.md` with:

```markdown
# Impact map — <feature-name>

## Touched subsystems
- <subsystem>: <one-line role in the feature>

## Cross-subsystem call graph
<which subsystem calls which; ASCII-art or bullet tree>

## Behaviors to preserve (cross-subsystem)
<merged from each scout's extracted-behaviors section; deduplicate
when two scouts surface the same invariant>

## Material forks
<every choice the implementation will face that has 2+ defensible
answers; each fork gets:
- a name
- the alternatives considered
- whether it warrants a `/decide` (cross-file, supersedes a pattern,
  excludes a future option) or just an in-spec note (local choice)>

## Risks / constraints
<from canonical-patterns.md, architectural-smells.md, and the
decision registry — what could go wrong>
```

For each fork that warrants `/decide`:

- Draft the ADR title and status `proposed`.
- Either: invoke `/decide <slug>` inline (if the choice is fully
  characterizable now) and capture the assigned ADR id.
- Or: leave the fork's name in the spec's `motivating_decision`
  comment with `(decision pending — invoke /decide before
  implementation)`.

The orchestrator decides between inline-decide and stub by asking:
"can I write the Decision sentence right now without speculation?"
Yes → invoke. No → stub.

### Stage 4 — Spec scaffold

**Pre:** impact.md written, decision ids (if any) captured.
**Post:** `ai-docs/specs/<feature-name>.md` exists with
`lifecycle: proposed`; after fill, `status: draft`.

```bash
.venv/bin/python scripts/specs.py init "${FEATURE_NAME}" \
  --code-roots <root1> [--code-roots <root2> ...] \
  --title "<derived from feature-name>" \
  --lifecycle proposed \
  ${MOTIVATING_DECISION:+--motivating-decision "${MOTIVATING_DECISION}"} \
  ${FORCE_FLAG} \
  --allow-missing
```

`--allow-missing` because Feature-tier specs may target files that
will be CREATED by the implementation, not files that exist yet.

Then OPEN the resulting spec and fill the five narrative sections from
`impact.md`:

- `## Goals` — the feature's user-facing outcome (one paragraph).
- `## Architecture` — the integration sketch from `impact.md`'s call
  graph, plus the chosen alternative for each material fork.
- `## Implementation` — `IM-N: <description>` checklist, ordered
  test-first (write a characterization test before mutating each
  touched call site).
- `## Learnings` — empty placeholder; `/refactor-subsystem` Phase 2b
  will populate post-execution.
- `## Exceptions` — known opt-outs from canonical patterns / decisions
  the feature explicitly takes (each with a one-line justification).

Replace the scaffold's `status: STUB` with `status: draft` once the
sections are filled — STUB is reserved for unpopulated scaffolds.

### Stage 5 — Effectiveness log

**Pre:** spec written. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

```bash
SUBSYSTEM_COUNT=$(echo "${SUBSYSTEMS}" | tr ',' '\n' | wc -l)
DECISION_COUNT=$(echo "${MOTIVATING_DECISIONS}" | tr ',' '\n' | grep -c .)
SCOUT_FAIL=$(find "${REPORT_DIR}/scout" -name '*.md' -size 0 | wc -l)

.venv/bin/python scripts/log_effectiveness.py \
  --skill plan-feature \
  --scan-id "scan-${TS}" \
  --target "${FEATURE_NAME}" \
  --findings-total "${SUBSYSTEM_COUNT}" \
  --buckets "{\"subsystems\": ${SUBSYSTEM_COUNT}, \"decisions_stubbed\": ${DECISION_COUNT}, \"scout_failures\": ${SCOUT_FAIL}}"
```

### Stage 6 — Summarize

Report to the user in ≤12 lines:

- Path to the new spec (`ai-docs/specs/<feature-name>.md`).
- Subsystems covered (with scout count).
- Decision IDs created (if any) and stubs pending (if any).
- Material forks list (one line each).
- Behaviors to preserve (count + a "see impact.md" pointer).
- Risks flagged from canonical patterns / smells.
- Recommended next command:
  - If decisions are still `proposed` and pending → `/decide --amend
    <id>` to mark accepted, then `/refactor-subsystem` to execute.
  - If no decisions needed → `/refactor-subsystem <feature-name>`
    directly.
  - If impact analysis surfaced 2+ workflows → ESCALATE to the
    System-tier chain (currently: read the spec, mark it for
    `/scope-feature` re-planning when that ships in PR2).

Do NOT start implementation. The spec is the handoff.

## Non-goals

- Implementing the feature (that's `/refactor-subsystem` or manual
  work driven by the spec).
- Building a new subsystem (that's the System-tier chain — escalate).
- Bug fixes (that's `/fix-workflow`).
- Auditing existing code for dead/dup/smell signals (that's the SUSPECT
  skills — invoke them separately if needed).
- Recording every minor preference as a decision — `/decide`'s
  threshold rules apply (constrains future work / excludes alternative
  / sets expiration).
- Editing `canonical-patterns.md` / `architectural-smells.md` — pattern
  proposals from this skill route through `/decide` and a separate
  human-reviewed edit.

## When things go sideways

| Symptom | Action |
|---|---|
| `--subsystems` argument names a subsystem doc that doesn't exist | Abort; recommend running `/map-subsystem <name>` first or correcting the name |
| Stage 1 finds no relevant decision and no relevant pattern | Note "no constraining priors" in `context.md`; this is fine for greenfield-ish features but worth flagging |
| Stage 2 scout returns "no integration point exists in this subsystem" | The feature may need a NEW subsystem — escalate to System-tier; do NOT proceed to spec scaffold |
| Stage 2 scouts surface 2+ workflows touched | Stop; document the cross-workflow nature in `impact.md`; recommend `/scope-feature` (System-tier) instead of completing the spec |
| Stage 3 surfaces a fork that violates an existing decision | Stop; the fork is either (a) an opportunity to supersede the existing decision (use `/decide --supersede`) or (b) the wrong choice — clarify with user before scaffolding the spec |
| `scripts/specs.py init` fails because spec id already exists | Abort; recommend `--force` only after the user decides whether to supersede the existing spec |
| Decision stub created but `/decide` invocation fails | Don't block the spec; record the fork in `motivating_decision: pending-<slug>` and flag it in the summary |
| Scout fails twice (no file written) | Proceed with partial impact; flag MISSING in the spec; `/refactor-subsystem` will re-scan during its Inventory phase |

## Repository layout

```
.claude/skills/plan-feature/
├── SKILL.md                    # this file — orchestrator
├── agents/
│   └── impact-scout.md         # Stage 2 scout brief
└── knowledge/
    ├── rules.md                # tier discipline + escalation criteria
    └── (host-overlay specifics).md       # subsystem naming, integration hot spots
```

The orchestrator (you) does NOT read files in `knowledge/`. Those are
for the scout sub-agent and for skill maintainers. Keeping them out of
your context is the whole point of this architecture.
