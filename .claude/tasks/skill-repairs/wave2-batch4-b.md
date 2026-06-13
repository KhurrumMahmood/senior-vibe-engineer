# W2-3 batch-4 group b repair report

Scope owned: `find-workflow-state-gaps`, `introduce-fk`, and
`map-subsystem` skill directories only, plus this report.

## find-workflow-state-gaps

### Findings verified

- **PARTLY TRUE — standards-only triage finding.**
  `adversarial-4-5.md` says the batch-4 detailed defect spec was lost,
  and re-derived support was standards-shaped: missing activation
  elements 1, 2, and 7, plus shipped-kit `/sites` scope. That was TRUE
  for the old 51-line SKILL: no success-verdict block, no artifact-truth
  gate, no sideways table, and `/sites` was in frontmatter/body.
- **PARTLY FALSE — "no execution defect found."**
  While verifying from ground truth, I found two additional executable
  defects not named by triage: `scripts/detect.py` called
  `/find-workflow-duplication` with an obsolete four-argument API, and
  `scripts/smoke.py` referenced a missing `fixtures/` tree.

### Edits made

- Rebuilt `SKILL.md` with a near-top "How success is judged" block,
  artifact-truth requirements, decision points, honest failure table,
  repository layout, and replay case.
- Removed host-specific `/sites` language from the SKILL and script
  target labels; default scope is now host-declared workflow targets, with
  explicit-path fallback when no host descriptor exists.
- Fixed the workflow-duplication context call to the current
  `detect(project_root, min_owners=..., min_active_owners=...)` API.
- Made `scripts/smoke.py` self-contained by generating temporary good and
  bad workflow HTML surfaces instead of relying on absent fixture files.

## introduce-fk

### Findings verified

- **TRUE — empty load-bearing `knowledge/` contract.**
  The old SKILL said project-specific defaults lived in `knowledge/`, said
  the scout reads that file, and referenced `knowledge/` for proposal
  risk guidance. Ground truth: the directory has no files, and
  `agents/fk-profiler.md` did not read any knowledge file.
- **TRUE — collector argparse matched documented forms.**
  The triage note that `collect.py` itself matched the documented
  `--from-finding` / `--target` forms was verified by source and help.

### Edits made

- Removed the phantom `knowledge/` dependency and made the absence of a
  shipped overlay explicit.
- Added artifact-truth gates for `targets.json`, `profile.md`,
  `proposal.md`, collector stderr, and profile classification counts.
- Added declared-verdict dispatch language to Stage 2 and to
  `agents/fk-profiler.md`: the scout output is judged by the written
  profile file, status, counts, call-site table, and source citations.
- Switched documented invocations and script docstring examples to
  `.venv/bin/python`.
- Removed the not-yet-shipped `/fix-workflow introduce-fk:<target-slug>`
  handoff and replaced it with an honest proposal-path handoff.
- Expanded the sideways table for real collector/scout/logger failure
  modes.

## map-subsystem

### Findings verified

- **TRUE — orphan renderer invocation.**
  `scripts/render_doc.py` requires `--name --target --scratch --output`,
  and the layout said it implements Stages 6-7, but no pipeline stage
  invoked it.
- **TRUE — scratch-dir contradiction.**
  Stage 0 promised `reports/map/<name>/` scratch, while the old command
  used `mktemp -d`.
- **TRUE — additional load-bearing doc drift.**
  The SKILL referenced generic `knowledge/` naming rules and a reserved
  `agents/` directory that do not exist. `knowledge/output-format.md`
  existed and was non-empty, but it also referenced stale
  `reports/map/<name>/inbound.txt` paths.

### Edits made

- Stage 0 now creates `reports/map/<name>/scan-<TS>/` and updates a
  `latest` symlink under `reports/map/<name>/`.
- Stage 6 now invokes `render_doc.py` with its real argparse contract and
  names the renderer `wrote ...` line as a truth artifact.
- Stage 7 now reflects that `render_doc.py` appends the effectiveness row
  when `--effectiveness-log` is non-empty, and requires verification
  before claiming the row.
- Replaced nonexistent naming-rule knowledge with inline naming guidance
  and removed the nonexistent `agents/` layout entry.
- Aligned `knowledge/output-format.md` and `render_doc.py` on optional
  `workflows.json` input and `Workflow participation` output.
- Updated stale inbound scratch references to
  `reports/map/<name>/latest/deps.json`.
- Made `_read_json` tolerate malformed JSON by returning the provided
  default, matching the documented failure posture for optional scratch.

## Verification output

