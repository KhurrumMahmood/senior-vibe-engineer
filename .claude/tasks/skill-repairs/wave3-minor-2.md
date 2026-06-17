# Wave 3 Minor 2 — Detection Scanners

Scope owned: `find-duplication`, `find-frontend-duplication`,
`find-implicit-state`, `find-layer-violation`, `find-omnibus`,
`find-query-mutation`. Edits stayed inside those six `SKILL.md` files.
No scripts changed. No git commit was made.

Read first: `repair-skill/knowledge/skill-standard.md`, the relevant
triage rows in `standards-triage/batch-2.md` and `batch-3.md`, and the
scanner exemplars `find-perimeter-gaps`, `find-stale-artifacts`, and
`find-workflow-duplication`.

## find-duplication

Findings verified:

- TRUE: frontmatter allowed `Edit` while the skill declares editing files a
  non-goal. Removed `Edit`.
- TRUE: Stage 5 invoked `python3 scripts/log_effectiveness.py`; changed it
  to `.venv/bin/python scripts/log_effectiveness.py`.
- TRUE: replay evidence was absent. Added a replay case for the
  detect/collapse/rank/scout/report path with expected finding counts.
- PARTLY: declared verdict and sideways handling already existed, but the
  artifact-truth gate and declared scout merge verdict were weaker than the
  standard. Added pasted-output and scout JSON acceptance gates.

Edits made: removed stale write/edit capability, added closeout artifact
requirements, added the Stage 4 scout acceptance contract, fixed the venv
effectiveness-log command, added a replay case, and added an explicit
non-zero-script failure path.

Reference check: `agents/investigate.md`,
`knowledge/false-positives.md`, and `knowledge/learnings.md` exist,
are non-empty, and are read by the scout, not the orchestrator.

## find-frontend-duplication

Findings verified:

- TRUE: Stage 1 said all three inventories must be non-empty, but
  `cotton_inventory.py` has a valid empty-inventory outcome for
  `component_profile.kind = none`. Relaxed the postcondition to file
  existence plus valid zero-candidate handling.
- TRUE: frontmatter advertised stale `--templates` / `--js` flags not
  accepted by the scripts. Replaced with the real `--root`,
  `--min-count`, and `--min-tokens` surface, and documented scope tuning
  through the frontend duplication scope descriptor.
- TRUE: replay evidence was absent. Added a replay case for inventory,
  class-chain/helper detection, collapse, rank, scout, and report.
- PARTLY: declared verdict and sideways handling already existed, but the
  artifact-truth gate and declared scout merge verdict needed tightening.

Edits made: corrected argument hint and scope prose, added `PROJECT_ROOT`
and explicit `--root` flags to Stage 1 commands, relaxed the inventory
postcondition, changed the effectiveness log to `.venv/bin/python`, added
artifact-truth and scout acceptance gates, added replay evidence, and added
a non-zero-script failure path.

Reference check: `agents/investigate.md`,
`knowledge/extraction-thresholds.md`, and `knowledge/false-positives.md`
exist, are non-empty, and are read by the scout.

## find-implicit-state

Findings verified:

- TRUE: script flags matched the documented detect/collapse/report path,
  but replay evidence for the full path was absent.
- TRUE: the read-only scanner still allowed `Edit`; removed it.
- PARTLY: success and sideways gates existed, but artifact-truth and
  declared scout merge acceptance were weaker than the activation
  standard.

Edits made: removed `Edit`, switched documented script invocations and
effectiveness-log helpers to `.venv/bin/python`, added pasted-output
artifact gates, added explicit scout JSON acceptance rules, added a replay
case for stringly-state plus tuple-identity findings, and added a
non-zero-script failure path.

Reference check: `agents/verify.md` and `knowledge/verification.md` exist,
are non-empty, and are read by the scout.

## find-layer-violation

Findings verified:

- TRUE: script flags matched, but replay evidence for the detector/scout/
  report path was absent.
- TRUE: the read-only scanner still allowed `Edit`; removed it.
- PARTLY: success and sideways gates existed, but artifact-truth and
  declared scout merge acceptance were weaker than the activation
  standard.

Edits made: removed `Edit`, switched documented script invocations and
effectiveness-log helpers to `.venv/bin/python`, added pasted-output
artifact gates, added explicit scout JSON acceptance rules including signal
coverage and interface-depth requirements, added a replay case, and added
a non-zero-script failure path.

Reference check: `agents/verify.md` and `knowledge/verification.md` exist,
are non-empty, and are read by the scout.

## find-omnibus

Findings verified:

- TRUE: the prose said "three buckets" while naming four. Corrected to
  "four buckets".
- TRUE: replay evidence was absent. Added a replay case for detector,
  collapse, scout, and report.
