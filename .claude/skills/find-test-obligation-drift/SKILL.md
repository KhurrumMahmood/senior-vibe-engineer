---
name: find-test-obligation-drift
description: |
  Advisory SUSPECT diff analyzer that maps touched files to expected
  verification tiers from `.claude/docs/testing.md` and
  `development-workflow.md`, then flags missing nearby test/smoke
  obligations.
argument-hint: "[paths... | --staged | --changed-from REF]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Mapping touched files or a git diff to expected tests and verification
  tiers before handoff: backend `/sites` code without tests,
  UI/template/JS without Playwright or site-page DOM contract coverage,
  new skill/script work without smoke tests, lint/tooling changes without
  quality-tool tests, and verification obligation drift on changed surfaces.
not_for: |
  Product workflow inventory (use `/map-product-workflow`), proving
  commands actually ran, choosing the final command for a risky bug, or
  blocking commits in v1. It is an advisory obligation check that
  complements the human final verification note.
language: any
framework: django
scans: [python, javascript, templates]
---

# /find-test-obligation-drift

Use this before finishing a multi-file change. It inspects explicit
paths, staged files, a ref diff, or the working tree diff and reports
where the touched surface implies a verification tier that the diff does
not appear to cover. For non-trivial `/sites` diffs, use its output to
confirm whether the relevant product-health scanner should have been run
before/after the change.

## Pipeline

```
.venv/bin/python .claude/skills/find-test-obligation-drift/scripts/run.py <paths...>
.venv/bin/python .claude/skills/find-test-obligation-drift/scripts/run.py --staged
.venv/bin/python .claude/skills/find-test-obligation-drift/scripts/run.py --changed-from main
```

Reports are written under
`reports/find-test-obligation-drift/scan-<UTC>/`.

## Detector Bands

- `missing_backend_test_obligation`
- `missing_ui_test_obligation`
- `missing_skill_smoke_obligation`
- `missing_quality_tool_test_obligation`

Promote a band to a diff-scoped lint only after fixture coverage, at
least one real fix, explicit false-positive handling, and low `/sites`
noise.
