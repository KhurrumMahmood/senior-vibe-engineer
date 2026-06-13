# W2-2 batch-4 group a repair report

Owned skills:

- `.claude/skills/find-standard-gaps/`
- `.claude/skills/find-transaction-overreach/`
- `.claude/skills/find-workflow-duplication/`

Reference material read first:

- `.claude/skills/repair-skill/knowledge/skill-standard.md`
- `.claude/tasks/skill-repairs/standards-triage/batch-4.md`
- `.claude/tasks/skill-repairs/standards-triage/adversarial-1-and-batch4-rederive.md`
- `.claude/tasks/skill-repairs/standards-triage/adversarial-4-5.md`
- Exemplar shapes: `fix-workflow`, `converge`, `audit-decisions`

Source note: `batch-4.md` is a recovered transcript whose detailed
defect table was not written. The actionable defect specs for these
three skills are the re-derived batch-4 findings in
`adversarial-1-and-batch4-rederive.md` and `adversarial-4-5.md`.

Scope note: the repo has unrelated dirty files outside this lane. I did
not edit them.

## find-standard-gaps

### Findings verified

- TRUE — activation-gating contract was missing from `SKILL.md`.
  Batch-4 re-derivation said the skill had no doctrine for
  `--project-state`, `project_state.py`, `gated_out`, or activation
  gating while `scan_coverage.py` emits `gated_out`. Ground truth
  matched in the pre-repair diff: the skill text had no doctrine for
  those terms while argparse exposed `--project-state` and the script
  emits `gated_out`.
- PARTLY — the old success block and sideways table existed, but were
  not strong enough for the activation standard. They did not require
  pasted command output, did not say only `status: scanned` can be a
  clean pass, and did not cover malformed/missing project-state failure
  modes.
- FALSE — default `standards/standards.json` absence was not a defect.
  The skill already honestly declared that the repo ships
  `standards.example.json` for copying/adaptation.

Knowledge check:

- `knowledge/detector-model.md` exists and is non-empty.
- The orchestrator is the mandated reader; `SKILL.md` points directly to
  that file.

### Edits made

- Added artifact-truth gates to judge runs by `coverage.md`,
  `coverage.json`, and pasted `scan_coverage.py` output.
- Documented ADR-0020 activation, `.engineering/project-state.json`
  resolution, legacy fallback, assumed-MAX behavior, and explicit
  `--project-state`.
- Added decision handling for `gated_out`, `no_files_matched`,
  `language_unsupported`, `skipped`, and `error`.
- Expanded the sideways table for real script failure modes.
- Added a replay case for a tiny `ast` standard.
- Updated `knowledge/detector-model.md` with activation-gating doctrine.
- Fixed stale script docstrings in `scan_coverage.py` and
  `project_state.py` so `--help` matches the resolver.

## find-transaction-overreach

### Findings verified

- TRUE — the documented default cheap subprocess dispatch was
  unexecutable in this checkout. The old `SKILL.md` defaulted to
  `.claude/skills/_common/dispatch_scout_cheap.sh`, whose receiver is
  `tools.code_agent`; that module is absent.

  ```text
  $ .venv/bin/python - <<'PY'
  import importlib.util
  print(importlib.util.find_spec('tools.code_agent'))
  PY
  Traceback (most recent call last):
    File "<stdin>", line 2, in <module>
    File "<frozen importlib.util>", line 95, in find_spec
  ModuleNotFoundError: No module named 'tools'
  ```

- TRUE — declared-verdict dispatch was under-specified. The orchestrator
  said to dispatch scouts, but did not state that scout output is judged
  only by the JSON file at `output_path`.
- TRUE — the required knowledge-file contract was loose. The skill and
  scout brief implied a host overlay under `knowledge/`, but the owned
  tree ships one concrete file: `knowledge/verification.md`.

Knowledge/agent check:

- `knowledge/verification.md` exists and is non-empty.
- `agents/verify.md` exists and is non-empty.
- The scout, not the orchestrator, is the mandated reader of
  `knowledge/verification.md`; the brief now makes optional host overlays
  explicitly optional.

### Edits made

- Removed `Edit` from `allowed-tools` to match the read-only audit role.
- Switched Stage 3 shipped default to the Agent tool and removed the
  unexecutable cheap-helper command block from the default path.
