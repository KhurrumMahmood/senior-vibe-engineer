---
name: adapt-project
description: Build a deterministic canonical host profile and project adapter, then run the mandatory evidence-backed quality-perimeter audit before reporting adoption readiness. Use when onboarding or re-profiling Python/Django, TypeScript/Node/React, Rust, Go, or mixed repositories. Writes scan artifacts by default; durable host-profile/adapter writes require --apply, and --no-host-write keeps dogfood artifacts outside the host.
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
produces: [host_profile, adapter, perimeter, adaptation_report, standardization_cautions]
evidence_required: [adapter, report, host_profile, perimeter, perimeter_report]
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

- `scripts/project_adapt.py discover` writes a scan directory containing
  `host-profile.json`, `adapter.yml`, `perimeter.json`, both human reports,
  and `evidence.json`.
- The scan's `evidence.json` maps the required evidence tokens plus the host
  profile and perimeter artifacts, satisfying
  this skill's `evidence_required: [adapter, report]` declaration.
- `scripts/evidence_gate.py check --skill adapt-project --scan-dir <scan>`
  exits 0 before the run is called done.
- Host writes are absent unless `--apply` was explicitly requested; a
  dogfood run with `--no-host-write` uses an `--artifact-root` outside
  the host project.
- The summary surfaces high-confidence facts, standardization cautions,
  sensitive surfaces, and open questions without inferring project
  philosophy.
- Exit 0 means the mandatory profile-derived perimeter has no uncovered
  significant cells. Exit 1 means artifacts were produced but adoption stays
  incomplete; exit 2 means profiling or audit execution itself failed.

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

   ```bash
   .venv/bin/python scripts/project_adapt.py discover \
     --project-root "${PROJECT_ROOT}" \
     --artifact-root "${ARTIFACT_ROOT}"
   ```

   Add `--no-host-write` for dogfood runs, or `--apply` only after the
   user explicitly wants durable project state written.

3. Read `host-profile.json`, `adapter.yml`, `perimeter.md`, and `report.md`.
4. Surface:
   - high-confidence facts;
   - standardization cautions;
   - sensitive surfaces;
   - uncovered root/language cells and reason-bearing accepted exclusions;
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
- `host-profile.json` / `.yml` — deterministic per-root stack, command,
  exclusion, and assertion evidence.
- `perimeter.json` / `.md` — executable-evidence coverage matrix and gaps.
- `report.md` — human-readable summary.
- `evidence.json` — evidence manifest for `evidence_gate.py`.

Durable project state, when `--apply` is used:

- `.engineering/project/adapter.yml`
- `.engineering/project/host-profile.json`

Reruns merge generated adapter keys while preserving host-owned extension keys.
They never replace host instruction/identity files or an approved interview
profile.

## Dogfood

For host-a-style dogfood without touching the host project:

```bash
.venv/bin/python scripts/project_adapt.py discover \
  --project-root /path/to/host-a \
  --artifact-root /private/tmp/engineering-skills-dogfood/host-a \
  --no-host-write
```

Then pair it with `/project-interview` and write an evaluation:

```bash
.venv/bin/python scripts/project_adapt.py evaluate \
  --project-root /path/to/host-a \
  --artifact-root /private/tmp/engineering-skills-dogfood/host-a \
  --reference host-a
```

Dogfood evaluation is host-read-only: the artifact root must stay
outside the project being evaluated.

## Standardization Guard

When the project looks like a vibe-coded or inherited mess, the correct
output is a stabilization map, not a canon. Mark common-but-suspect
patterns as `do not standardize yet`, route them to `/triage-debt`, and
only promote patterns with human approval plus tests, lints, or clear
examples of healthy use.

## Skill activation

Adaptation also records **which skills apply to this project**. Not every
skill fits every repo — a stdlib CLI toolkit has no routes, a backend-only
service has no frontend. Activation is the applicability switch: it is
separate from per-run scope (`<skill>-scope.md`, which narrows paths inside
an active skill) and from ADR 0020 maturity×stakes rung-gating (which
*standards* fire inside a skill).

State lives in the committed manifest at `.engineering/manifest.json` under
a `skills` block. The model is **default-on with an opt-out list** — most
skills apply, so you name only the exceptions and why:

```json
{
  "version": 1,
  "skills": {
    "default": "active",
    "inactive": {
      "find-route-sprawl": "No HTTP route surface (stdlib CLI toolkit).",
      "find-frontend-duplication": "No application frontend (only test fixtures)."
    }
  }
}
```

Record exceptions during adaptation with the manifest CLI (stdlib, no venv
needed — it must run on a fresh host before any venv exists):

```bash
python3 scripts/manifest.py --project-root <repo> deactivate find-route-sprawl "No HTTP route surface."
python3 scripts/manifest.py --project-root <repo> activate find-route-sprawl   # re-enable
python3 scripts/manifest.py --project-root <repo> show                         # list state
```

Consumers gate on it before doing work:

- in Python: `engineering_home.is_skill_active(root, name)` /
  `engineering_home.inactive_reason(root, name)`;
- in shell: `python3 scripts/manifest.py --project-root <repo> is-active <skill>`
  (exit `0` active, `1` inactive).

A flipped allowlist (`"default": "inactive"` plus an `active` list) is
supported for locked-down repos, but default-on is the norm. Today the
operator records the opt-out list by hand from adaptation findings;
auto-proposing it from discovery is a follow-on.

## When things go sideways

| Symptom | Action |
|---|---|
| `scripts/project_adapt.py discover` exits nonzero | Surface the exact stderr and stop; do not claim `adapter.yml`, `adapter.json`, `report.md`, or `evidence.json` landed |
| `project_adapt.py` reports `--apply and --no-host-write are mutually exclusive` | Pick one mode: `--apply` for durable host state, or `--no-host-write` for dogfood/read-only evaluation |
| `project_adapt.py` reports `--no-host-write requires --artifact-root outside --project-root` | Move `--artifact-root` outside the host project and rerun; do not write dogfood artifacts inside the repo being evaluated |
| `scripts/evidence_gate.py check` reports no `evidence.json` manifest | Treat the adaptation as incomplete; rerun discovery or inspect the scan directory before claiming done |
| `evidence_gate.py check` reports missing `adapter` or `report` evidence | Fix the scan so `evidence.json` points to existing `adapter.yml` and `report.md`, then rerun the gate |
| `evidence_gate.py check` reports malformed JSON or missing scan dir | Surface the usage/data error and stop; do not fabricate a passing evidence transcript |

## Inspiration

This skill was inspired in part by GAIA React's agent workflow ideas,
especially its fitness, forensics, audit, and review-gate patterns:
https://github.com/gaia-react/gaia
