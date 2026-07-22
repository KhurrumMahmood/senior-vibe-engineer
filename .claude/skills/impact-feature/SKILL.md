---
name: impact-feature
description: Second skill in the System-tier chain. Reads a `scoped`-status plan, fans out one scout per touched subsystem to map call sites + behaviors-to-preserve, synthesizes the cross-subsystem impact + blast radius, and fills §3-4 of the plan. Advances plan status to `impacted`. Heavier than /scope-feature (scout fan-out) but lighter than /plan-feature (no spec scaffold; that's /plan-spec).
argument-hint: "<plan-name>  (must already be ai-docs/plans/<name>.md with status=scoped)"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: system
job: plan
best_for: |
  Second stage of System-tier planning — a `scoped`-status plan that
  needs full reachability + blast radius mapped before architecture-
  fit analysis can run. Fans out scouts per subsystem because the
  impact map is the most parallelizable part of the chain.
not_for: |
  Plan with status != scoped (use the matching next-stage skill).
  Feature-tier impact mapping — /plan-feature already bundles its own
  scout fan-out (use it instead). Authoring decisions (use /decide).
escalate_to: |
  None — handoff is forward to /architecture-fit. If impact mapping
  reveals the scope was wrong (touches subsystems not in §1, doesn't
  touch ones it claimed), STOP and recommend re-running /scope-feature
  rather than expanding scope silently.
delegate_from: |
  /scope-feature recommends /impact-feature once §1-2 are filled and
  status is scoped.
language: python
framework: django
---

# /impact-feature

You are the **orchestrator** for the **second** skill in the System-
tier planning chain. The deliverable is the same plan at
`ai-docs/plans/<name>.md` with §3 (Impact Map) and §4 (Blast Radius)
populated and `status: impacted`. You do NOT do architecture-fit
analysis — that's the next skill's job.

The scout fan-out is the most parallelizable part of System-tier
planning; running scouts in parallel keeps the wall-clock cost
proportional to the most-touched subsystem rather than to the sum.

## How success is judged

- One scout ran per touched subsystem, each leaving its brief at
  `${REPORT_DIR}/scout/<subsystem>.md` with call sites, model
  touchpoints, route boundaries, test surfaces, and
  behaviors-to-preserve — not just a touched-files list.
- §3 (Impact Map) and §4 (Blast Radius) of `ai-docs/plans/<name>.md`
  are synthesized from those scout files, and status advances to
  `impacted`.
- A scope mismatch (impact exceeds §1) triggers a STOP and a
  re-run-`/scope-feature` recommendation — never silent expansion.
- Stage 5 reports the real `.venv/bin/python scripts/plans.py audit`
  output after the status edit; a claim without that output is not
  enough.
Write toward these gates from Stage 0.

## Core beliefs

1. **Impact ≠ touched-files-list.** Impact includes call sites,
   model touchpoints, route boundaries, **behaviors-to-preserve**
   (load-bearing `.save()` orderings, queue pinning, signal handlers),
   and test surfaces. A list of paths is not an impact map.
2. **Behaviors-to-preserve are the contract.** The new feature must
   not break invariants that current code carries implicitly. The
   scout's job is to surface those.
3. **Scope mismatch is signal.** If the impact map can't fit inside
   §1's "in scope" list, the scope is wrong — STOP and recommend re-
   running `/scope-feature`. Do NOT silently expand scope.
4. **One scout per subsystem.** Don't pile multiple subsystems into
   one scout brief; the per-subsystem isolation is what makes the
   parallel fan-out useful.

## Scope (this skill itself)

- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python`. `scripts/plans.py` parses YAML
  frontmatter through PyYAML from `requirements.txt`; the venv is part
  of the contract.
- **Read:** `ai-docs/plans/<name>.md`,
  `.claude/docs/subsystems/`, `.claude/docs/workflows/`.
- **Write:** `reports/impact-feature/scan-<TS>/scout/<subsystem>.md`,
  `reports/impact-feature/scan-<TS>/impact.md`,
  `ai-docs/plans/<name>.md` (§3-4 + status bump).

## Pipeline

### Stage 0 — Setup

```bash
PLAN_NAME="<arg>"
PLAN_PATH="ai-docs/plans/${PLAN_NAME}.md"
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/impact-feature/scan-${TS}"
mkdir -p "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/impact-feature/latest
```

Verify plan exists and `status: scoped`. If status is `draft`, abort
and recommend `/scope-feature` first. If status is `impacted+`, abort
and recommend the next-stage skill.

### Stage 1 — Identify touched subsystems

Read the plan's §1 "In scope" list. Map each in-scope artifact to the
matching subsystem doc under `.claude/docs/subsystems/`:

```bash
ls .claude/docs/subsystems/ | sed 's/\.md$//'
```

Present the candidate subsystem list to the user and wait for
confirmation. Approval token: `approved` / `approve` / `go` /
`lgtm` / `proceed` / `yes`.

If §1 names subsystems that don't have docs, note them but proceed —
scout for those will be best-effort (no doc to consult). Recommend
`/map-subsystem <name>` in the summary so the next planning round has
the doc.

### Stage 2 — Scout fan-out

Dispatch one scout per touched subsystem. Each scout receives the
plan path, the subsystem name, and the in-scope items relevant to it,
and returns a markdown file with:

- `## Call sites` — every place that would be touched if the in-scope
  items land. File paths, function names, line numbers.
- `## Model touchpoints` — models read or written, including any
  `.save()` orderings or signal handlers.
- `## Route boundaries` — URL patterns, view classes, mixins (e.g.
  `LoginRequiredMixin`) that would matter for the integration.
- `## Test surfaces` — existing test modules that exercise the touched
  code; the spec's characterization tests should extend these.
- `## Behaviors to preserve` — invariants the new feature must not
  break. Be specific: "X must be saved before Y because Z relies on
  the FK", "this task must run on the browser queue because Akamai".

Tell every scout that its output is judged by those sections existing
in the file at `output_path`; a reply that only summarizes findings in
chat does not satisfy the dispatch.

For shallow Agent dispatch (top-level invocation), use:

```
Agent(subagent_type=general-purpose, prompt=<scout brief substituted>)
```

For nesting-safe dispatch (sub-agent invocation):

```bash
for sub in ${SUBSYSTEMS}; do
    out="${REPORT_DIR}/scout/${sub}.md"
    .claude/skills/_common/dispatch_scout.sh \
        .claude/skills/impact-feature/agents/scout.md \
        "$out" \
        plan_path="${PLAN_PATH}" \
        subsystem="$sub" \
        plan_name="${PLAN_NAME}" \
        project_root="$(pwd)" \
        skill_root=".claude/skills/impact-feature" \
        output_path="$out" &
done
wait
```

Send all scout dispatches in a single message so they run
concurrently. If a scout fails (no file written), re-dispatch once;
if it fails twice, proceed and flag the gap as MISSING in the impact
map.

### Stage 3 — Synthesize cross-subsystem impact

Read every scout's output. Write `${REPORT_DIR}/impact.md` with:

```markdown
# Impact map — <plan-name>

## Touched subsystems
- <subsystem>: <one-line role in the work>

## Cross-subsystem call graph
<which subsystem calls which; ASCII-art or bullet tree>

## Behaviors to preserve (cross-subsystem)
<merged from each scout; deduplicate when two surface the same
invariant>

## Blast radius
- Files touched (count by subsystem)
- Tests that will need updates (count by module)
- Workflows affected (from .claude/docs/workflows/)
```

### Stage 4 — Write §3-4 of the plan

Edit `${PLAN_PATH}` to fill §3 (Impact Map) and §4 (Blast Radius)
from `impact.md`:

```markdown
## 3. Impact Map

**Touched subsystems.**
- `<subsystem>` — _role in the work_

**Cross-subsystem call graph.**
_(ASCII or bullet tree from the scout synthesis)_

**Models touched.**
- `core.models.X` — _read / write / new field_

**Routes touched.**
- `/sites/<site_id>/foo` — _new / changed / removed_

## 4. Blast Radius

**Behaviors to preserve.**
- _Invariant 1 (with origin: which scout / which file)_

**Affected workflows.**
- _Workflow name_ — _which step changes_

**Test surfaces.**
- `tests.test_<module>` — _which tests need extension_

**Files to touch (estimate).**
- _N files across M subsystems_
```

### Stage 5 — Advance status

Edit the frontmatter `status:` line to `impacted`. Optionally update
`subsystems:` and `workflows:` lists in frontmatter from §3-4.

```bash
.venv/bin/python scripts/plans.py audit
```

### Stage 6 — Summarize

Report to the user in ≤10 lines:

- Path to the plan and to `${REPORT_DIR}/impact.md`.
- Subsystems covered (with scout pass/fail count).
- Behaviors-to-preserve count.
- Workflows touched.
- Files-to-touch estimate.
- Recommended next command: `/architecture-fit <plan-name>`.

## Non-goals

- Doing architecture-fit analysis (that's `/architecture-fit`).
- Authoring decisions (that's `/decide`).
- Scaffolding the spec (that's `/plan-spec`).
- Editing production code.

## When things go sideways

| Symptom | Action |
|---|---|
| Plan status is `draft` | Abort; recommend `/scope-feature` first |
| Plan status is `impacted+` | Abort; recommend next-stage skill |
| §1 in-scope list is empty | Abort; recommend re-running `/scope-feature` |
| Scout reports impact outside §1 in-scope list | Stop; recommend re-running `/scope-feature` to widen / narrow scope; do not silently expand the impact map |
| Scout fails twice | Mark MISSING in §3 with `(<subsystem> impact map MISSING — rerun /impact-feature <plan-name> and select this subsystem at Stage 1)`; proceed |
| Scout finds no integration point in subsystem | Note in §3; this is a real signal — the scope may need to add a NEW subsystem (escalate to a decision via `/decide`) |
| `plans.py audit` fails with `ModuleNotFoundError: yaml` | Runtime is not initialized. Stop and run `/engineer-init`; do not retry with bare `python3` |
