# Wave 1 Batch 1 Heavy Quartet Repair

Scope: W1-4 only. Edited:

- `.claude/skills/audit-decisions/SKILL.md`
- `.claude/skills/converge/SKILL.md`
- `.claude/skills/check-ecosystem-consistency/SKILL.md`
- `.claude/skills/adapt-project/SKILL.md`

No edits were made to `decide/` or `scripts/decisions.py`.

## Grounding

Read before editing:

- `.claude/skills/repair-skill/knowledge/skill-standard.md`
- `.claude/tasks/skill-repairs/standards-triage/batch-1.md`
- `.claude/skills/decide/SKILL.md`
- Each owned skill's `SKILL.md`

`.venv/bin/python scripts/decisions.py --help` showed the real subcommands:

- `init` — Scaffold a new ADR
- `list` — List all decisions
- `show` — Print one decision in full
- `rebuild` — Rebuild `decision-index.json`
- `audit` — Run drift checks
- `link-check` — Verify supersedes / applies_to links

There is no `status` or `renumber` subcommand.

## Per-skill Findings

### audit-decisions

Verdict: TRUE.

Fixes:

- Replaced all `/decide --status ...` references with `/decide --amend <id>` and explicit `status` field language.
- Fixed the `resolution_command` JSON example to use `/decide --amend 0007`.
- Replaced `/decide --renumber` with the real manual path: edit the duplicate ADR filename/frontmatter id, then run `scripts/decisions.py rebuild` and `scripts/decisions.py audit`.

Spot-check: `rg -n "/decide --status|/decide --renumber" .claude/skills/audit-decisions/SKILL.md` returns no hits.

### converge

Verdict: TRUE.

Fixes:

- Added a near-top `How success is judged` block with the fixed verdict schema, artifact-truth evidence rule, no-execution rule, and report/effectiveness gates.
- Converted evidence language from "find and cite" to quoted artifact/command-output truth.
- Replaced the hardcoded `status_repair` bucket with a `status_${PHASE_STATUS}` bucket read from `verdict.json`.
- Added a `When things go sideways` table covering missing evidence, invalid status, competing next steps, report write failure, and attempts to execute the next step inside `/converge`.

### check-ecosystem-consistency

Verdict: TRUE.

Fixes:

- Added `How success is judged` with script exit-code honoring, artifact expectations, complete findings relay, and explicit `--update-state` review gate.
- Added an execution contract for default, `--changed-from REF`, `--staged`, and `--update-state` script forms.
- Added a `When things go sideways` table for bad git refs, `shape_registry_schema_error`, report/state write failure, and `baseline_missing`.

### adapt-project

Verdict: TRUE.

Fixes:

- Added `How success is judged` near the top, tied to real artifacts: `adapter.yml`, `adapter.json`, `report.md`, and `evidence.json`.
- Surfaced the existing `evidence_required: [adapter, report]` gate and the `evidence.json` map to `adapter.yml` and `report.md`.
- Added a `When things go sideways` table covering `project_adapt.py discover` failure, mutually exclusive `--apply`/`--no-host-write`, invalid dogfood artifact root, missing evidence manifest, missing evidence files, malformed JSON, and missing scan dir.

## Verification

- `.venv/bin/python scripts/skill_meta.py lint` — OK: `OK — 74 skills, 74 declaring new contract`
- `.venv/bin/python scripts/decisions.py --help` — OK; subcommands listed above
- Ruff: not run; this lane touched no Python files
- Owned touched files: only the four `SKILL.md` files listed in scope
