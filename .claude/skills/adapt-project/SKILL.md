---
name: adapt-project
description: Discover objective host-project facts and scaffold a project adapter for engineering-skills. Reads stack markers, commands, tests, CI, docs, source roots, domain terms, sensitive surfaces, existing guardrails, and skill overlays; writes adapter artifacts under reports/adapt-project/scan-<TS>/ by default. Host writes to .engineering/project/adapter.yml require --apply, and --no-host-write is the dogfood mode for evaluating another project without touching it.
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

## How success is judged

- The installed skill's `scripts/discover.py` writes a scan directory containing
  `adapter.yml`, `adapter.json`, `report.md`, and `evidence.json`.
- The scan's `evidence.json` maps the required evidence tokens
  `adapter` and `report` to `adapter.yml` and `report.md`, satisfying
  this skill's `evidence_required: [adapter, report]` declaration.
- The installed skill's `scripts/check_evidence.py --scan-dir <scan>` exits 0
  before the run is called done.
- Host writes are absent unless `--apply` was explicitly requested; a
  dogfood run with `--no-host-write` uses an `--artifact-root` outside
  the host project.
- The summary surfaces high-confidence facts, standardization cautions,
  sensitive surfaces, and open questions without inferring project
  philosophy.

## JavaScript-family v1 contract

Source-root facts retain the reference Python count and add
`typescript_files` with a `.ts`/`.tsx` breakdown, `javascript_files` with a
`.js`/`.jsx`/`.mjs`/`.cjs` breakdown, and `source_languages`. The large-root
standardization caution fires when any of the Python, TypeScript, or
JavaScript counts exceeds 200. JavaScript-family counts exclude `node_modules`,
`dist`, `build`, `generated`, `vendor`, and test descendants, as well as
declaration, `*.test`/`*.spec`, generated, and minified files.

This is objective source-root discovery, not a Node-stack adapter. A
`package.json` may contribute package-manager markers and declared commands,
but it does not establish React, Vite, Next, Express, or any other framework.
This branch does not infer framework behavior from JavaScript or TypeScript,
resolve modules, type-check the host, or decide that observed code is a
healthy standard.

## Forms

```bash
/adapt-project
/adapt-project --project-root /path/to/repo
/adapt-project --project-root /path/to/repo --artifact-root /private/tmp/adapt/foo --no-host-write
/adapt-project --apply
```

Default behavior writes only a timestamped report under
`reports/adapt-project/scan-<TS>/`. `--apply` additionally writes the
durable adapter to `.engineering/project/adapter.yml` in the host project
(the committed-zone state home, ADR 0021 — not under any one agent's
folder). `--no-host-write` is mutually exclusive with `--apply` and is the
dogfood mode for evaluating another repo. When `--no-host-write` is
used, `--artifact-root` must be outside the host project.

## Pipeline

1. Resolve `PROJECT_ROOT` and `ARTIFACT_ROOT`.
2. Run discovery:

   <!-- installed-command:discover:start -->
   ```bash
   PROJECT_ROOT="$(cd "${PROJECT_ROOT:-.}" && pwd -P)" || exit $?
   ARTIFACT_ROOT="${ARTIFACT_ROOT:-$PROJECT_ROOT}"
   mkdir -p "$ARTIFACT_ROOT" || exit $?
   ARTIFACT_ROOT="$(cd "$ARTIFACT_ROOT" && pwd -P)" || exit $?
   ADAPT_PROJECT_SKILL="${ADAPT_PROJECT_SKILL:-.agents/skills/adapt-project}"
   cd "$ADAPT_PROJECT_SKILL"
   SCAN_DIR="$(python3 -I -S scripts/discover.py \
     --project-root "${PROJECT_ROOT}" \
     --artifact-root "${ARTIFACT_ROOT}")"
   printf '%s\n' "$SCAN_DIR"
   ```
   <!-- installed-command:discover:end -->

   Add `--no-host-write` only with an artifact root outside the project for a
   dogfood run, or add `--apply` only after the user explicitly wants durable
   project state written. Keep `ADAPT_PROJECT_SKILL` on its own preceding
   assignment line: a command-local environment assignment does not affect
   expansion of `$ADAPT_PROJECT_SKILL` in the same command line.

3. Read the generated `adapter.yml` and `report.md`.
4. Surface:
   - high-confidence facts;
   - standardization cautions;
   - sensitive surfaces;
   - open questions that require `/project-interview`.
5. Before claiming done, run the evidence gate on the scan directory:

   <!-- installed-command:check-evidence:start -->
   ```bash
   python3 -I -S scripts/check_evidence.py \
     --scan-dir "$SCAN_DIR"
   ```
   <!-- installed-command:check-evidence:end -->

   If discovery ran in a previous shell, pass its timestamped scan path
   explicitly instead of relying on `latest`.

## Output

Each scan directory contains:

- `adapter.yml` — machine-readable adapter facts (JSON-compatible YAML so
  the copied skill has no PyYAML dependency).
- `adapter.json` — same payload for tools that prefer JSON.
- `report.md` — human-readable summary.
- `evidence.json` — evidence manifest for the installed
  `scripts/check_evidence.py` command.

Durable project state, when `--apply` is used:

- `.engineering/project/adapter.yml`

## Dogfood

For host-a-style dogfood without touching the host project:

```bash
ADAPT_PROJECT_SKILL="${ADAPT_PROJECT_SKILL:-.agents/skills/adapt-project}"
cd "$ADAPT_PROJECT_SKILL"
python3 -I -S scripts/discover.py \
  --project-root /path/to/host-a \
  --artifact-root /private/tmp/engineering-skills-dogfood/host-a \
  --no-host-write
```

Read the resulting adapter and use `/project-interview` only for the human
questions that discovery explicitly leaves open. Dogfood discovery is
host-read-only: the artifact root must stay outside the project being
evaluated.

## Standardization Guard

When the project looks like a vibe-coded or inherited mess, the correct
output is a stabilization map, not a canon. Mark common-but-suspect
patterns as `do not standardize yet`, route them to `/triage-debt`, and
only promote patterns with human approval plus tests, lints, or clear
examples of healthy use.

## When things go sideways

| Symptom | Action |
|---|---|
| `scripts/discover.py` exits nonzero | Surface the exact stderr and stop; do not claim `adapter.yml`, `adapter.json`, `report.md`, or `evidence.json` landed |
| `discover.py` reports `--apply and --no-host-write are mutually exclusive` | Pick one mode: `--apply` for durable host state, or `--no-host-write` for dogfood/read-only evaluation |
| `discover.py` reports `--no-host-write requires --artifact-root outside --project-root` | Move `--artifact-root` outside the host project and rerun; do not write dogfood artifacts inside the repo being evaluated |
| `scripts/check_evidence.py` reports no `evidence.json` manifest | Treat the adaptation as incomplete; rerun discovery or inspect the scan directory before claiming done |
| `check_evidence.py` reports missing `adapter` or `report` evidence | Fix the scan so `evidence.json` points to existing `adapter.yml` and `report.md`, then rerun the gate |
| `check_evidence.py` reports malformed JSON or missing scan dir | Surface the usage/data error and stop; do not fabricate a passing evidence transcript |

## Inspiration

This skill was inspired in part by GAIA React's agent workflow ideas,
especially its fitness, forensics, audit, and review-gate patterns:
https://github.com/gaia-react/gaia
