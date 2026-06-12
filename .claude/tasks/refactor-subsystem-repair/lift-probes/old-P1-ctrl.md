# Probe old-P1-ctrl — Phase 1.4 git archaeology for `core/services/extraction.py`

**Skill snapshot:** `/tmp/refactor-skill-old/` (SKILL.md §1.4, `agents/inventory-scout.md`,
`knowledge/learnings.md` R4 / R17 / L-7 / L-8 / L-13 / L-25)

**Target facts:** 1,200 LOC; `git log --oneline -- core/services/extraction.py | wc -l` → 73 commits.

---

## 1. Who runs it

**The orchestrator (me), in parallel with the inventory scout — not the scout.**

§1.4's routing table:

- ≤ 500 LOC **AND** ≤ 20 commits → scout runs it inline.
- Everything else → orchestrator runs it in parallel with scouts.
- ≥ 50 commits → archaeology is **mandatory** (R17), not optional.

`extraction.py` fails the scout-inline test on both axes (1,200 > 500 LOC; 73 > 20 commits)
and crosses the ≥ 50-commit mandatory threshold (73 ≥ 50). So:

- The file is ≤ 2,000 LOC, so it **skips chunking** (§1.3.0): one inventory scout, single
  uniform chunk id `extraction__C-01` (R35 basename-qualified form).
- The chunk-map row's **Archaeology owner** column is set to `orchestrator`.
- The scout brief is dispatched with `{{archaeology_owner}} = orchestrator`, which per
  `agents/inventory-scout.md` tells the scout to **skip** archaeology ("the orchestrator is
  handling Phase 1.4 for {{file}} in parallel"). The orchestrator runs the git commands
  itself while the scout reads the code. (Ownership split by churn — L-7.)

## 2. Exact commands

Honest caveat first: SKILL.md §1.4 says "See `knowledge/` for the full recipe" and "per the
schema in `knowledge/`", but the skill snapshot's `knowledge/` directory contains only
`bootstrap.md`, `execution-playbook.md`, `learnings.md`, and `solid-gate-tests.md` — **the
operations/recipe file §1.4 points at is absent**. What is recoverable from the shipped
files is: the base commands (R4 + the scout template), and the subject-word filter whose
prefix SKILL.md quotes verbatim as `fix|retry|timeout|crash|...` (the `...` tail is in the
missing file and cannot be reproduced exactly). The commands as run, from what the skill
ships:

```bash
# 1. Churn count (already known: 73)
git log --follow --oneline -- core/services/extraction.py | wc -l

# 2. Full subject list — the haystack
git log --follow --oneline -- core/services/extraction.py

# 3. Subject-word filter — the high-signal pass (filter prefix verbatim from §1.4;
#    tail truncated by SKILL.md itself as "...")
git log --follow --oneline -i -E --grep='fix|retry|timeout|crash' -- core/services/extraction.py

# 4. Rationale capture per surviving commit (R4: "git log --follow -p is worth
#    1000 commits of future confusion")
git show <hash> -- core/services/extraction.py
# or, scout-template form for the bulk pass:
git log --follow -p -- core/services/extraction.py | head -500
```

Capture rationale **now, before the split destroys blame history** (R4) — Phase 5's moves
will detach `git blame` from these lines.

## 3. What qualifies a commit as high-signal

- Its subject matches the subject-word filter (`fix|retry|timeout|crash|...`) — i.e. it
  records a defensive change: a bug fixed, a retry/timeout added, a crash hardened against.
- Its diff explains a **"why" that lives nowhere else in the code** — the rationale behind a
  defensive block, an odd ordering, a magic constant, a swallow-and-retry shape (R17:
  "commit messages on high-churn files encode invariants that live nowhere else").
- "Load-bearing" means: if a future refactorer read only the code, they would plausibly
  delete or simplify the guarded construct; the commit is the evidence that it must stay.
  Calibration point: L-25 validated the recipe on a 102-commit file → 7 load-bearing
  findings, so single-digit survivors out of 73 commits is the expected yield.

## 4. Minimum findings

**At least 3 load-bearing LR-T candidates**, each tagged with
`<!-- archaeology: <hash> -->` (§1.4 + R17 + L-13). This is enforced at the Phase 1.5 gate,
condition 3: "every ≥ 50-commit file has ≥ 3 LR-T candidates" — fewer blocks Phase 2.

## 5. Format / schema per finding

Each finding is recorded as an **LR-T candidate** carrying the archaeology hash tag. The
dedicated archaeology-file schema lives in the missing knowledge file; the recoverable
canonical entry shape comes from the inventory-scout template's extracted-behaviors rules
(provisional-ID rule R16/R35, function-purpose summary rule, LR-T bucket definition):

```markdown
### extraction__C-01-LR-T-1: <short name of the invariant>
**File:** core/services/extraction.py:<line>
_<one-line purpose summary from docstring or first 3 body lines>_
**Behavior:** <the defensive behavior / invariant the commit explains>
**Proposed text:** <LR-T item text destined for the spec>
<!-- archaeology: <commit hash> -->
```

Rules applied:

- Provisional IDs are **basename-qualified chunk-id prefixed** (`extraction__C-01-LR-T-N`),
  never bare canonical IDs (`LR-T-2`) — Phase 2.2 reassigns canonical numbers (R16, R21, R35).
- The `<!-- archaeology: <hash> -->` tag is mandatory inline so Phase 7 crystallization can
  preserve the invariant's origin (per the LR-T bucket definition in the scout template).
- These entries flow into Phase 2.2 consolidation under `## LR-T candidates` in
  `reports/refactor/<spec-id>/extracted-behaviors.md`, and ultimately into the spec.

## 6. Exact output path

```
reports/refactor/<spec-id>/archaeology/extraction.md
```

Per §1.4: `reports/refactor/<spec-id>/archaeology/<basename>.md`; the basename of
`core/services/extraction.py` is `extraction`. (`<spec-id>` is the run's spec argument,
e.g. `reports/refactor/extraction-split/archaeology/extraction.md`.)

## 7. Gap noted (faithful-to-snapshot disclosure)

§1.4 and the SKILL.md preamble both reference a `knowledge/` operations file for "worktree
paths, scripts, venv conventions, **archaeology recipe**, test matrix, report layout" — that
file does not exist in `/tmp/refactor-skill-old/knowledge/`. Consequences for this probe:
the full subject-word regex (everything after `fix|retry|timeout|crash`) and the
archaeology-file's exact per-entry schema are **not recoverable from the skill as shipped**;
everything above marked "verbatim" is from SKILL.md §1.4, R4/R17, and the scout template,
and the rest is the minimal faithful reconstruction those surfaces force.