- Added the scout judgment contract to both `SKILL.md` and
  `agents/verify.md`.
- Replaced the required `knowledge/` overlay language with one required
  file, `knowledge/verification.md`, plus optional host files if present.
- Added pasted-output gates for Stage 1/2/4 command lines.
- Added real failure paths for missing targets, dispatch failure,
  invalid scout JSON, and report issues.
- Added a deterministic replay case for detect/collapse/report using a
  hand-written scout JSON.

## find-workflow-duplication

### Findings verified

- PARTLY — batch-4 NEEDS-REPAIR was supportable on standards grounds,
  not on a script-contract break. The pre-repair `SKILL.md` had no
  `How success is judged` block and no `When things go sideways` table.
- FALSE — any implied argparse mismatch was not found. `detect.py`
  exposes `--project-root`, `--min-owners`, `--min-active-owners`, and
  `--output`; `report.py` exposes the documented report flags plus
  optional `--project-root` and `--skip-effectiveness-log`.
- TRUE — artifact-truth and decision-point mandates were too weak. The
  old skill did not require pasted command output, did not force final
  claims through `findings.json`/`report.md`, and did not explicitly
  state the active-owner fork.
- TRUE — prose overpromised output families the current detector does
  not emit. Ground truth: `label_hits()` detects descriptor labels, tab
  IDs, and route literals; `detect.py` maps those to
  `duplicated_workflow_label`, `duplicated_workflow_tab_id`, and
  `duplicated_route_literal`, with a fallback
  `duplicated_workflow_knowledge`.

Knowledge check:

- This skill has no `knowledge/` or `agents/` files to validate.

### Edits made

- Added near-top `How success is judged` gates.
- Made the documented commands pass `--project-root` explicitly.
- Declared the skill default `--min-active-owners 2` and explained why
  the script's compatibility default of 0 is too permissive.
- Added artifact-truth requirements for `detect.py`/`report.py` output
  and final JSON/report artifacts.
- Added the active-owner decision fork to prevent docs/tests/legacy
  repeats from becoming findings without active executable drift.
- Narrowed the description, best-for text, findings list, and owner
  language to the detector's real surface: host-declared labels, tab
  IDs, route literals, and fallback workflow knowledge.
- Added a sideways table for missing descriptors, empty scan surfaces,
  zero findings, report write failures, and effectiveness logging.
- Added a replay case with a temporary host-authored workflow descriptor.

## Verification output

### Skill metadata lint

```text
$ .venv/bin/python scripts/skill_meta.py lint
OK — 74 skills, 74 declaring new contract
```

### CLI contract smoke checks

```text
$ .venv/bin/python .claude/skills/find-standard-gaps/scripts/scan_coverage.py --help | sed -n '1,90p'
usage: scan_coverage.py [-h] --ideas IDEAS --project-root PROJECT_ROOT
                        --output-dir OUTPUT_DIR
                        [--project-state PROJECT_STATE]
...
  --project-state PROJECT_STATE
                        path to the project-state file (default: <project-
                        root>/.engineering/project-state.json, with a legacy
                        <project-root>/.project-state.json fallback). Declares
                        (maturity, stakes); gates each standard's activation
                        (ADR 0020) before its detector runs.

$ .venv/bin/python .claude/skills/find-standard-gaps/scripts/census.py --help | sed -n '1,40p'
usage: census.py [-h] --concern {json_response_envelope} [--json OUT]
                 [--project-root PROJECT_ROOT]
                 paths [paths ...]

$ .venv/bin/python .claude/skills/find-transaction-overreach/scripts/detect.py --help | sed -n '1,45p'
usage: detect.py [-h] --target TARGET --project-root PROJECT_ROOT --output
                 OUTPUT [--skip-file-glob SKIP_FILE_GLOB]

$ .venv/bin/python .claude/skills/find-transaction-overreach/scripts/collapse.py --help | sed -n '1,35p'
usage: collapse.py [-h] --hits HITS --output OUTPUT

$ .venv/bin/python .claude/skills/find-transaction-overreach/scripts/report.py --help | sed -n '1,45p'
usage: report.py [-h] --scout-dir SCOUT_DIR --candidates CANDIDATES
                 --output-md OUTPUT_MD --output-json OUTPUT_JSON
                 [--scan-id SCAN_ID] [--target TARGET]

$ .venv/bin/python .claude/skills/find-workflow-duplication/scripts/detect.py --help | sed -n '1,45p'
usage: detect.py [-h] [--project-root PROJECT_ROOT] [--min-owners MIN_OWNERS]
                 [--min-active-owners MIN_ACTIVE_OWNERS] --output OUTPUT

$ .venv/bin/python .claude/skills/find-workflow-duplication/scripts/report.py --help | sed -n '1,45p'
usage: report.py [-h] --detections DETECTIONS --output-md OUTPUT_MD
                 --output-json OUTPUT_JSON --scan-id SCAN_ID --target TARGET
                 [--project-root PROJECT_ROOT] [--skip-effectiveness-log]
```

