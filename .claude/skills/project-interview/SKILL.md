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

## How success is judged

- The run writes a draft scan under
  `${ARTIFACT_ROOT}/reports/project-interview/scan-<TS>/` by default, or
  additionally writes `.engineering/project/` only when `--apply` was
  explicitly requested.
- `profile.yml`, `profile.md`, `open-questions.md`, and `evidence.json`
  exist in the same scan directory, and the final reply pastes the exact
  `evidence_gate.py check` output for that scan.
- The stock-selected skill resolves both helpers from its own `scripts/`
  directory and runs under isolated stdlib Python; no repository-level
  `scripts/`, toolkit venv, or sibling skill is required.
- `--no-host-write` runs never write inside `${PROJECT_ROOT}`. The
  command must use an `${ARTIFACT_ROOT}` outside the host project, and
  every later read/check uses that same artifact root.
- User answers are captured in the draft profile, or unresolved topics are
  left in `open-questions.md`; do not claim human approval without a
  visible user answer.

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

0. Resolve the installed skill and artifact roots for this run:

   ```bash
   PROJECT_ROOT="${PROJECT_ROOT:-$(pwd)}"
   ARTIFACT_ROOT="${ARTIFACT_ROOT:-${PROJECT_ROOT}}"
   PYTHON_BIN="${PYTHON_BIN:-python3}"

   if [ -n "${PROJECT_INTERVIEW_SKILL_DIR:-}" ]; then
     SKILL_DIR="${PROJECT_INTERVIEW_SKILL_DIR}"
   elif [ -f ".agents/skills/project-interview/SKILL.md" ]; then
     SKILL_DIR="$(cd .agents/skills/project-interview && pwd)"
   elif [ -f ".claude/skills/project-interview/SKILL.md" ]; then
     SKILL_DIR="$(cd .claude/skills/project-interview && pwd)"
   else
     echo "error: cannot find installed project-interview skill" >&2
     exit 2
   fi
   ```

   If the user invoked `--no-host-write`, set `ARTIFACT_ROOT` to a
   directory outside `PROJECT_ROOT` before running the helper. Reuse the
   exact same `ARTIFACT_ROOT` for every later read and evidence gate.

1. Run repo-fact discovery to seed the interview:

   ```bash
   SCAN_DIR="$("${PYTHON_BIN}" -I -S \
     "${SKILL_DIR}/scripts/project_interview.py" draft \
     --project-root "${PROJECT_ROOT}" \
     --artifact-root "${ARTIFACT_ROOT}")"
   ```

   Add `--no-host-write` when the user requested it. The helper performs
   objective, lightweight discovery only and always writes an unapproved
   draft. Do not pass `--apply` here; durable apply happens only after
   visible human answers are captured and confirmed.

2. Read the printed scan directory:

   ```bash
   test -d "${SCAN_DIR}" || { echo "missing scan: ${SCAN_DIR}" >&2; exit 2; }
   ```

   Read `${SCAN_DIR}/profile.yml`, `${SCAN_DIR}/profile.md`, and
   `${SCAN_DIR}/open-questions.md`.
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
   interactive. Set `user_approved: true` only after visible answers and
   confirmation; repository facts never count as human approval. If the user
   is unavailable, keep `user_approved: false` and leave the answers as open
   questions. Update `profile.yml`, `profile.md`, and `open-questions.md`
   together so the evidence shapes describe the same state.
5. Run the evidence gate:

   ```bash
   "${PYTHON_BIN}" -I -S "${SKILL_DIR}/scripts/evidence_gate.py" check \
     --skill project-interview \
     --scan-dir "${SCAN_DIR}"
   ```

   Paste the gate output in the final reply. A claim that the artifacts
   exist is not enough.
6. If and only if the user invoked `--apply`, the evidence gate passed, and
   the visible answers support `user_approved: true`, apply the three profile
   artifacts:

   ```bash
   "${PYTHON_BIN}" -I -S \
     "${SKILL_DIR}/scripts/project_interview.py" apply \
     --project-root "${PROJECT_ROOT}" \
     --scan-dir "${SCAN_DIR}"
   ```

   `--apply` and `--no-host-write` are mutually exclusive intents. The helper
   refuses apply while `user_approved` is not true and rejects a symlinked
   `.engineering/project` destination.

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

## When things go sideways

| Symptom | Action |
|---|---|
| `--no-host-write` fails because the artifact root is inside the project | Stop, choose an artifact root outside `${PROJECT_ROOT}`, and rerun; do not retry without `--no-host-write` |
| The draft helper exits 2 | Paste stderr, fix the invocation or write-mode conflict, and do not claim a profile was produced |
| The printed scan directory is missing | Stop and report the printed path; do not fall back to a repo-local reports directory |
| Evidence gate reports missing tokens | Leave the run incomplete; name the missing token and scan directory in the user reply |
| User is unavailable for interview answers | Keep the generated draft and move unanswered items to `open-questions.md`; do not mark the profile approved |
| Apply reports `user_approved is not true` | Keep the draft, ask for the missing human answers or confirmation, and never flip approval from repository inference |
| `--apply` was requested but durable `.engineering/project/` writes fail | Keep the draft scan as evidence, paste the write failure, and do not claim durable profile files were written |

## Replay case

For artifact-root or evidence-gate changes, replay the dogfood form with a
temporary artifact root:

```bash
ARTIFACT_ROOT="$(mktemp -d)"
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
SKILL_DIR="${PROJECT_INTERVIEW_SKILL_DIR:-${PROJECT_ROOT}/.claude/skills/project-interview}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SCAN_DIR="$("${PYTHON_BIN}" -I -S \
  "${SKILL_DIR}/scripts/project_interview.py" draft \
  --project-root "$(git rev-parse --show-toplevel)" \
  --artifact-root "${ARTIFACT_ROOT}" \
  --timestamp project-interview-smoke \
  --no-host-write)"
"${PYTHON_BIN}" -I -S "${SKILL_DIR}/scripts/evidence_gate.py" check \
  --skill project-interview \
  --scan-dir "${SCAN_DIR}"
```

The replay passes only when the helper prints the scan directory under
`${ARTIFACT_ROOT}` and the evidence gate prints `OK: 3/3 required evidence
shapes present.`
