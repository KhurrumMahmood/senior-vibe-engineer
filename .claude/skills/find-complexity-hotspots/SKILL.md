---
name: find-complexity-hotspots
description: Detect likely algorithmic, Django ORM, and structural complexity hotspots in Python code without changing production files. Runs a stdlib AST scan for nested loops, membership scans, sorting inside loops, QuerySet/manager calls inside loops, and high-branch functions; writes a timestamped report with ranked advisory findings. Use when a subsystem feels slow, export/discovery/extraction paths are growing expensive, or a refactor inventory needs a first-pass performance/complexity lead list.
argument-hint: "<paths>"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Read-only scans for performance and complexity leads: nested loops,
  repeated membership scans, sort-in-loop patterns, Django QuerySet calls
  inside loops, and unusually branchy functions. Useful before
  `/refactor-subsystem`, after export/discovery/extraction changes, or
  when a reviewer says "this path feels expensive."
not_for: |
  Implementing optimizations (use `/fix-workflow cluster:<symbol>` or
  direct edits after a human picks a finding). SQL query-plan tuning,
  database indexing decisions, benchmark harness design, or memory
  profiling. Broad architecture smells like omnibus modules (use
  `/find-omnibus`) or view/service layer leaks (use `/find-layer-violation`).
language: python
framework: django
---

# /find-complexity-hotspots

You are running a **read-only SUSPECT audit**. The scanner produces
leads, not verdicts. Treat every finding as "worth reading" until
surrounding code, input sizes, and tests prove it actionable.

## Scope

- **Target path:** required positional argument(s). Accepts files,
  directories, and glob patterns. Point it at the subsystem to scan —
  there is no whole-repo default.
- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python`; all skill scripts are stdlib-only but
  use the project venv for consistency with the host project's agent rules.
- **Output:** `reports/find-complexity-hotspots/scan-<TS>/` with
  `detections.jsonl`, `report.md`, `findings.json`, and a `latest`
  symlink.
- **No production edits.** This skill never changes app code.

Read `references/reading-notes.md` only when judging whether a finding
is interesting enough to recommend follow-up.

## Pipeline

Run the single orchestrator unless you need to debug an intermediate:

```bash
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py <paths>
```

Useful options:

```bash
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py <paths>
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py <paths> --max-findings 40
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py <paths> --include-tests
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py <paths> --skip-effectiveness-log
```

The detector can also be run directly:

```bash
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/detect.py \
  --project-root "$(pwd)" \
  --output /tmp/complexity-hotspots.jsonl \
  <paths>
```

## Finding Buckets

- `django-query-in-loop` — likely N+1 ORM/API shape. Check whether a
  bulk query, join, `select_related`, `prefetch_related`, grouped
  lookup, or service-level precomputation preserves filters and
  authorization.
- `nested-loop` — pairwise or repeated scan shape. Check duplicate-key,
  ordering, and "first vs all matches" semantics before replacing with
  a map/set/grouping.
- `membership-scan-in-loop` — `x in list` / `not in list` style checks
  under iteration. Convert to `set` or `dict` only when equality,
  normalization, hashability, and ordering behavior are safe.
- `sort-in-loop` — repeated ordering work. If the same input is reused,
  sort once; if only top-k is needed, consider heap/select logic; if
  each loop item has its own candidate set, measure before changing.
- `repeated-scan-in-loop` — `filter()` / `map()` / `sum()` / `any()` /
  `all()` over another collection inside a loop. Consider indexing or
  combining passes if the collections can be large.
- `high-branch-function` — high approximate branch count and LOC. This
  is usually a readability/refactor lead, not necessarily a runtime
  bottleneck.

## How To Summarize

Report in 10 lines or fewer:

- total findings and bucket counts,
- the top 3 interesting candidates with path + symbol,
- whether anything looks actionable now or just "measure first",
- path to `reports/find-complexity-hotspots/latest/report.md`,
- suggested next step (`/fix-workflow cluster:<symbol>`,
  `/refactor-subsystem <spec>`, or no action).

Do not enumerate every finding in chat. The report is the source of
truth.

## Safety Notes

- Scanner output is intentionally conservative and heuristic. A false
  positive is cheaper than missing an expensive export/discovery path.
- Do not optimize cold code or tiny collections. Name the expected data
  size before recommending a change.
- Preserve output order, duplicate handling, missing-record behavior,
  permissions, tenant/site filters, pagination, soft-delete filters,
  and cache invalidation.
- Add a benchmark or representative final-output check when the
  improvement is non-obvious.

Inspired by https://github.com/Kappaemme-git/codex-complexity-optimizer