### Tiny fixture smoke — find-standard-gaps

```text
$ .venv/bin/python .claude/skills/find-standard-gaps/scripts/scan_coverage.py --ideas "$tmp/standards.json" --project-root "$tmp" --output-dir "$tmp/out"
WARNING: no project state found at /private/tmp/es-fsg.Uhhubq/.engineering/project-state.json — assuming MAX (production / public-adversarial) so nothing is silently skipped. Run /orient to declare (maturity, stakes).
state production/public-adversarial: scanned 1/1 standard(s): 1 coverage gap(s)
  idea-timeout [ast]: 1 gap(s) of 1 situation site(s)
  -> /tmp/es-fsg.Uhhubq/out/coverage.md
coverage-json: status=scanned gaps=1 state=production/public-adversarial
```

### Tiny fixture smoke — find-transaction-overreach

```text
$ .venv/bin/python .claude/skills/find-transaction-overreach/scripts/detect.py --target "$tmp/app" --project-root "$tmp" --output "$tmp/out/hits.jsonl"
[detect_transaction_overreach] wrote /tmp/es-txn.5B6xcr/out/hits.jsonl (1 hits across 1 files) by_category={'http': 1}

$ .venv/bin/python .claude/skills/find-transaction-overreach/scripts/collapse.py --hits "$tmp/out/hits.jsonl" --output "$tmp/out/candidates.jsonl"
[collapse_transaction_overreach] hits=1 candidates=1 by_confidence={'high': 1}
[collapse_transaction_overreach] wrote /tmp/es-txn.5B6xcr/out/candidates.jsonl

wrote scout fixture transaction-overreach-0001.json

$ .venv/bin/python .claude/skills/find-transaction-overreach/scripts/report.py --scout-dir "$tmp/out/scout" --candidates "$tmp/out/candidates.jsonl" --output-md "$tmp/out/report.md" --output-json "$tmp/out/findings.json" --scan-id scan-fixture --target app
[report_transaction_overreach] scouts=1 raw_candidates=1
[report_transaction_overreach] wrote /tmp/es-txn.5B6xcr/out/report.md
[report_transaction_overreach] wrote /tmp/es-txn.5B6xcr/out/findings.json
transaction-json: raw=1 scouts=1 buckets={'narrow_transaction': 1}
```

### Tiny fixture smoke — find-workflow-duplication

```text
$ .venv/bin/python .claude/skills/find-workflow-duplication/scripts/detect.py --project-root "$tmp" --min-active-owners 2 --output "$tmp/out/detections.jsonl"
wrote /tmp/es-wfd.eZlZgZ/out/detections.jsonl: 1 findings

$ .venv/bin/python .claude/skills/find-workflow-duplication/scripts/report.py --detections "$tmp/out/detections.jsonl" --output-md "$tmp/out/report.md" --output-json "$tmp/out/findings.json" --scan-id scan-fixture --target "product workflow" --project-root "$tmp" --skip-effectiveness-log
wrote /tmp/es-wfd.eZlZgZ/out/report.md
wrote /tmp/es-wfd.eZlZgZ/out/findings.json
workflow-json: findings=1 buckets={'duplicated_workflow_label': 1}
```

### Matching pytest selector

```text
$ .venv/bin/python -m pytest -k 'standard_gaps or transaction or workflow_dup' -q
.................                                                        [100%]
17 passed, 352 deselected in 0.12s
```

### Forbidden-string check

```text
Ran the forbidden-token and username-absolute-path grep across the owned
skill paths and this report.
<no output>
```