### Skill metadata lint

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/skill_meta.py lint
OK — 74 skills, 74 declaring new contract
```

### Changed script help / smoke

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .claude/skills/find-workflow-state-gaps/scripts/run.py --help
usage: run.py [-h] [--project-root PROJECT_ROOT] [--skip-effectiveness-log]
              [paths ...]

Run find-workflow-state-gaps and write the standard report directory.

positional arguments:
  paths

options:
  -h, --help            show this help message and exit
  --project-root PROJECT_ROOT
  --skip-effectiveness-log
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .claude/skills/find-workflow-state-gaps/scripts/detect.py --help
usage: detect.py [-h] [--project-root PROJECT_ROOT]
                 [--no-workflow-duplication] --output OUTPUT
                 [paths ...]

Detect workflow state coverage gaps.

positional arguments:
  paths

options:
  -h, --help            show this help message and exit
  --project-root PROJECT_ROOT
  --no-workflow-duplication
  --output OUTPUT
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .claude/skills/find-workflow-state-gaps/scripts/report.py --help
usage: report.py [-h] --output OUTPUT [--target TARGET] detections

Render a find-workflow-state-gaps JSONL scan.

positional arguments:
  detections

options:
  -h, --help       show this help message and exit
  --output OUTPUT
  --target TARGET
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .claude/skills/find-workflow-state-gaps/scripts/smoke.py
find-workflow-state-gaps smoke OK
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .claude/skills/find-workflow-state-gaps/scripts/run.py --project-root "$TMP_STATE" --skip-effectiveness-log .
wrote /private/var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/tmp.DbXaiFYVlI/reports/find-workflow-state-gaps/scan-20260613-014518
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .claude/skills/introduce-fk/scripts/collect.py --help
usage: collect.py [-h] (--from-finding CANDIDATE_ID | --target SPEC)
                  [--findings FINDINGS] --project-root PROJECT_ROOT --output
                  OUTPUT [--owner-spec OWNER_SPEC]

options:
  -h, --help            show this help message and exit
  --from-finding CANDIDATE_ID
                        Candidate ID in --findings to resolve
  --target SPEC         'OWNER_FILE::OwnerModel -> TARGET_FILE::TargetModel
                        [via fk_name]'
  --findings FINDINGS   findings.json from /find-implicit-state (Form A)
  --project-root PROJECT_ROOT
  --output OUTPUT
  --owner-spec OWNER_SPEC
                        For Form A only: 'OWNER_FILE::OwnerModel' — the
                        finding tells us the target model but not the owner;
                        supply it explicitly
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .claude/skills/introduce-fk/scripts/collect.py --target "core/models/owner.py::Owner -> core/models/target.py::Target via active_target" --project-root "$TMP_FK" --output "$TMP_FK/targets.json"
[collect_introduce_fk] wrote /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/tmp.OR2pRosjXs/targets.json: Owner -> Target (1 call sites, proposed_fk_name=active_target, owner_has_existing_fk=False)
owner__active_target 1 active_target False
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .claude/skills/map-subsystem/scripts/render_doc.py --help
usage: render_doc.py [-h] --name NAME --target TARGET --scratch SCRATCH
                     --output OUTPUT [--prior-doc PRIOR_DOC] [--header HEADER]
                     [--effectiveness-log EFFECTIVENESS_LOG]

Render a subsystem inventory doc from the Stage 1–5 scratch files.

options:
  -h, --help            show this help message and exit
  --name NAME           Subsystem name (kebab-case)
  --target TARGET       Path to the subsystem
  --scratch SCRATCH     Scratch dir with Stage 1–5 outputs
  --output OUTPUT       Output markdown path
  --prior-doc PRIOR_DOC
                        Prior version for --refresh diff
  --header HEADER       One-paragraph header text
  --effectiveness-log EFFECTIVENESS_LOG
                        Effectiveness log path (empty string to skip)
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .claude/skills/map-subsystem/scripts/render_doc.py --name input-utils --target core/input_utils.py --scratch "$SCRATCH" --output "$TMPDIR_RENDER/input-utils.md" --header "Single-file helpers for parsing request data." --effectiveness-log "$TMPDIR_RENDER/effectiveness.jsonl"
wrote /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/tmp.kPbUt8NJWl/input-utils.md (1163 bytes)
effectiveness-lines:        1
```

### Python lint

```text
$ .venv/bin/ruff check .claude/skills/find-workflow-state-gaps/scripts .claude/skills/introduce-fk/scripts/collect.py .claude/skills/map-subsystem/scripts/render_doc.py
All checks passed!
```

### Pytest

The requested selector found no matching tests:

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -k 'workflow_state or introduce_fk or map_subsystem' -q

369 deselected in 0.09s
```

Related targeted tests were run because grep found nearby taxonomy/router
coverage for `introduce-fk` and `map-subsystem`:

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_skill_taxonomy.py tests/test_which_shape.py -q
................................                                         [100%]
32 passed in 1.12s
```

### Diff hygiene and forbidden-string sweep

```text
$ git diff --check -- .claude/skills/find-workflow-state-gaps .claude/skills/introduce-fk .claude/skills/map-subsystem
<no output>
```

The sweep command below is displayed with placeholders so this report does
not write the forbidden literal token or absolute user path. The real sweep
used the actual forbidden token and the actual user-path string; it produced
no output.

```text
$ rg -n "<forbidden-token>|<forbidden-absolute-user-path>|/sites|sites surface" .claude/skills/find-workflow-state-gaps .claude/skills/introduce-fk .claude/skills/map-subsystem || true
<no output>
```
