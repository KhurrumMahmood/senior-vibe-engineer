# Probe old-P1 — Phase 1.4 git archaeology for `core/services/extraction.py`

**Skill version probed:** `/tmp/refactor-skill-old/` (SKILL.md + knowledge/ + agents/)
**Target:** `core/services/extraction.py` — 1,200 LOC, 73 commits
(`git log --oneline -- core/services/extraction.py | wc -l` → 73)

## 1. Who runs it

**The orchestrator (me), not a scout.** SKILL.md §1.4 trigger table:

- "≤ 500 LOC AND ≤ 20 commits → scout runs it inline" — does NOT apply
  (1,200 LOC and 73 commits fail both halves).
- "Everything else → orchestrator runs it in parallel with scouts" — applies.

Mechanically: the file is < 2,000 LOC, so it skips chunking (§1.3.0) and gets a
single basename-qualified chunk id `extraction__C-01`. In the chunk map the
**Archaeology owner** column for this row is set to `orchestrator`, and the
inventory-scout brief is dispatched with `archaeology_owner=orchestrator`, which
per `agents/inventory-scout.md` tells the scout: "skip archaeology — the
orchestrator is handling Phase 1.4 for {{file}} in parallel." I run the
archaeology concurrently with the Phase 1.3 scout dispatch (ownership split by
churn — L-7).

## 2. Exact commands

SKILL.md §1.4 says "See `knowledge/` for the full recipe" and that "the recipe
uses a subject-word filter (`fix|retry|timeout|crash|...`) to find high-signal
commits." **Caveat (real gap found by this probe):** the knowledge file that is
supposed to hold the full recipe — worktree paths, archaeology recipe, report
layout, and the recording schema — is absent from `/tmp/refactor-skill-old/knowledge/`
(only `bootstrap.md`, `execution-playbook.md`, `learnings.md`,
`solid-gate-tests.md` exist). What follows is exactly what the surviving text
mandates, with the only concrete command shapes the skill itself writes down.

Base log (the scout-inline variant in `agents/inventory-scout.md` — the only
literal archaeology commands in the skill; R4 names `git log --follow -p` as the
core tool):

```bash
git log --follow --oneline core/services/extraction.py | head -50
git log --follow -p core/services/extraction.py | head -500
```

Orchestrator recipe applies the subject-word filter to isolate high-signal
commits (filter words as enumerated in SKILL.md §1.4; the `...` continuation
list lives in the missing knowledge file):

```bash
git log --follow --oneline core/services/extraction.py \
  | grep -iE 'fix|retry|timeout|crash'
```

then read each surviving commit's diff to extract the "why":

```bash
git show <hash> -- core/services/extraction.py
```

## 3. What qualifies a commit as high-signal

A commit whose **subject line matches the subject-word filter**
(`fix|retry|timeout|crash|...`) — i.e. bug-fix / defensive-hardening commits.
The underlying rationale (R4, R17, learnings.md): commit messages on high-churn
files "encode invariants that live nowhere else"; a high-signal commit is one
whose message explains the "why" behind a defensive block — a **load-bearing**
rationale that must be captured BEFORE the split destroys blame history.

## 4. Minimum findings

73 commits ≥ 50 → archaeology is **mandatory, not optional** (R17; original
lesson L-13). The archaeology file must contain **at least 3 load-bearing LR-T
candidates**, each cross-referenced with an inline `<!-- archaeology: <hash> -->`
tag. The Phase 1.5 gate (condition 3) blocks Phase 2 until this file has its
≥ 3 LR-T candidates on disk.

## 5. Format / schema per finding

SKILL.md §1.4 says "per the schema in `knowledge/`" — that schema file is
missing from this copy (see caveat above). The binding requirements that DO
survive in the skill text:

- each finding is an **LR-T candidate** (Bucket 4 of the six-bucket taxonomy:
  IM / AR / EX / LR-T / REM / INV), feeding Phase 2.2 consolidation into the
  `## LR-T candidates` section of `extracted-behaviors.md`;
- each carries an inline `<!-- archaeology: <hash> -->` tag so Phase 7
  crystallization preserves the invariant's origin;
- the per-entry shape mandated for extracted candidates (inventory-scout.md,
  R16 + addendum) — provisional chunk-prefixed ID, file:line cite, one-line
  italic purpose summary, behavior, proposed spec text:

```markdown
### extraction__C-01-LR-T-1: <short name>
**File:** core/services/extraction.py:<line>
_<one-line purpose summary>_
**Behavior:** <the defensive behavior and its "why" from the commit>
**Proposed text:** <LR-T item text for the spec> <!-- archaeology: <hash> -->
```

(Provisional IDs are basename-qualified per R35/R21 — `extraction__C-01-LR-T-N`
— matching `^[a-z0-9_]+__(C-\d+|orphan-\d+)-(IM|AR|EX|LR-T|REM|INV)-\d+$`;
Phase 2.2 reassigns them to canonical spec numbers.)

## 6. Exact output path

```
reports/refactor/<spec-id>/archaeology/extraction.md
```

(SKILL.md §1.4: `reports/refactor/<spec-id>/archaeology/<basename>.md`;
basename of `core/services/extraction.py` is `extraction`. `<spec-id>` is the
spec argument the skill was invoked with — not given in this scenario.)

## Probe findings beyond the questions

- **Dangling knowledge reference:** §1.4's "full recipe" and finding schema are
  delegated to a knowledge file that does not exist in this skill copy. The
  subject-word filter list is therefore only partially specified
  (`fix|retry|timeout|crash|...`) and the archaeology-file schema must be
  reconstructed from the LR-T candidate schema in `agents/inventory-scout.md`.
- The only literal archaeology commands anywhere in the skill are the two
  scout-inline lines in `agents/inventory-scout.md` (`git log --follow
  --oneline ... | head -50`, `git log --follow -p ... | head -500`).
