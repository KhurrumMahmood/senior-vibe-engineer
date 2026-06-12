# Phase 1.4 (Git Archaeology) — Exact Protocol for `core/services/extraction.py`

## Target File Profile
- **File:** `core/services/extraction.py`
- **LOC:** 1,200
- **Commit count:** 73 commits
- **Trigger:** ≥ 50 commits → archaeology is **mandatory** (R17)

## Who Runs Archaeology

**The orchestrator runs it** — not a scout.

Per SKILL.md §1.4: "≤ 500 LOC AND ≤ 20 commits → scout runs it inline. Everything else → orchestrator runs it in parallel with scouts."

Since extraction.py is 1,200 LOC AND has 73 commits, archaeology is delegated to the orchestrator in parallel with Phase 1.3 inventory scouts.

## Exact Git Commands

The recipe is defined at SKILL.md §1.4 and learnings.md R4/R17.

```bash
# Step 1: Raw commit log with subject-word filter
# Subject-word filter: fix|retry|timeout|crash and related high-signal terms
git log --follow --oneline -- core/services/extraction.py | \
  grep -iE 'fix|retry|timeout|crash|error|bug|revert|fail|exception|broken|leak|deadlock|race|circular|cascade' | \
  head -20

# Step 2: Show full -p diffs for high-signal commits (sample)
# For each commit hash identified in Step 1, run:
git log --follow -p -- core/services/extraction.py | \
  grep -B 5 -A 20 'fix|retry|timeout|crash|error|bug'
```

## High-Signal Commit Criteria

A commit qualifies for extraction if:

1. **Subject line contains a high-signal term** — one of:
   - `fix` / `Fix` — bug fixes, corrections
   - `retry` / `Retry` — retry logic, exception handling, resilience
   - `timeout` / `Timeout` — timeout constraints, deadlines
   - `crash` / `Crash` / `Error` / `error` — exception paths, failure modes
   - `bug` / `Bug` — acknowledged defects
   - `revert` / `Revert` — reverted changes (carry "why we undid this" info)
   - `fail` / `exception` / `broken` / `leak` / `deadlock` / `race` / `circular` / `cascade` — structural failures

2. **Commit message depth** — the message encodes invariants, constraints, or defensive coding that "live nowhere else" (R4)
   - Rationale for why a block is defensive
   - Why a particular ordering is required
   - Why a workaround exists instead of a direct fix

## Findings Output Format & Schema

**Output file path:**
```
reports/refactor/<spec-id>/archaeology/extraction.md
```

**Format: Markdown with structured sections**

```markdown
# Archaeology — core/services/extraction.py (73 commits)

## High-Signal Commits Found

### [commit-hash-1]
**Subject:** <original subject line>
**Date:** <commit date>
**Summary:** <1-line extraction purpose>
**Archaeology finding:**
- **Type:** LR-T candidate (Learning — technical)
- **Code reference:** <file:line range affected>
- **Rule/Invariant:** <what constraint was set by this commit>
- **Why it matters:** <consequence if violated>

### [commit-hash-2]
**Subject:** <original subject line>
**Date:** <commit date>
**Summary:** <1-line extraction purpose>
**Archaeology finding:**
- **Type:** LR-T candidate
- **Code reference:** <file:line range affected>
- **Rule/Invariant:** <what constraint>
- **Why it matters:** <consequence>

[...repeat for all high-signal commits...]

## Cross-References to extracted-behaviors.md

Each archaeology LR-T entry must appear in the extracted-behaviors.md file
(Bucket 4: LR-T candidates) with the following tag:

### extraction__C-NN-LR-T-M: <short name>
**File:** core/services/extraction.py:<line>
_<one-line purpose summary from code or docstring>_
**Behavior:** ...
<!-- archaeology: <commit-hash> -->

```

## Minimum Findings Requirement

**Mandatory minimum for ≥ 50 commit files (R17):**
- **At least 3 load-bearing LR-T candidates**
- Each must have a `<!-- archaeology: <hash> -->` tag
- Each must cite file:line from extraction.py

A "load-bearing" LR-T is one that encodes:
- A defensive block whose purpose is non-obvious without commit history
- A constraint that would be violated by a naive refactor
- An ordering or sequencing requirement that protects invariants
- A workaround for a known issue that re-fixes itself if removed

## Integration with Phase 1.3 Scouts

While the orchestrator runs archaeology in parallel with scouts:

1. **Scouts do NOT run archaeology** for this file (archaeology_owner: "orchestrator" in the chunk map)
2. **Scouts produce extracted-behaviors.md** with their own observations
3. **Orchestrator appends archaeology findings** to the consolidated extracted-behaviors.md at Phase 2.2

At Phase 2.2, the orchestrator consolidates:
- All scout-provided extracted-behaviors.md from every chunk
- All orchestrator-discovered archaeology LR-T candidates
- Merges semantically identical entries before reassigning to canonical IDs

## Chunk-Qualified Provisional IDs

Extract IDs use the chunk-id prefix pattern (R21, R35):

For extraction.py with chunk id `extraction__C-NN`:
- `extraction__C-NN-LR-T-1`
- `extraction__C-NN-LR-T-2`
- `extraction__C-NN-LR-T-3` (minimum)
- ... (more if found)

These provisional IDs get reassigned to canonical IDs (`LR-T-1`, `LR-T-2`, etc.) at Phase 2.2 consolidation.

## Gate Condition at Phase 1.5

Phase 1.5 completeness gate (SKILL.md §1.5) requires:

For every file with ≥ 50 commits:
- Archaeology file exists at `reports/refactor/<spec-id>/archaeology/extraction.md`
- Contains ≥ 3 LR-T candidates
- Each candidate has a commit hash reference and file:line citation
- Each is formatted as a provisionally-IDed entry for Phase 2.2 consolidation

Missing archaeology → re-run before proceeding to Phase 2. Do not proceed with fewer than 3 load-bearing LR-T extractions.

## Rationale

Per SKILL.md core belief (R4) and learnings (R17):

> `git log --follow -p` is worth 1000 commits of future confusion. Capture rationale **BEFORE the split destroys blame history**, not after.

Splitting a 1,200-LOC file with 73 commits without archaeology risks losing the "why" behind 3–5 defensive blocks that will silently regress if moved into a new file with different callers or ownership.