- TRUE: the read-only scanner still allowed `Edit`; removed it.
- PARTLY: success and sideways gates existed, but artifact-truth and
  declared scout merge acceptance were weaker than the activation
  standard.

Edits made: fixed the bucket-count typo, removed `Edit`, switched
documented script invocations and effectiveness-log helpers to
`.venv/bin/python`, added pasted-output artifact gates, added explicit
scout JSON acceptance rules, added replay evidence, and added a
non-zero-script failure path.

Reference check: `agents/verify.md` and `knowledge/verification.md` exist,
are non-empty, and are read by the scout.

## find-query-mutation

Findings verified:

- TRUE: replay evidence was absent.
- TRUE: the scout verdict merge contract was under-explicit; success
  required confirmed mutations but did not say how malformed or missing
  scout JSON is rejected before reporting.
- TRUE: the read-only scanner still allowed `Edit`; removed it.
- PARTLY: success and sideways gates existed, but artifact-truth and
  declared scout merge acceptance needed activation-standard tightening.

Edits made: removed `Edit`, switched documented script invocations and
effectiveness-log helpers to `.venv/bin/python`, added pasted-output
artifact gates, added explicit scout JSON acceptance rules with
`recommendation_hint_symbol` handling, added replay evidence, and added a
non-zero-script failure path.

Reference check: `agents/verify.md` and `knowledge/verification.md` exist,
are non-empty, and are read by the scout.

## Verification Output

Required metadata lint:

```text
$ .venv/bin/python scripts/skill_meta.py lint
OK — 76 skills, 76 declaring new contract
```

Required artifact-drift gate:

```text
$ .venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/detect.py --gate find-duplication find-frontend-duplication find-implicit-state find-layer-violation find-omnibus find-query-mutation
<no stdout/stderr; exited 0>
```

Script help smoke: no scripts changed, but the primary documented script
surfaces were checked. Usage lines observed:

```text
$ .venv/bin/python .claude/skills/find-frontend-duplication/scripts/cotton_inventory.py --help
usage: cotton_inventory.py [-h] [--root ROOT] [--out OUT] [--print]
                           [--kind KIND] [--definitions-root DEFINITIONS_ROOT]
                           [--reference-pattern REFERENCE_PATTERN]
                           [--extensions EXTENSIONS]

$ .venv/bin/python .claude/skills/find-implicit-state/scripts/detect.py --help
usage: detect.py [-h] --target TARGET --project-root PROJECT_ROOT --output
                 OUTPUT [--skip-file-glob SKIP_FILE_GLOB]

$ .venv/bin/python .claude/skills/find-layer-violation/scripts/detect.py --help
usage: detect.py [-h] --target TARGET --project-root PROJECT_ROOT --output
                 OUTPUT [--fn-budget FN_BUDGET]
                 [--method-budget METHOD_BUDGET] [--task-budget TASK_BUDGET]
                 [--skip-file-glob SKIP_FILE_GLOB]

$ .venv/bin/python .claude/skills/find-omnibus/scripts/detect.py --help
usage: detect.py [-h] --target TARGET --project-root PROJECT_ROOT --output
                 OUTPUT [--skip-file-glob SKIP_FILE_GLOB]
                 [--skip-path-glob SKIP_PATH_GLOB]
                 [--language {javascript,python}]

$ .venv/bin/python .claude/skills/find-query-mutation/scripts/detect.py --help
usage: detect.py [-h] --target TARGET --project-root PROJECT_ROOT --output
                 OUTPUT [--skip-file-glob SKIP_FILE_GLOB]

$ .venv/bin/python .claude/skills/find-duplication/scripts/collapse.py --help
usage: collapse.py [-h] --jscpd-report JSCPD_REPORT
                   [--ast-findings AST_FINDINGS] --target TARGET --output
                   OUTPUT [--ignore IGNORE] [--no-defaults] --project-root
                   PROJECT_ROOT
```

Matching pytest:

```text
$ .venv/bin/python -m pytest tests/test_layer_violation_detector.py tests/test_omnibus_language_adapters.py tests/test_perimeter_gaps.py tests/test_standard_gaps_census.py -q
.........................                                                [100%]
25 passed in 0.07s
```

Whitespace and forbidden-token/path checks:

```text
$ git diff --check -- .claude/skills/find-duplication/SKILL.md .claude/skills/find-frontend-duplication/SKILL.md .claude/skills/find-implicit-state/SKILL.md .claude/skills/find-layer-violation/SKILL.md .claude/skills/find-omnibus/SKILL.md .claude/skills/find-query-mutation/SKILL.md
<no output; exited 0>

Changed tracked files were scanned for the forbidden token and local
absolute-user paths.
<no output; no forbidden token or local absolute-user path was found>
```
