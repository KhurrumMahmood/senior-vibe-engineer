# Wave 1 scanner family A repair report

Scope owned:

- `.claude/skills/find-route-sprawl/`
- `.claude/skills/find-rule-surface-drift/`
- `.claude/skills/find-skill-artifact-drift/`
- `.claude/skills/find-stale-artifacts/`
- `.claude/skills/find-perimeter-gaps/`

## find-route-sprawl

Findings verified:

- TRUE: `--root-urls` was advertised in `argument-hint` and Scope.
- TRUE: `scripts/detect.py` defines `--root-urls`, but the documented
  pipeline did not forward it.
- TRUE: `scripts/detect.py` emits `scattered_route_family`, but the
  Findings list omitted it.

Call: the script surface was intended; the SKILL.md pipeline and Findings
list were wrong.

Edits made:

- Added a grounded `How success is judged` block and a `When things go
  sideways` table.
- Made the pipeline honor command exit codes and use `.venv/bin/python`.
- Added `ROOT_URLS_ARGS` so `--root-urls` can be forwarded explicitly.
- Added `scattered_route_family` to the Findings list.

Verification output:

- No shipped smoke/fixture found for this skill.
- Covered by `.venv/bin/python scripts/skill_meta.py lint`: `OK - 74
  skills, 74 declaring new contract`.

## find-rule-surface-drift

Findings verified:

- TRUE: `argument-hint` used stale `--max-root-chars 12000
  --max-doc-chars 25000`; `scripts/detect.py` defaults are 30000/50000.
- TRUE: replay fixtures exist under `fixtures/exercise-all/` and
  `fixtures/exercise-onboarding/`, but no declared verdict block pointed
  at them.
- TRUE: there was no honest failure-path table.

Call: the script defaults and fixture behavior were intended; the SKILL.md
hint and activation-standard coverage were wrong.

Edits made:

- Updated `argument-hint` to 30000/50000.
- Added `How success is judged`, `Replay fixtures`, and `When things go
  sideways`.
- Added fixture replay commands that keep output outside the fixture roots.

Verification output:

- Fixture `exercise-all`: `exercise-all OK {'dormant_doc': 1,
  'missing_doc': 1, 'oversized_doc': 1, 'oversized_root': 1,
  'unreferenced_doc': 1}`.
- Fixture `exercise-onboarding`: `exercise-onboarding OK
  {'dormant_in_onboarding': 1, 'missing_link': 1}`.
- `.venv/bin/python scripts/skill_meta.py lint`: `OK - 74 skills, 74
  declaring new contract`.

## find-skill-artifact-drift

Findings verified:

- TRUE: the skill had a fixture smoke contract in `scripts/smoke.py`, but
  no declared verdict block.
- TRUE: no honest failure-path table was present.
- TRUE: frontmatter declares `evidence_required: [report, findings]`,
  but the body did not say the run is incomplete when those artifacts are
  absent.

Call: the smoke script and evidence-required frontmatter were intended;
the SKILL.md verdict/failure contract was incomplete.

Edits made:

- Added `How success is judged` tied to `detections.jsonl`, `report.md`,
  `findings.json`, no silent drops, and `scripts/smoke.py`.
- Stated that missing `report.md` or `findings.json` fails the
  `evidence_required` contract.
- Added `When things go sideways`.
- Made the pipeline honor command exit codes and create the scan dir
  before writing artifacts.

Verification output:

- `.venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/smoke.py`:
  `OK - 6 bad fixture findings across 6 bands, good clean, gate honored`.
- `.venv/bin/python scripts/skill_meta.py lint`: `OK - 74 skills, 74
  declaring new contract`.

## find-stale-artifacts

Findings verified:

- TRUE: Scope went directly to Pipeline without `How success is judged`.
- PARTLY: honest failure paths were absent. The triage examples mentioning
  unreadable manifests or zero-evidence candidates do not match this
  script, so the repair uses this skill's own targets: absent
  `ai-docs/plans/`, absent `reports/`, zero findings, and non-zero exits.
- TRUE: no replay case was documented.

Call: script flags and defaults already matched the SKILL.md. The missing
activation-standard text was the wrong side.

Edits made:

- Added `How success is judged`.
- Added a disposable-project replay case covering `abandoned_plan`,
  `stale_plan`, `aged_scan_dir`, and `orphan_toplevel_report`.
- Added `When things go sideways`.
- Made the pipeline honor command exit codes.

Verification output:

- No shipped smoke/fixture found for this skill.
- `.venv/bin/python scripts/skill_meta.py lint`: `OK - 74 skills, 74
  declaring new contract`.

## find-perimeter-gaps

Findings verified:

- TRUE: the skill had no `How success is judged` block.
- TRUE: the skill had no honest failure-path table or replay case.
- TRUE: `scripts/scan.py --help` said `language: any` covers everything,
  while `_detector_coverage` deliberately treats it as covering nothing.

Call: `language: any` covering nothing is intended. This is pinned by
`tests/test_perimeter_gaps.py`, so the script help text was wrong.

Edits made:

- Corrected the `scripts/scan.py` docstring exposed in argparse help.
- Added `How success is judged`, a copy-runnable scan-dir pipeline,
  a replay case, and `When things go sideways`.
- The pipeline now writes stdout to `report.md` and JSON to
  `perimeter.json` under `reports/find-perimeter-gaps/<scan-id>/`.

Argparse help captured:

- Before: `language:` fell back to `(where ``any`` covers everything)`.
- After: `language:` falls back to the exact value and says
  ``language: any`` covers nothing here.

Verification output:

- `.venv/bin/python -m unittest tests.test_perimeter_gaps`: `Ran 3 tests
  ... OK`; output included the CSS gap before `--accept` and no gap after
  acceptance.
- `.venv/bin/ruff check .claude/skills/find-perimeter-gaps/scripts/scan.py`:
  `All checks passed!`.
- `.venv/bin/python scripts/skill_meta.py lint`: `OK - 74 skills, 74
  declaring new contract`.

## Shared verification

- `.venv/bin/python scripts/skill_meta.py lint`: `OK - 74 skills, 74
  declaring new contract`.
- `.venv/bin/ruff check .claude/skills/find-perimeter-gaps/scripts/scan.py`:
  `All checks passed!`.
- `git diff --check` on the five owned skill dirs: no output.

No commit made.
