---
name: find-workflow-state-gaps
description: |
  Advisory SUSPECT scan for `/sites` workflow state coverage gaps:
  loading, empty, success, partial, failed, retry/cancel, disabled,
  stale-job, permission, and mobile states. Also imports workflow
  duplication findings as state-authority context.
argument-hint: "[paths... - defaults to the /sites route surface]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Checking whether a `/sites` tab/workflow has the states a senior
  engineer would expect before UI polish: loading, empty, terminal,
  recovery, disabled, stale-job, permission, and mobile/responsive
  states.
not_for: |
  Visual QA, accessibility audits, or replacing Playwright. This is a
  text-surface advisory scanner whose findings need judgment before
  becoming guardrails.
language: any
framework: django
scans: [javascript, templates]
---

# /find-workflow-state-gaps

Use this as a state-coverage audit for the `/sites` workflow. It is
especially useful before adding another async panel or after a cleanup
that moves route/template/JS ownership.

## Pipeline

```
.venv/bin/python .claude/skills/find-workflow-state-gaps/scripts/run.py <paths...>
```

Reports are written under
`reports/find-workflow-state-gaps/scan-<UTC>/`.

## Detector Bands

- `missing_loading_state`
- `missing_empty_state`
- `missing_failure_state`
- `missing_recovery_state`
- `missing_disabled_state`
- `missing_mobile_state`
- Imported `/find-workflow-duplication` findings for workflow-authority
  context.
