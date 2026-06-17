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

## How success is judged

- The run is graded only by artifacts: pasted command output plus the
  generated `detections.jsonl`, `report.md`, `findings.json`, and
  `latest` symlink under `reports/find-complexity-hotspots/`. Do not
  claim a path was scanned without those artifacts.
- The scan verdict is one of `no-hotspots`, `measure-first`,
  `actionable-hotspot`, or `scan-blocked`. Use `measure-first` when a
  heuristic finding may matter but needs input-size or benchmark
  evidence before a fix is recommended.
- The summary names the target path, total findings, bucket counts, and
  top candidates from `report.md` or `findings.json`; never grade by
  memory or by a raw model impression of the code.
- The skill remains read-only. It can route to `/fix-workflow`,
  `/refactor-subsystem`, or benchmarking work, but it never optimizes
  code in this run.

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
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py \
  .claude/skills/find-complexity-hotspots
```

Useful options:

```bash
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py .claude/skills/find-complexity-hotspots --max-findings 40
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py .claude/skills/find-complexity-hotspots --include-tests
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py .claude/skills/find-complexity-hotspots --skip-effectiveness-log
```

The detector can also be run directly:

```bash
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/detect.py \
  --project-root "$(pwd)" \
  --output /tmp/complexity-hotspots.jsonl \
  .claude/skills/find-complexity-hotspots
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

If you dispatch an Agent to read the report, tell it this exact verdict
contract: it must return one of `no-hotspots`, `measure-first`,
`actionable-hotspot`, or `scan-blocked`, and every candidate must cite
the report row or command output that supports it. Agent output without
artifact citations is not evidence.

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

## Replay check

After editing this skill or its detector contract, run:

```bash
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py --help
.venv/bin/python .claude/skills/find-complexity-hotspots/scripts/smoke.py
```

The smoke script is the replay case: it scans the good/bad fixture pair
and asserts that representative hotspot bands are emitted while the clean
fixture stays clean. Paste the command output when using it as repair
evidence.

## When things go sideways

| Symptom | Action |
|---|---|
| No target path was supplied | The argparse failure is the correct outcome; re-run with one or more explicit files, directories, or globs. |
| The report shows a likely hotspot on tiny or cold data | Use verdict `measure-first`, name the unknown input size, and do not recommend an optimization yet. |
| Detector succeeds but effectiveness logging fails | Keep the report artifacts, state the logging failure, and do not rerun the detector solely to log. |
| A direct detector run writes JSONL but no markdown report | State that only the debug artifact exists; run `scripts/run.py` for the standard report before presenting a scan verdict. |
| Agent triage omits report citations | Reject that dispatch output and read the report directly; do not use uncited Agent claims as findings. |

Inspired by https://github.com/Kappaemme-git/codex-complexity-optimizer
