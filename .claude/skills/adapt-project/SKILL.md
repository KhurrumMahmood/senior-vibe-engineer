---
name: adapt-project
description: Discover objective host-project facts and scaffold a project adapter for engineering-skills. Reads stack markers, commands, tests, CI, docs, source roots, domain terms, sensitive surfaces, existing guardrails, and skill overlays; writes adapter artifacts under reports/adapt-project/scan-<TS>/ by default. Host writes to .claude/project/adapter.yml require --apply, and --no-host-write is the dogfood mode for evaluating another project without touching it.
argument-hint: "[--project-root <path>] [--artifact-root <path>] [--apply|--no-host-write]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  Adapting the portable engineering-skills ecosystem to a new host
  project. Use when onboarding a repo, dogfooding against a reference
  project, or regenerating local adapter facts after stack/CI/test
  changes. Produces project adapter facts, not human intent.
not_for: |
  Capturing project purpose, risk posture, desired direction, or
  intentional tradeoffs (use /project-interview). Cleaning up a messy
  codebase (use /triage-debt then the maintenance loop). Installing the
  runtime itself (use /engineer-init). Treating common legacy patterns
  as canonical without review.
escalate_to: |
  /project-interview when discovery finds ambiguous priorities,
  vibe-coded surfaces, or patterns that are common but not clearly
  healthy. /prevent-regression after a discovered convention is
  human-approved and detectable.
language: any
framework: any
lanes: [project-adaptation]
stage: discover
entrypoint: true
produces: [adapter, adaptation_report, standardization_cautions]
evidence_required: [adapter, report]
risk_triggers: [legacy, high-churn, missing-tests, sensitive-surface]
max_overhead: "Stop after discovery and write unresolved questions; do not infer project philosophy."
---

# /adapt-project

Discover objective facts about a host project and turn them into a
project adapter. The adapter is the operational half of localizing
engineering-skills: stack, commands, tests, CI, source roots, docs,
domain terms, sensitive surfaces, existing guardrails, and candidate
overlays.

Do not confuse observed frequency with health. A messy repo may have
many repeated patterns that are exactly what the adapter should warn
against standardizing. Discovery reports what exists; `/project-interview`
and human review decide what deserves to become doctrine.

## Forms

```bash
/adapt-project
/adapt-project --project-root /path/to/repo
/adapt-project --project-root /path/to/repo --artifact-root /private/tmp/adapt/foo --no-host-write
/adapt-project --apply
```

Default behavior writes only a timestamped report under
`reports/adapt-project/scan-<TS>/`. `--apply` additionally writes the
durable adapter to `.claude/project/adapter.yml` in the host project.
`--no-host-write` is mutually exclusive with `--apply` and is the
dogfood mode for evaluating another repo. When `--no-host-write` is
used, `--artifact-root` must be outside the host project.

## Pipeline

1. Resolve `PROJECT_ROOT` and `ARTIFACT_ROOT`.
2. Run discovery:

   ```bash
   .venv/bin/python scripts/project_adapt.py discover \
     --project-root "${PROJECT_ROOT}" \
     --artifact-root "${ARTIFACT_ROOT}"
   ```

   Add `--no-host-write` for dogfood runs, or `--apply` only after the
   user explicitly wants durable project state written.

3. Read the generated `adapter.yml` and `report.md`.
4. Surface:
   - high-confidence facts;
   - standardization cautions;
   - sensitive surfaces;
   - open questions that require `/project-interview`.
5. Before claiming done, run the evidence gate on the scan directory:

   ```bash
   .venv/bin/python scripts/evidence_gate.py check \
     --skill adapt-project \
     --scan-dir reports/adapt-project/latest
   ```

   If using an external artifact root, pass that scan path explicitly.

## Output

Each scan directory contains:

- `adapter.yml` — machine-readable adapter facts.
- `adapter.json` — same payload for tools that prefer JSON.
- `report.md` — human-readable summary.
- `evidence.json` — evidence manifest for `evidence_gate.py`.

Durable project state, when `--apply` is used:

- `.claude/project/adapter.yml`

## Dogfood

For PNCI-style dogfood without touching the host project:

```bash
.venv/bin/python scripts/project_adapt.py discover \
  --project-root /path/to/pnci-pricing \
  --artifact-root /private/tmp/engineering-skills-dogfood/pnci-pricing \
  --no-host-write
```

Then pair it with `/project-interview` and write an evaluation:

```bash
.venv/bin/python scripts/project_adapt.py evaluate \
  --project-root /path/to/pnci-pricing \
  --artifact-root /private/tmp/engineering-skills-dogfood/pnci-pricing \
  --reference pnci-pricing
```

Dogfood evaluation is host-read-only: the artifact root must stay
outside the project being evaluated.

## Standardization Guard

When the project looks like a vibe-coded or inherited mess, the correct
output is a stabilization map, not a canon. Mark common-but-suspect
patterns as `do not standardize yet`, route them to `/triage-debt`, and
only promote patterns with human approval plus tests, lints, or clear
examples of healthy use.

## Inspiration

This skill was inspired in part by GAIA React's agent workflow ideas,
especially its fitness, forensics, audit, and review-gate patterns:
https://github.com/gaia-react/gaia
