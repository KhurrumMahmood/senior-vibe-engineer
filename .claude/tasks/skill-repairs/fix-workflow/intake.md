# Intake — /fix-workflow repair

Date: 2026-06-12. Target: `.claude/skills/fix-workflow/` (SKILL.md +
knowledge/fix-shapes.md + knowledge/learnings.md). Pre-repair copy
frozen at `/tmp/skill-repairs-old/fix-workflow` (probe-only path,
untracked).

## Evidence of execution-time failure (Stage 0 entry)

1. **Class-2 ceremony hit** — Step 5 mandates appending a cluster
   entry to `reports/duplication/learnings.md`, which nothing reads;
   the skill's only consumed learnings surface is the internal
   `knowledge/learnings.md`. Source:
   `.claude/tasks/skill-repairs/class-sweeps-spec.md` Class 2 hit 3
   (citing SKILL.md:235, 44, 263-265) and its Batch-fix spec entry.
2. **Class-1 hit** — no declared-verdict block. Source:
   class-sweeps-spec.md Class 1 hit table, fix-workflow row
   (SKILL.md:119): "regression test first and green;
   behavior-preserving commit separate from bug-fix commit; matrix
   run."
3. **Board item** — Step 7 (closeout) lacks a class-lift gate: name
   the fixed defect's class, define the cheapest detector, run it,
   paste hits — the repair-skill Stage 8 pattern.

## Orchestrator pre-read observation (to be scout-verified)

SKILL.md contains six bare `knowledge/` references (lines 42, 116,
199, 206, 221, 334) promising worktree paths, a test matrix, commit
verb conventions + message template, concurrency guard commands, and
the jscpd re-scan command — but `knowledge/` contains only
`fix-shapes.md` and `learnings.md`. The promised content exists
nowhere in the repo (learnings.md R10 and fix-shapes.md §2a step 5
also point at the same missing matrix). Headline artifact-reality
drift: a filename appears to have been stripped at extraction time.

## Scale gate

**Full loop** — execution-heavy (the skill edits code, runs tests,
and produces commits) and ≥3 high-severity findings already on file.
Stage 7 dogfood substituted with live verification of the script the
skill calls (`scripts/log_effectiveness.py`) because no foreign host
repo is available to this run; substitution stated here and in
verification.md.

## Role isolation

Orchestrator cannot nest the Agent tool; fresh-context roles (frame
review, scout, implementer, verifier, lift probes) run via `claude -p`
with self-contained prompts. Lift probes use `--model haiku`
(weakest-tier probes are the point); other roles use the default
model.
