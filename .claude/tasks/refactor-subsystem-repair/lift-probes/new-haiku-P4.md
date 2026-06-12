# First Five Actions: Resume refactor-subsystem for spec `extraction-pipeline`

Fresh session, mid-run resumption. Following the skill's "Resuming mid-refactor" protocol (SKILL.md lines 133–154) plus phase-inference prerequisites.

## Action 1: Confirm git state and worktree
```bash
git rev-parse --show-toplevel
```
Validates the worktree path before any subsequent operations. Non-negotiable before Phase 1 Scope rules (SKILL.md line 122).

## Action 2: Infer current phase — coverage check
```bash
python3 scripts/specs.py coverage extraction-pipeline
```
**Why:** Core resumption gate (SKILL.md line 139). The output tells us:
- Current checkmark distribution (`[ ]` / `[~]` / `[x]`)
- Drift state (if any)
- Whether the spec is parseable

This disambiguates whether we're in Phase 1, 2, 3, 4, 5, 6, or 7 by cross-referencing the coverage delta against report artifacts (next action).

## Action 3: Infer current phase — report inventory
```bash
ls -la reports/refactor/extraction-pipeline/
```
**Why:** Phase inference (SKILL.md line 140). The presence/absence of these files tells us exactly where the run stopped:
- `phase-1-inventory.md` present → Phase 1 done, infer Phase 2+
- `phase-1-inventory-gate.md` present → Phase 1.1.5 gate ran
- `phase-1-solid-audit.md` present → Decomposition-mode Phase 1.2.5 ran
- `extracted-behaviors.md` present → Phase 2.2 done
- `findings.md` present → Phase 2.3 done
- `phase-3-plan.md` present → Phase 3 done
- `phase-3-plan.md` with "Sign-off" section → Phase 4 approval recorded
- Batch commits (git log) or Phase 5 artifacts → Phase 5 in progress
- `phase-6-boundary.md` present → Phase 6.0 done
- `phase-6-solid-agent.md` present → Phase 6.3 done
- Cleanup commit evidence → Phase 7 in progress

## Action 4: Load the current-phase knowledge file in full
```bash
# Assuming Phase 5 is in progress (most likely mid-run scenario):
cat .claude/skills/refactor-subsystem/knowledge/execution-playbook.md
```
**Why:** Mandatory (SKILL.md line 144): "Re-read that phase's knowledge file. Phase 5 means `knowledge/execution-playbook.md` IN FULL — not from memory."

Replace `execution-playbook.md` with `operations.md` (Phase 1), `bootstrap.md` (Phase 0), or `solid-gate-tests.md` (Phase 6.3) based on the phase inferred in Action 3.

## Action 5: Restate approved scope from sign-off
```bash
# Phase 3 plan must exist and have a Sign-off section
cat reports/refactor/extraction-pipeline/phase-3-plan.md | grep -A 20 "^## Sign-off"
```
**Why:** SKILL.md line 146: "Restate the approved scope and waivers from `phase-3-plan.md` §Sign-off before any edit."

This confirms:
- Who approved the refactor
- What scope was approved (split plan, remove candidates, findings triage)
- What was deferred
- Convention enforcement scope (subsystem vs. repo-wide)

These five actions establish the resumption baseline without touching any code, per the "Do not resume a Phase 5 batch with the playbook unread or the sign-off scope unloaded" invariant (SKILL.md line 152–154).
