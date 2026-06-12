# Resume /refactor-subsystem for spec `extraction-pipeline` — First Five Actions

**Scenario:** Fresh session, no prior memory. Spec `extraction-pipeline` is mid-run; previous session ended partway through.

**Task:** List the first five concrete actions (real commands + real file reads with paths) before touching any code, per the skill protocol.

---

## Action 1: Determine git worktree and verify project context

```bash
git rev-parse --show-toplevel
git branch --show-current
git status --porcelain
```

**Why:** SKILL.md §Scope requires confirmation of the worktree before Phase 1. This establishes baseline: are we on the right branch, is the working tree clean for resumption, and do we have write permissions?

**Mandatory:** Yes. Without this, subsequent state checks are against the wrong repository.

---

## Action 2: Check spec existence and load current state via `specs.py show`

```bash
python3 scripts/specs.py show extraction-pipeline
```

**Why:** SKILL.md §Phase 1.1 (Load spec and ledger) opens with this exact command. It:
- Exits 0 if the spec exists (confirm we skip Phase 0 bootstrap)
- Exits 1 if the spec does not exist (would trigger Phase 0 bootstrap, which we don't need mid-run)
- Exits non-zero otherwise (abort signal)

Returns the full spec structure, including `code_roots`, current `[ ]` / `[~]` / `[x]` states, and all plan items. This is the north-star for all subsequent work. Resuming without reading this is resuming blind.

**Mandatory:** Yes. It is the gate for every subsequent phase decision.

---

## Action 3: Verify spec coverage and detect drift via `specs.py coverage`

```bash
python3 scripts/specs.py coverage extraction-pipeline
```

**Why:** SKILL.md §Phase 1.1 includes: "If coverage reports drift (checkmark lag or orphan refs), **fix the drift first** — either as a sub-task or abort and report. A spec that already drifts is not a safe refactor target."

This command:
- Returns JSON with `is_clean`, `checkmark_lag`, `orphan_refs`, `documented_only`, `implementation_ahead` flags
- Identifies whether code has moved and the spec was not updated (checkmark lag)
- Identifies whether code was added without spec planning (orphan refs)
- **Blocks Phase 5 resumption if `is_clean: false`**

Mid-run drift is the #1 failure mode that silently orphans load-bearing code (R14 in learnings.md). Must be resolved before resuming execution.

**Mandatory:** Yes, before Phase 5 resumption. Non-negotiable gate.

---

## Action 4: Locate and read the latest phase-completion artifact

```bash
ls -ltr reports/refactor/extraction-pipeline/ | tail -20
```

Then read the most recent phase file to understand which phase completed last:

```bash
# Example paths per SKILL.md §1.5 and subsequent phases:
cat reports/refactor/extraction-pipeline/phase-1-inventory.md          # if Phase 1 done
cat reports/refactor/extraction-pipeline/phase-3-plan.md              # if Phase 3 done
cat reports/refactor/extraction-pipeline/findings.md                  # if Phase 2.3 done
```

**Why:** SKILL.md requires mandatory output artifacts at each phase gate (§1.5, §2.3, §3.3). Reading the most recent completion artifact tells us:
- Which phase completed last (inventory, characterization, plan, approval, or execution)
- What work remains
- Whether hidden state (scout outputs, extraction consolidations) exists on disk
- Whether Phase 4 approval is recorded in the plan file

Without this, we don't know if we're resuming Phase 3 planning, Phase 5 execution, or Phase 6 verification.

**Mandatory:** Yes. It is the resumption state machine.

---

## Action 5: Read the spec's `## Sign-off` section to check Phase 4 approval status

```bash
grep -A 20 "^## Sign-off" ai-docs/specs/extraction-pipeline.md
```

**Why:** SKILL.md §Phase 4.3 records: "Append to `phase-3-plan.md`: `## Sign-off`..." and §Phase 4.2 gates Phase 5 entry: "Do not start Phase 5 on implicit 'looks good' signals. The user must respond with an **unconditional, standalone approval**."

If the spec was mid-run and Phase 4 approval is present, we can resume Phase 5 execution. If Phase 4 approval is missing or partial, we must loop back to Phase 3 or request approval.

This is the gate between planning and execution. Skipping this check means potentially executing a plan the user never approved or approved only partially.

**Mandatory:** Yes, if we're past Phase 3. Determines whether Phase 5 is authorized to proceed.

---

## Summary

These five actions load the **state machine** that drives resumption:

1. **Worktree validation** → confirm we're in the right project, branch, and clean state
2. **Spec validation** → confirm the spec exists and is parseable
3. **Drift detection** → confirm code and spec are in sync (or identify what must be fixed first)
4. **Phase detection** → read completion artifacts to determine which phase completed last
5. **Approval detection** → confirm Phase 4 sign-off exists (mandatory before Phase 5 execution)

**All five are mandatory.** Skipping any one of them risks resuming into a broken or unapproved state.

Each command is **read-only** — no code changes, no edits, no commits. These five actions are pure information gathering, the foundation on which the orchestrator rebuilds context and decides whether to resume Phase 3, Phase 5, Phase 6, or Phase 7 — or whether to abort and request clarification from the human.
