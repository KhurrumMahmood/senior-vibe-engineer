# Phase 1.4 Git Archaeology — Exact Procedure for extraction.py

## File profile
- **File:** `core/services/extraction.py`
- **Size:** 1,200 LOC
- **Commit history:** 73 commits
- **Trigger:** ≥ 50 commits → archaeology is **mandatory** (R17, SKILL.md §1.4)

## Who runs it
**Orchestrator** (not scout). Since the file exceeds 500 LOC AND has 73 commits (both thresholds), the orchestrator runs archaeology **in parallel with scout dispatch** (SKILL.md §1.4, operations.md §1.4).

## Exact git commands

**Step 1: Initial subject scan (high-signal filter)**
```bash
git log --follow --oneline core/services/extraction.py | grep -iE 'fix|retry|timeout|crash'
```

This filters the full 73-commit log to commits with failure/defense vocabulary. The host project extends the subject-word list beyond the base four terms (`fix|retry|timeout|crash`) — see the `host-adapter` slot in `operations.md` line 108. **Assumption: only the base four terms are in scope for this procedure.**

**Step 2: Full commit log (top 50)**
```bash
git log --follow --oneline core/services/extraction.py | head -50
```

Baseline view of the most recent commits.

**Step 3: Patch inspection (top 500 lines of output)**
```bash
git log --follow -p core/services/extraction.py | head -500
```

Read the actual diffs for candidates identified in Step 1.

## High-signal commit definition

Per operations.md §Git archaeology recipe and SKILL.md §1.4:

A commit qualifies as **high-signal** if:
1. Its subject line matches the filter: `-iE 'fix|retry|timeout|crash'` (case-insensitive)
2. The commit message or diff reveals **load-bearing rationale** — a defensive pattern, invariant, or behavioral constraint worth recording as an LR-T (technical lesson) item
3. The change is **not incidental** — it documents why a specific block, check, or sequence exists

Commits that are refactors, naming cleanups, or mechanical moves qualify only if they document a *why* (e.g., "refactor: extract to prevent circular import at runtime").

## Mandatory findings count

**≥ 3 load-bearing LR-T candidates with archaeology tags** (R17, operations.md lines 86–88).

Since the file has 73 commits, the archaeology output is mandatory. A minimum of 3 entries must be produced and included in the output file.

## Output format and schema

**File path:** `reports/refactor/<spec-id>/archaeology/extraction.md`

(The basename is `extraction` — stripped from `core/services/extraction.py`.)

**Schema per entry:**

```markdown
### LR-T candidate: <short name>
**File:** core/services/extraction.py:<line>
_<one-line purpose summary>_
**Behavior:** <the invariant and why the defensive block exists>
<!-- archaeology: <hash> -->
**Proposed text:** <LR-T item text for the spec>
```

**Structure of the full file:**

```markdown
# Archaeology — core/services/extraction.py

### LR-T candidate: <name 1>
**File:** core/services/extraction.py:<line>
_<summary>_
**Behavior:** <invariant explanation>
<!-- archaeology: <commit-hash> -->
**Proposed text:** <spec LR-T text>

### LR-T candidate: <name 2>
[same structure]

### LR-T candidate: <name 3>
[same structure]

[Additional entries beyond the mandatory 3 if discovered]
```

Each `<hash>` in the `<!-- archaeology: <hash> -->` tag is the full or short SHA of the commit that introduced or documented the behavior.

## Integration points

- **Phase 1.5:** Consolidation gate checks that ≥ 50-commit files have ≥ 3 LR-T candidates (SKILL.md §1.5 gate cond. 3).
- **Phase 2.2:** The orchestrator-produced archaeology entries feed the extraction consolidation and become LR-T items in `extracted-behaviors.md`.
- **Phase 3.1:** New LR-T items from archaeology are added to the spec as `[x]` entries (marked complete since archaeology documents pre-existing decisions with no code work).
- **Phase 7:** Archaeology hashes are pinned in spec LR-T items — they survive staleness checks as recognized exceptions (operations.md lines 119–120).

## Summary

- **Runner:** Orchestrator (parallel with scouts)
- **Commands:** Three sequential reads (subject filter, oneline log, patch log)
- **High-signal:** Failure/defense vocabulary in subject + load-bearing behavioral rationale
- **Minimum findings:** 3 LR-T candidates
- **Schema:** Markdown entries with `<!-- archaeology: <hash> -->` tags
- **Output file:** `reports/refactor/<spec-id>/archaeology/extraction.md`
