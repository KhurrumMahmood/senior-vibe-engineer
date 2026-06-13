---
name: find-async-lifecycle-drift
description: |
  Advisory SUSPECT scan for polling, job, cancel/resume, and export
  lifecycle drift on configured product-workflow targets or explicit
  paths: unguarded polling, missing terminal handling, stale response
  hazards, duplicate job starts, and missing retry/cancel controls.
argument-hint: "[paths... - defaults to workflow_targets(project_root); empty without .engineering/docs/product-workflows.md]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Auditing async UI and backend lifecycle flows where AI-grown code often
  forgets cleanup: progress polling, start/cancel/resume/export paths,
  stale fetch response guards, duplicate-job protection, and terminal
  status handling.
not_for: |
  Proving Celery behavior, replacing integration tests, or blocking
  commits in v1. Use this as a baseline scanner before promoting a
  narrow lifecycle rule to `/prevent-regression`.
escalate_to: |
  /fix-workflow for isolated findings. When one band returns ≥5
  findings on one surface, treat the cluster as ONE
  standardize-and-enforce candidate: /decide the shared abstraction
  (poller / job-lifecycle primitive), extract it, then
  /prevent-regression to pin the band. Per-item fixes leave the
  generator in place.
language: any
framework: django
scans: [python, javascript]
---

# /find-async-lifecycle-drift

Run this before or after product-workflow work that starts background
jobs, polls progress, exports files, downloads pages/images, or resumes
work. The output is advisory and should be triaged by confidence.

Default scope is not hard-coded to `/sites`. With no positional paths,
`scripts/run.py` passes `None` into `detect()`, and
`product_health.expand_paths()` scans `workflow_targets(project_root)`
from `.engineering/docs/product-workflows.md` (`## Targets`). If that
descriptor or section is absent, the default target set is empty. To
scan a concrete surface, pass explicit positional paths after
`scripts/run.py`.

## How success is judged

- The runner exits 0 and prints the scan directory it wrote.
- `reports/find-async-lifecycle-drift/scan-<UTC>/detections.jsonl`,
  `report.md`, `findings.json`, and `latest` exist under the selected
  `--project-root`.
- The target scope is explicit in the command or comes from
  `workflow_targets(project_root)`; do not describe a no-descriptor run
  as a `/sites` scan.
- Findings are grouped by async lifecycle detector bands and are treated
  as advisory triage input, not proof that the workflow is broken.

## Pipeline

```
.venv/bin/python .claude/skills/find-async-lifecycle-drift/scripts/run.py <paths...>
```

`<paths...>` are positional path or glob arguments. Omit them only when
the host repo has declared `## Targets` in
`.engineering/docs/product-workflows.md`.

The runner writes `detections.jsonl`, `report.md`, `findings.json`, and
`latest` under `reports/find-async-lifecycle-drift/scan-<UTC>/`, and logs
an effectiveness row.

## Detector Bands

- `unguarded_polling_timer`: polling timer exists without a cleanup path.
- `missing_terminal_poll_stop`: progress/status polling observes terminal
  states without stopping the timer.
- `missing_stale_response_guard`: async fetch mutates UI without a
  request-generation, abort, or latest-response guard.
- `missing_recovery_control`: job progress UI lacks nearby retry, cancel,
  abort, or resume controls.
- `duplicate_job_path`: backend start/run/queue path dispatches work
  without an active/existing/running guard.

## When things go sideways

| Symptom | Action |
|---|---|
| Descriptor absent | Treat the default workflow target set as empty; pass explicit positional paths or add `## Targets` to `.engineering/docs/product-workflows.md`. |
| Zero findings | Check whether `detections.jsonl` is empty because the workflow target set expanded to no `.py` or `.js` files; rerun with explicit paths before calling the lifecycle surface clean. |
| Script failure | Re-run the exact `.venv/bin/python .claude/skills/find-async-lifecycle-drift/scripts/run.py ...` command, capture stderr, and fix the path/import/argparse failure before interpreting results. |
