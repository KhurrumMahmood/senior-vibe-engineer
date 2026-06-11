---
name: plan-spec
description: Final skill in the System-tier chain. Reads an `architected`-status plan, validates that §6 has no unresolved P0 forks, then calls `scripts/plans.py promote` to scaffold a successor spec under `ai-docs/specs/<spec-id>.md` and mark the plan `promoted`. The plan's §3-5 inform the spec's Architecture / Implementation / Exceptions sections. Hands off to `/refactor-subsystem` for execution.
argument-hint: "<plan-name>  (must be ai-docs/plans/<name>.md with status=architected)"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: system
job: plan
best_for: |
  Fourth and final stage of System-tier planning — an `architected`-
  status plan with §6 clean (no unresolved P0 forks) ready to become
  a behavior-preserving spec that `/refactor-subsystem` can execute.
  Validates the promotion gate, scaffolds the spec, links plan ↔ spec
  bidirectionally.
not_for: |
  Plan with status != architected (use the matching earlier-stage
  skill). Plan with unresolved P0 forks in §6 (use /decide for each,
  then come back). Authoring decisions (use /decide).
escalate_to: |
  None — this is the terminal skill in the chain. Forward handoff is
  to /refactor-subsystem (with the new spec id) or to manual
  implementation against the spec.
delegate_from: |
  /architecture-fit recommends /plan-spec once §5-6 are filled and
  status is architected.
language: python
framework: django
---

# /plan-spec

You are the **orchestrator** for the **fourth and final** skill in the
System-tier planning chain. The deliverable is a `proposed`-status
spec at `ai-docs/specs/<spec-id>.md` plus the same plan at
`ai-docs/plans/<plan-name>.md` updated to `status: promoted` with
`successor_spec: <spec-id>` set.

This skill is the gate between **forward-looking design** (the plan)
and **behavior-preserving execution** (the spec). The promotion is
explicit — you call `scripts/plans.py promote`, which itself shells
out to `scripts/specs.py init`. No silent promotion.

## Core beliefs

1. **The promotion gate is real.** A plan with unresolved P0 forks in
   §6 is NOT promotable. Refuse and recommend `/decide` for each
   blocking fork. The cost of a premature promotion is a spec that
   forces the implementer to re-derive the architecture.
2. **Spec sections come from plan sections.** The spec's Architecture
   reflects plan §3 + §5; Implementation reflects plan §4 + §3;
   Exceptions reflects plan §5 (smells accepted) + §6 (P1 deferred
   forks). Don't invent — transcribe.
3. **Plan ↔ spec link is bidirectional.** The plan's
   `successor_spec` points at the spec; the spec's
   `motivating_decision` (if set) plus a `# Provenance` section point
   back at the plan. This is the audit trail.
4. **One plan, one spec.** If a plan should yield multiple specs
   (different code roots, different timelines), it was actually two
   plans — abandon the merge, re-run `/scope-feature` for each.

## Scope (this skill itself)

- **Project root:** this worktree's root.
- **Python:** `python3` (stdlib-only).
- **Read:** `ai-docs/plans/<name>.md`.
- **Write (via plans.py promote):** `ai-docs/specs/<spec-id>.md`,
  `ai-docs/plans/<name>.md` (status + successor_spec).
- **Write (this skill):** spec body sections after promote scaffold.

## Pipeline

### Stage 0 — Setup

```bash
PLAN_NAME="<arg>"
PLAN_PATH="ai-docs/plans/${PLAN_NAME}.md"
```

Verify plan exists and `status: architected`. If status is anything
else, abort and recommend the matching stage skill (or `/decide` if
P0 forks remain).

### Stage 1 — Validate promotion gate

Read `${PLAN_PATH}` §6 (Open Decisions). Count entries under each
priority heading:

- **P0 forks > 0** → ABORT. Print each P0 fork name and the
  recommended `/decide <slug>` invocation. Do NOT proceed.
- **P1 forks > 0** → continue, but include them in spec §Exceptions
  with `(deferred from plan §6 — resolve during /refactor-subsystem
  Phase 2)`.

Read §5 (Architecture Fit). Verify:

- At least one ADR conformance OR an explicit "no constraining
  priors" note. Empty §5 → ABORT, recommend re-running
  `/architecture-fit`.

### Stage 2 — Determine code roots

Ask the user for the spec's code roots (the file paths the spec
will track for `# spec:<id>::IM-N` annotations). Default candidates:

- Subsystems named in plan frontmatter `subsystems:` field
  (translate to file/dir paths via the subsystem doc's first
  "Files" section).
- Files named in §3 "Files touched (estimate)".

