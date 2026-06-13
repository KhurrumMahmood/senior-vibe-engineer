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
  tiers before handoff: host-declared product workflow backend code
  without tests, workflow UI/template/JS without Playwright or DOM
  contract coverage, new skill/script work without smoke tests,
  lint/tooling changes without quality-tool tests, and verification
  obligation drift on changed surfaces.
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
not appear to cover. Product backend/UI obligations are inferred only
from the host's `.engineering/docs/product-workflows.md` descriptor. If
that descriptor is absent, the run still checks skill-script and tooling
obligations, but it must not claim product workflow coverage was
evaluated.

## How success is judged

- `run.py` writes a report directory under
  `reports/find-test-obligation-drift/scan-<UTC>/` containing
  `detections.jsonl`, `findings.json`, and `report.md`, and updates
  `reports/find-test-obligation-drift/latest`.
- The console output is pasted in the handoff, including
  `workflow scope patterns: <N>`, `findings: <N>`, and `wrote <dir>`.
- If product backend/UI files are in scope, the run used at least one
  descriptor pattern from `.engineering/docs/product-workflows.md`; if
  `workflow scope patterns: 0`, the summary says product workflow
  obligations were not inferred.
- Findings are treated as advisory obligations, not proof that tests
  failed. The user-facing verdict is "obligation present/missing" with
  the pasted detector artifact, never "verified" based on a claim.
Write toward these gates from Stage 0.

Grade only by the report artifacts and real command output. A statement
that "the diff has enough tests" does not count unless `report.md` or
`detections.jsonl` backs it.

## Pipeline

### Stage 0 — Resolve target and descriptor context

Pick one input form:

- Explicit paths: pass them as positionals.
- Staged diff: pass `--staged`.
- Ref diff: pass `--changed-from REF`.
- No args: scans the working-tree diff.

Before interpreting product backend/UI absence, check the descriptor
state. The script prints the descriptor-derived pattern count; zero
means this shipped kit has no host product workflow scope to infer from.

### Stage 1 — Run the detector

```
.venv/bin/python .claude/skills/find-test-obligation-drift/scripts/run.py <paths...>
.venv/bin/python .claude/skills/find-test-obligation-drift/scripts/run.py --staged
.venv/bin/python .claude/skills/find-test-obligation-drift/scripts/run.py --changed-from main
```

Supported `run.py` flags:

- `paths` (zero or more): explicit files or directories.
- `--project-root DIR`: project root; defaults to current working
  directory.
- `--staged`: scan `git diff --cached`.
- `--changed-from REF`: scan `git diff REF`.
- `--skip-effectiveness-log`: write report artifacts without appending
  to `reports/_meta/effectiveness.jsonl`.

Reports are written under
`reports/find-test-obligation-drift/scan-<UTC>/`.

`run.py` returns exit 0 when report artifacts are written, even when it
finds obligations. Domain findings live in the report, not the process
exit code. `detect.py` and `report.py` are lower-level helpers; use
`run.py` for normal skill execution.

### Stage 2 — Read the report and emit the declared verdict

Open the generated `report.md` and `findings.json`.

Dispatch by declared verdict:

- **0 findings, workflow scope patterns > 0:** no drift found for the
  touched, descriptor-scoped surfaces. Still run the verification
  commands required by the actual task.
- **0 findings, workflow scope patterns = 0:** no generic skill/tooling
  drift found; product backend/UI obligations were not inferred because
  the host descriptor is absent or empty.
- **1+ findings:** list each detector band with file, recommendation,
  and obligation. These are advisory repair items; the owner either adds
  coverage or records a concrete reason the touched file did not need
  that tier.

## Detector Bands

- `missing_backend_test_obligation`
- `missing_ui_test_obligation`
- `missing_skill_smoke_obligation`
- `missing_quality_tool_test_obligation`

Promote a band to a diff-scoped lint only after fixture coverage, at
least one real fix, explicit false-positive handling, and low host
workflow noise.

## When things go sideways

| Symptom | Action |
|---|---|
| `git diff` form fails because the ref is unknown | Re-run with explicit paths or a valid `--changed-from REF`; paste the failing command output |
| `workflow scope patterns: 0` but the change is product backend/UI work | State that the host descriptor is absent or empty; do not infer product obligations from baked-in paths |
| Report directory cannot be written | Stop and report the exact write failure; do not claim the detector ran |
| `detections.jsonl` exists but `report.md` or `findings.json` is missing | Treat the run as incomplete; re-run `run.py` once, then report the missing artifact if it persists |
| Findings look like docs/comment-only false positives | Keep the finding in the report and add the human reason in the handoff; do not delete or rewrite detector output |
| A product workflow descriptor has malformed rows | The descriptor parser skips malformed rows; if the pattern count is lower than expected, fix the descriptor before trusting absence of product findings |

## Replay case

After material edits to this skill or its scripts, run the fixture smoke
and paste the output:

```bash
.venv/bin/python .claude/skills/find-test-obligation-drift/scripts/smoke.py
```

Also prove the normal CLI remains executable:

```bash
.venv/bin/python .claude/skills/find-test-obligation-drift/scripts/run.py \
  --project-root . \
  --skip-effectiveness-log \
  .claude/skills/find-test-obligation-drift/scripts/run.py
```
