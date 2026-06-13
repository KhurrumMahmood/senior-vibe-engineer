---
name: find-workflow-state-gaps
description: |
  Advisory SUSPECT scan for workflow state coverage gaps in JavaScript
  and templates: loading, empty, failure, retry/cancel, disabled, and
  mobile states. Also imports workflow-duplication findings as
  state-authority context.
argument-hint: "[paths... - defaults to host-declared workflow targets]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Checking whether async product workflow surfaces have the states a
  senior engineer would expect before UI polish or after a cleanup that
  moves route/template/JS ownership: loading, empty, failure, recovery,
  disabled, and mobile/responsive states.
not_for: |
  Visual QA, accessibility audits, or replacing Playwright. This is a
  text-surface advisory scanner whose findings need judgment before
  becoming guardrails.
language: any
framework: any
scans: [javascript, templates]
---

# /find-workflow-state-gaps

Use this as a state-coverage audit for async workflow surfaces. It is
especially useful before adding another polling panel or after a cleanup
that moves route/template/JS ownership.

## How success is judged

- The run writes a real scan directory under
  `reports/find-workflow-state-gaps/scan-<UTC>/` containing
  `detections.jsonl`, `report.md`, and `findings.json`, and updates the
  `latest` symlink.
- The closing summary pastes the runner's exact `wrote <report_dir>`
  line and the finding count from `findings.json`; claims without those
  artifacts do not count.
- Every reported gap names one detector band and one follow-up decision:
  state coverage fix, Playwright/manual verification, accepted
  false-positive, or guard proposal.
- The run stays advisory. It does not edit templates, JavaScript, tests,
  or workflow registries.

## Pipeline

Run the one-shot wrapper from the repository root:

```bash
.venv/bin/python .claude/skills/find-workflow-state-gaps/scripts/run.py <paths...>
```

If `<paths...>` is omitted, the scanner examines the host-declared
workflow targets from the shared workflow descriptor helpers. In a repo
with no workflow descriptor, pass explicit file or directory paths. To
scan only one surface, pass that specific path.

For a raw detector replay without report rendering:

```bash
.venv/bin/python .claude/skills/find-workflow-state-gaps/scripts/detect.py \
  --project-root "$(pwd)" \
  --no-workflow-duplication \
  --output /tmp/workflow-state-gaps.jsonl \
  <paths...>
```

Render an existing raw detector file:

```bash
.venv/bin/python .claude/skills/find-workflow-state-gaps/scripts/report.py \
  /tmp/workflow-state-gaps.jsonl \
  --target "<workflow surface>" \
  --output /tmp/workflow-state-gaps.md
```

## Detector Bands

- `missing_loading_state`
- `missing_empty_state`
- `missing_failure_state`
- `missing_recovery_state`
- `missing_disabled_state`
- `missing_mobile_state`
- `state_authority_context:*` imported from `/find-workflow-duplication`
  when that detector is present.

## Judgment Points

- Treat this scan as a prompt for inspection, not proof of a UI bug.
  Before recommending code work, read the flagged file and confirm the
  state is truly absent from the rendered path.
- A low-confidence `missing_mobile_state` finding requires a viewport
  check or a named reason it is out of scope; do not turn it directly
  into a guard.
- A `state_authority_context:*` row is context for ownership drift. Do
  not fix it inside this skill; hand it to `/find-workflow-duplication`
  or the product-topology skill named by the row.
- If the scan produces zero rows, still report the scan directory and
  finding count. A clean scan is a valid artifact only when `findings.json`
  confirms zero findings.

## Replay Case

The fixture smoke test is the cheap replay case for the detector bands:

```bash
.venv/bin/python .claude/skills/find-workflow-state-gaps/scripts/smoke.py
```

It must print `find-workflow-state-gaps smoke OK`. If it fails, do not
trust a catalog-wide scan until the fixture failure is repaired.

## When things go sideways

| Symptom | Action |
|---|---|
| Wrapper exits non-zero or prints no `wrote` line | Stop, paste stdout/stderr, and do not claim a report was produced |
| `reports/find-workflow-state-gaps/latest` is missing or points at no directory | Report the broken artifact path and re-run the wrapper before judging findings |
| A path argument does not exist or expands to no `.js` / `.html` files | State that the target produced no scanned files and ask for a corrected path; do not broaden scope silently |
| No paths were passed and the host has no workflow descriptor | Report that no default workflow targets were available; re-run with explicit file or directory paths |
| Imported workflow-duplication context fails | Re-run with the raw detector and `--no-workflow-duplication`, paste that command output, and mark authority-context rows unavailable |
| Findings are obviously generated from fixture, vendored, or generated files | Mark them false-positive in the summary with the path evidence; do not delete rows from `detections.jsonl` |

## Repository layout

```
.claude/skills/find-workflow-state-gaps/
├── SKILL.md
└── scripts/
    ├── detect.py
    ├── report.py
    ├── run.py
    └── smoke.py
```
