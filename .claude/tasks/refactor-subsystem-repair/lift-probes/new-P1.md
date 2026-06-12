# Phase 1.4 git archaeology — core/services/extraction.py (1,200 LOC, 73 commits)

Source of truth: SKILL.md §1.4 plus `knowledge/operations.md` ("Git archaeology
recipe (Phase 1.4)" and "Archaeology report schema").

## 1. Who runs it

**The orchestrator (me), not a scout.** Trigger table:

- Scout-inline archaeology requires **≤ 500 LOC AND ≤ 20 commits**. This file
  fails both prongs (1,200 LOC; 73 commits), so it falls into "everything
  else → the orchestrator runs it in parallel with scout dispatch."
- Because the file has **≥ 50 commits** (73), archaeology is **mandatory**
  (R17, R4) — not optional, not skippable.

Ownership is recorded in the Phase 1.3.0 artifacts: the chunk map's
`Archaeology owner` column and the `archaeology_owner` key in
`reports/refactor/<spec-id>/inventory/chunks.jsonl` are set to
`"orchestrator"` for this file. (At 1,200 LOC the file is ≤ 2,000 LOC, so it
skips chunking and gets the single uniform chunk id `extraction__C-01`; the
inventory scout's brief receives `archaeology_owner = "orchestrator"`, which
deactivates the brief's inline-archaeology section.)

Timing: I run it **in parallel with** dispatching the Phase 1.3 inventory
scouts — not before, not after.

## 2. Exact commands

The recipe preserves exactly these commands (R4's base command is
`git log --follow -p`; there is no distinct orchestrator-side variant — the
orchestrator runs the same scout-side commands):

```bash
git log --follow --oneline core/services/extraction.py | head -50
git log --follow -p core/services/extraction.py | head -500
```

Plus the **subject-word filter** to bias toward high-signal commits, applied
to the `--oneline` subject list:

```bash
git log --follow --oneline core/services/extraction.py | grep -iE 'fix|retry|timeout|crash'
```

The filter vocabulary is exactly `fix|retry|timeout|crash` — the only four
terms that survive from the original recipe. A host-adapter slot allows the
host project to extend this list as an explicit configured choice; absent
that configuration I do not improvise additional terms.

## 3. What qualifies a commit as high-signal

A commit whose **subject line matches the failure/defense vocabulary**
(`fix|retry|timeout|crash`, case-insensitive). These are the commits likely
to explain *why* a defensive block, retry loop, timeout guard, or
non-obvious invariant exists — i.e., load-bearing rationale that was never
written down in the code. (Calibration point from the recipe: a 102-commit
file yielded 7 load-bearing LR-T candidates — L-25.)

## 4. Minimum findings

Because the file has ≥ 50 commits, the archaeology file **must contain at
least 3 load-bearing LR-T candidates**, each carrying an
`<!-- archaeology: <hash> -->` tag. This is also Phase 1.5 gate condition 3
("Archaeology present where required") — Phase 2 does not start until it
holds.

## 5. Exact format/schema per finding

One entry per load-bearing rationale, matching the LR-T candidate shape from
`agents/inventory-scout.md` (Output 3, Bucket 4):

```markdown
# Archaeology — core/services/extraction.py

### LR-T candidate: <short name>
**File:** core/services/extraction.py:<line>
_<one-line purpose summary>_
**Behavior:** <the invariant and why the defensive block exists>
<!-- archaeology: <hash> -->
**Proposed text:** <LR-T item text for the spec>
```

The `<!-- archaeology: <hash> -->` tag travels with the rationale: it appears
in the report entry AND in the spec LR-T item it becomes at Phase 3.1, so
Phase 7 crystallization preserves the invariant's origin. Pinned archaeology
hashes are a recognized exception to staleness rules
(`.claude/skills/_common/skill-conventions.md`).

## 6. Exact output path

```
reports/refactor/<spec-id>/archaeology/extraction.md
```

(`<basename>.md` where the basename of `core/services/extraction.py` is
`extraction`.) Consumers: Phase 1.5 gate condition 3, Phase 2.2
consolidation, the Phase 3.1 spec update, and §3.3 REM entries cite this
file in their `**Archaeology:**` field.
