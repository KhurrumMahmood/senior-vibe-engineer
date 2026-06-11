---
name: find-async-lifecycle-drift
description: |
  Advisory SUSPECT scan for polling, job, cancel/resume, and export
  lifecycle drift on `/sites`: unguarded polling, missing terminal
  handling, stale response hazards, duplicate job starts, and missing
  retry/cancel controls.
argument-hint: "[paths... - defaults to the /sites route surface]"
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

Run this before or after `/sites` work that starts background jobs,
polls progress, exports files, downloads pages/images, or resumes work.
The output is advisory and should be triaged by confidence.

## Pipeline

```
.venv/bin/python .claude/skills/find-async-lifecycle-drift/scripts/run.py <paths...>
```

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
