# Shared skill conventions (project-agnostic)

This file holds the conventions every skill follows regardless of the
project it is used in. Host projects override or extend with a sibling
file (e.g. `<project>-specifics.md`) for project-specific bits such as
the venv path, test matrix, or worktree concurrency note.

The split exists so that a future `_lib/{core,language,framework,repo}/`
reorganization can move this file under `_lib/core/` without rewriting
project-specific content. See `portability-roadmap.md` for the planned
move.

---

## Skill hygiene

- Keep reusable procedure in `SKILL.md`.
- Keep project-specific rules, examples, known false positives, and
  historical learnings in `knowledge/<project>-specifics.md`, this
  shared file, or other supplementary docs.
- If a `SKILL.md` starts naming files, memories, scan IDs, or
  one-off targets outside argument examples, move that content into a
  supplementary file and leave a pointer.

## Frontmatter contract

Every skill's `SKILL.md` declares an agent decision contract via
frontmatter. The full spec lives in `skill-frontmatter.md`. Required
fields for new skills:

- `name`, `description`, `argument-hint`, `allowed-tools`,
  `user-invocable` (existing surface).
- `tier`, `job`, `best_for`, `not_for`, `language`, `framework` (new
  agent decision contract).

Validate with `.venv/bin/python scripts/skill_meta.py lint`.

## Report directory layout

Every skill writes its artifacts under a timestamped scan directory
with a `latest` symlink, so human review and `reports/_meta/`
aggregation have a predictable location to read from:

```
reports/<skill-name>/
├── scan-<YYYYMMDD-HHMMSS>/   # one per run
│   └── ... skill-specific subtree ...
└── latest -> scan-<YYYYMMDD-HHMMSS>  # always points to newest
```

The `latest` symlink is what `/fix-workflow` follows when you invoke it
with a finding ID (`cluster:jscpd-0001`). Skills MUST update the
symlink at the end of every run.

Skill-specific subtrees (inventory/, scout/, findings/, jscpd/, etc.)
are documented in each skill's own `knowledge/` directory.

## Effectiveness log

Every skill's final stage appends one line to
`reports/_meta/effectiveness.jsonl` so we can measure whether cleanups
are actually reducing findings over time.

Schema:

```json
{
  "skill": "find-dormant",
  "scan_id": "scan-20260419-062049",
  "ts": "2026-04-19T06:20:49Z",
  "target": "core/services/",
  "findings_total": 27,
  "buckets": {"certain_delete": 4, "orphan_endpoint": 0,
              "quasi_dead_broken": 4, "false_positive": 17,
              "unverified_budget": 2},
  "notes": "optional free-text"
}
```

Append entries with the `scripts/log_effectiveness.py` helper (stdlib-
only, so it runs under `python3`) — don't hand-craft JSON:

```bash
python3 scripts/log_effectiveness.py \
  --skill <skill-name> --scan-id "scan-${TS}" --target <target> \
  --findings-total N --buckets '{"bucket1": 1, ...}' [--notes "..."]
```

Run `python3 scripts/skill_effectiveness.py` to aggregate the jsonl
into a markdown dashboard at `reports/_meta/dashboard.md`.

## Markdown structure for scout outputs

Scout deliverables go under `reports/<skill>/scan-<TS>/scout/<id>.md`
with a standard shape: one `# Heading` per finding/candidate, a
`## Context` block, a `## Assessment` block, and an explicit
`## Recommendation` block. The orchestrator's report aggregator reads
these headings directly.

## No raw line numbers in prose

Comments, docstrings, report prose, and scout outputs reference symbolic
names (`clean_samples guard`, `UI-chrome filter`, `preseed_expected_values
per-sample loop`), **never** raw line numbers like `L191` or
`ppc_loop.py:501`.

**Why:** line numbers rot the instant anyone edits above them. A `see
L237` comment becomes a lie within a week and silently misleads every
future reader. A comment that says "the `clean_samples guard` in
`orchestrator.py`" stays correct as long as the name survives — and if
the name goes away, the comment fails loudly instead of silently
pointing at the wrong line.

**Exceptions:** stack traces, git-archaeology commit references (pinned
hashes), and fixture output formats are fine to use line numbers — they
already lock to a point-in-time snapshot, not to live code.

**How to apply:** when you have to reference a specific piece of code,
use the function/class/variable/block name. If no suitable symbol
exists, name the nearest landmark and describe the relative position
("inside `_run_phase_3`, the retry-budget loop").

## Shared design references

- `interface-depth.md` — project-agnostic rubric for deciding whether
  an extraction, helper, module split, or adapter actually improves
  depth, locality, and testability.
- `skill-frontmatter.md` — the agent decision contract spec.
- `portability-roadmap.md` — the planned `_lib/` reorganization.

## Concurrency / worktree note

There is **no universal worktree concurrency guard** documented across
skills. Specific skills have their own guards (e.g. `/fix-workflow`
confirms the current worktree before edits; `/refactor-subsystem`
checks `git status --porcelain` before Phase 1 and before every Phase 5
batch). `/find-*` skills are read-only audits and don't need a guard.

If a future refactor adds a dual-worktree workflow, the shared guard
lives in the host project's local conventions overlay until promoted
here.
