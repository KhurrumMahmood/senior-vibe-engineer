---
name: project-interview
description: Build the human-approved project profile that complements /adapt-project discovery. Reads repository facts first, then interviews the user about purpose, maturity, critical workflows, risk posture, desired direction, intentional tradeoffs, known-bad legacy patterns, and do-not-break surfaces. Writes draft artifacts under reports/project-interview/scan-<TS>/ by default; durable .engineering/project/profile.yml, profile.md, and open-questions.md require --apply.
argument-hint: "[--project-root <path>] [--artifact-root <path>] [--apply|--no-host-write]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  Capturing the human side of adapting engineering-skills to a host
  project: project purpose, target users, important workflows,
  maturity, risk tolerance, desired future path, intentional tradeoffs,
  and known-bad patterns that should not become doctrine.
not_for: |
  Objective repo discovery (use /adapt-project). Feature planning
  inside an already-profiled project (use /plan-feature or the System
  tier). ADR authoring (use /decide). Cleanup execution (use
  /triage-debt, /fix-workflow, /refactor-subsystem).
escalate_to: |
  /adapt-project when repo facts are stale or missing. /decide when
  interview answers reveal a durable architectural choice. /triage-debt
  when the user identifies known-bad current patterns that need cleanup
  before standardization.
language: any
framework: any
lanes: [project-adaptation]
stage: frame
entrypoint: true
consumes: [repo_context, adapter]
produces: [project_profile, open_questions]
evidence_required: [profile, profile_summary, open_questions]
risk_triggers: [vibe-coded, legacy, unclear-goals, critical-workflow]
max_overhead: "Ask only questions that change the profile; park unresolved topics in open-questions.md."
---

# /project-interview

Create the durable project profile that tells engineering-skills what
the project is trying to be. `/adapt-project` can discover facts, but it
cannot safely infer purpose, priorities, risk posture, intentional
tradeoffs, or whether a repeated pattern is healthy.

The deliverable is a draft or applied profile:

- `.engineering/project/profile.yml` — machine-readable, human-approved
  project intent.
- `.engineering/project/profile.md` — readable summary.
- `.engineering/project/open-questions.md` — unresolved questions agents
  should revisit.

## Forms

```bash
/project-interview
/project-interview --project-root /path/to/repo
/project-interview --project-root /path/to/repo --artifact-root /private/tmp/adapt/foo --no-host-write
/project-interview --apply
```

Default behavior writes a draft under
`reports/project-interview/scan-<TS>/`. `--apply` writes durable files
under `.engineering/project/`. `--no-host-write` is the dogfood mode and
requires `--artifact-root` outside the host project.

## Pipeline

1. Run repo-fact discovery to seed the interview:

   ```bash
   .venv/bin/python scripts/project_adapt.py interview \
     --project-root "${PROJECT_ROOT}" \
     --artifact-root "${ARTIFACT_ROOT}"
   ```

   Add `--no-host-write` for dogfood or `--apply` only when the user
   wants durable project state written.

2. Read `profile.yml`, `profile.md`, and `open-questions.md`.
3. Ask only questions that cannot be answered from the repo and that
   materially change future agent behavior:
   - What is the project for, and who is it for?
   - Which workflows are correctness-critical?
   - Is this prototype, feature-shop, durable, or regulated work?
   - Where should agents slow down?
   - Which current patterns are intentional tradeoffs?
   - Which common current patterns are known bad and must not be
     standardized?
   - What should the project become next?
4. Update the profile draft with the user's answers if the run is
   interactive. If the user is unavailable, leave the answers as open
   questions.
5. Run the evidence gate:

   ```bash
   .venv/bin/python scripts/evidence_gate.py check \
     --skill project-interview \
     --scan-dir reports/project-interview/latest
   ```

## How Future Skills Use The Profile

- `/which-skill` tunes recommendations by maturity and risk posture.
- Planning skills treat critical workflows and intentional tradeoffs as
  prior constraints.
- `/adapt-project --apply` should prefer user-approved profile entries
  over inferred facts.
- `/prevent-regression` prioritizes guards for do-not-break surfaces.
- `/engineering-fitness` can grade profile completeness once that skill
  ships.

## Vibe-Coded Or Legacy Projects

The interview must explicitly ask what **not** to standardize. In a
messy project, repeated patterns are often scars, not examples. Capture
those under `open-questions.md` or the profile's standardization policy
so future agents do not turn accidental consistency into doctrine.

## Inspiration

This skill was inspired in part by GAIA React's agent workflow ideas,
especially its fitness, forensics, audit, and review-gate patterns:
https://github.com/gaia-react/gaia