Present the candidate list and wait for user approval / amendment.
Approval token: `approved` / `approve` / `go` / `lgtm` / `proceed` /
`yes`.

### Stage 3 — Promote

```bash
python3 scripts/plans.py promote "${PLAN_NAME}" \
  --code-roots "<root1>" \
  [--code-roots "<root2>" ...] \
  --allow-missing
```

`--allow-missing` is appropriate for System-tier specs because new
subsystems may not yet have files on disk. The promote subcommand:

1. Verifies plan is not already promoted.
2. Shells out to `scripts/specs.py init <spec-id> --code-roots ...`
   with title and motivating_decision propagated from the plan.
3. Writes the spec scaffold under `ai-docs/specs/<spec-id>.md`.
4. Updates the plan's `status:` to `promoted` and sets
   `successor_spec:` to the spec id.

If promote fails (non-zero exit), surface the error and stop. Do not
re-run silently — the plan and spec must end in a consistent state.

### Stage 4 — Fill spec body from plan

Open the new spec at `ai-docs/specs/<spec-id>.md`. The scaffold has
the six standard sections (Goals / Architecture / Implementation /
Learnings / Exceptions / Lifecycle). Fill them by transcribing from
the plan:

- **Goals** ← plan §1 problem statement + §2 success criteria.
- **Architecture** ← plan §3 cross-subsystem call graph + plan §5
  decision conformance + pattern alignment.
- **Implementation** ← plan §4 behaviors-to-preserve become
  characterization-test items (`AR-N`); files to touch become
  `IM-N` items, ordered test-first.
- **Learnings** ← empty placeholder (`/refactor-subsystem` Phase 2b
  fills post-execution).
- **Exceptions** ← plan §5 smells-accepted + plan §6 P1 deferred
  forks.
- **Lifecycle** ← `proposed` (the scaffold default).

Replace the scaffold's `status: STUB` with `status: draft` once the
sections are filled.

Add a `# Provenance` block immediately after the frontmatter:

```markdown
# Provenance

Promoted from plan `<plan-name>` (`ai-docs/plans/<plan-name>.md`).
- Plan §1-2 → Goals
- Plan §3, §5 → Architecture
- Plan §4, §3 → Implementation (test-first)
- Plan §5, §6 → Exceptions
```

This is the audit trail — when the spec drifts during implementation,
the plan is the original-intent record.

### Stage 5 — Verify links

```bash
python3 scripts/plans.py audit
python3 scripts/specs.py inventory-check "${SPEC_ID}"
```

The plan audit confirms `successor_spec` resolves; the spec
inventory-check confirms the scaffold parses and the code roots are
addressable.

### Stage 6 — Summarize

Report to the user in ≤10 lines:

- Plan path: `ai-docs/plans/<name>.md` (now `status: promoted`).
- Spec path: `ai-docs/specs/<spec-id>.md` (now `status: draft`,
  `lifecycle: proposed`).
- Code roots tracked in spec.
- ADR ids carried over from plan §5.
- P1 forks deferred to spec §Exceptions (count + names).
- Recommended next command:
  - `/refactor-subsystem <spec-id>` to begin behavior-preserving
    execution.
  - Or, if the spec is greenfield (no `code-roots` exist yet):
    manual implementation against the spec, with
    `/refactor-subsystem` joining once code lands.

## Non-goals

- Authoring decisions (that's `/decide` — must happen before
  this skill if there are P0 forks).
- Implementing the feature (that's `/refactor-subsystem`).
- Re-running impact analysis (that's `/impact-feature`; if the impact
  map is stale, the plan should be reverted to `impacted` and re-
  walked, not patched here).
- Editing the plan's §1-§4 (those are frozen once the plan is
  `architected`; only `status` and `successor_spec` change).

## When things go sideways

| Symptom | Action |
|---|---|
| Plan status is not `architected` | Abort; recommend the matching stage skill |
| §6 has unresolved P0 forks | Abort; print each P0 with the recommended `/decide` invocation |
| §5 is empty or "no priors" without justification | Abort; recommend re-running `/architecture-fit` |
| User can't name code roots | The work is greenfield — pass `--allow-missing` and use the directory paths the new code WILL live in (e.g. `core/services/<new-name>/`) |
| `plans.py promote` fails (spec id collision) | Abort; ask user to choose a different `--spec-id` (default is plan name; pass `--spec-id <alt>` to override) |
| Spec scaffold succeeds but transcription reveals plan §3 is too thin | Roll back: revert plan status to `impacted`, delete the spec, re-run `/impact-feature` |
| Plan promotion completes but inventory-check reports STUB | Expected — the spec needs its `IM-N` items filled. Continue with `/refactor-subsystem` Phase 1.2 (Inventory) which expands the auto-generated inventory |
