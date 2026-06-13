# Wave 2 extract repair report

Scope: W2-1 extract family. Owned skill directories only:
`extract-cotton-primitive`, `extract-existing-ideas`,
`extract-state-type`, `extract-workflow-registry`, and `extract-enum`.
No git commit made.

## extract-cotton-primitive

### Findings verified

- TRUE - F1/F4: `SKILL.md` documented "zero callsites exits 1" as a
  load-bearing Stage 1 abort.
- TRUE - F2/F3: `scripts/profile.py` gathered callsites, wrote a
  profile with `callsite_count: 0`, and returned 0.
- PARTLY TRUE - activation-standard gap: the skill already had success
  and failure sections, but artifact-truth, scout-verdict, and replay
  gates were not explicit.

### Edits made

- `scripts/profile.py` now writes `profile.json`, prints the normal
  summary, then exits 1 with a clear stderr error when zero
  representative callsites load.
- `SKILL.md` now states the profile-write-then-abort order, requires
  pasted profile/census output, tells the scout how `primitive.md` is
  judged, and adds a replay smoke.

## extract-existing-ideas

### Findings verified

- TRUE - F1/F4: `SKILL.md` wrote candidates to `/tmp`, bypassing the
  existing helper's durable `--out` flag.
- TRUE - F2/F3: Stage 2 created an approved survivor set, but Stage 3
  still passed the original candidate file to `brainstorm.py`.
- TRUE - F5: the success gate required a candidates JSON plus report,
  but no pipeline step wrote the report.
- PARTLY TRUE - activation-standard gap: failure paths existed, but
  the approved-artifact gate and replay case were missing.

### Edits made

- `SKILL.md` now creates `reports/extract-existing-ideas/scan-<TS>/`,
  writes `extract-candidates.json` via `extract.py --out`, redirects
  the helper report to `report.md`, writes `approved-candidates.json`
  before the writer stage, and captures `brainstorm.py` output in
  `write-report.md`.
- Added `scripts/filter_candidates.py` to turn approved slugs into the
  exact survivor JSON that `brainstorm.py` consumes.
- Updated success, sideways, and replay gates so the final counts come
  from artifacts, not conversational claims.

## extract-state-type

### Findings verified

- TRUE - F1/F2: Form A advertised an `implicit-state:` finding path
  resolved from `reports/implicit-state/latest/candidates.jsonl`.
- TRUE - F3/F4/F5: `scripts/collect_target.py` only implements
  `--file`, `--symbol`, `--project-root`, and `--output`; there is no
  `--from-finding` resolver.
- PARTLY TRUE - activation-standard/load-bearing gap: the scout brief
  referenced generic `knowledge/` conventions that did not exist as a
  separate file.

### Edits made

- Chose the smaller honest fix: Form A is now a manual resolution
  recipe. The orchestrator strips `implicit-state:`, reads the
  JSONL candidate, extracts `file` and `symbol`, then calls the real
  `collect_target.py --file ... --symbol ...` Form-B helper. I did
  not add a second resolver because the skill already notes this
  sub-shape is not reliably emitted by the detector.
- Added `knowledge/state-conventions.md` and wired
  `agents/state-profiler.md` to read it.
- Updated `SKILL.md` with artifact-truth, scout-verdict, venv command,
  replay, and knowledge-file gates.

## extract-workflow-registry

### Findings verified

- TRUE - F1: `SKILL.md` documented the default
  `.claude/docs/workflows/sites.md`; that file is absent.
- TRUE - F2: `scripts/propose.py` accepted `--workflow-map` but built
  entries from `workflow_steps(project_root)`, not the map argument.
- TRUE - F3: `SKILL.md` promised `api_endpoints` and
  `api_endpoint_templates`, while `REGISTRY_FIELDS` omitted both.
- TRUE - activation-standard gap: this skill lacked a near-top success
  block, failure table, and replay case.

### Edits made

- `scripts/propose.py` now defaults to
  `.claude/docs/workflows/<workflow>.md`, aborts if the map is missing
  or has zero steps, parses the workflow map tables, and validates
  `--finding` paths.
- Added `api_endpoints` and `api_endpoint_templates` to
  `REGISTRY_FIELDS`, proposal field meanings, effectiveness buckets,
  and rendered proposal output.
- `SKILL.md` now declares success gates, consumes a real workflow map
  artifact, documents missing-map behavior, and includes sideways and
  replay sections.

## extract-enum

### Findings verified

- TRUE - batch-1 minor: prefix handling was under-specified. The skill
  did not explicitly say the orchestrator strips optional
  `implicit-state:` before passing `--from-finding`.
- TRUE - batch-1 minor: the recommendation gate was under-specified.
  The skill described reading `recommendation_hint`, but did not place
  an explicit pre-`collect.py` check in the Form-A path.
- TRUE - adversarial escalation: `knowledge/` was empty while
  `SKILL.md` made it load-bearing for third-party bridge and risk
  context; `agents/enum-profiler.md` did not read it.

### Edits made

- Added `knowledge/risk-context.md` with enum risk buckets, bridge
  handling, case-variant handling, and the plain string-valued enum
  fallback for non-model carriers.
- Updated `agents/enum-profiler.md` to read `risk-context.md`.
- `SKILL.md` now includes the Form-A prefix strip and explicit
  `recommendation_hint`/`bucket == extract_enum_candidate` check
  before `collect.py`.
- `scripts/collect.py` now also accepts prefixed IDs and rejects
  non-`extract_enum_candidate` findings, so the guard is enforceable
  if the helper is invoked directly.
- Added artifact-truth, scout-verdict, venv command, layout, and
  replay gates.

## Verification output

### Compile changed scripts

```text
py_compile OK 6 files
```

### extract-cotton-primitive zero-callsite smoke

```text
COMMAND .venv/bin/python .claude/skills/extract-cotton-primitive/scripts/profile.py --category modal-shell --candidates /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/cotton-smoke-bie84bem/candidates.json --project-root /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/cotton-smoke-bie84bem/root --output /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/cotton-smoke-bie84bem/profile.json
RC 1
STDOUT Wrote /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/cotton-smoke-bie84bem/profile.json
STDERR Profiled modal-shell — 0 representative callsites loaded (of 1 total)
ERROR: zero representative callsites loaded; profile artifact was written for inspection, aborting before scout
PROFILE_EXISTS True
PROFILE_CALLSITE_COUNT 0
```

### extract-existing-ideas durable out plus approved filter smoke

```text
EXTRACT_COMMAND .venv/bin/python .claude/skills/extract-existing-ideas/scripts/extract.py /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/ideas-smoke-occmfoj3/source --source both --project-root . --out /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/ideas-smoke-occmfoj3/extract-candidates.json
EXTRACT_RC 0
EXTRACT_STDOUT_FIRST # Extract candidates (root: /private/var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/ideas-smoke-occmfoj3/source)
EXTRACT_STDOUT_LAST   .venv/bin/python .claude/skills/brainstorm-ideas/scripts/brainstorm.py /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/ideas-smoke-occmfoj3/extract-candidates.json
FILTER_COMMAND .venv/bin/python .claude/skills/extract-existing-ideas/scripts/filter_candidates.py --candidates /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/ideas-smoke-occmfoj3/extract-candidates.json --keep-slugs add-workflow-registry-endpoint-payload --out /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/ideas-smoke-occmfoj3/approved-candidates.json
FILTER_RC 0
FILTER_STDERR wrote 1 approved candidate(s) to /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/ideas-smoke-occmfoj3/approved-candidates.json
RAW_COUNT 2
APPROVED_COUNT 1
APPROVED_SLUG add-workflow-registry-endpoint-payload
```

### extract-state-type collect_target smoke

```text
COMMAND .venv/bin/python .claude/skills/extract-state-type/scripts/collect_target.py --file /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/state-smoke-51o61yqs/root/pipeline.py --symbol build_state --project-root /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/state-smoke-51o61yqs/root --output /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/state-smoke-51o61yqs/targets.json
RC 0
STDOUT wrote /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/state-smoke-51o61yqs/targets.json: build_state (kind=function, dict_candidates=1, callers=0)
STDERR
DICT_CANDIDATES 1
CALLERS 0
```

### extract-workflow-registry map and endpoint smoke

```text
COMMAND .venv/bin/python .claude/skills/extract-workflow-registry/scripts/propose.py sites --workflow-map /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/workflow-smoke-zpk1j3a2/sites.md --output /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/workflow-smoke-zpk1j3a2/proposal.md --project-root . --skip-effectiveness-log
RC 0
STDOUT wrote /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/workflow-smoke-zpk1j3a2/proposal.md
STDERR
HAS_API_ENDPOINTS True
HAS_API_ENDPOINT_TEMPLATES True
HAS_BOOT_KEY True
```

### extract-enum Form-A guard smoke

```text
COMMAND .venv/bin/python .claude/skills/extract-enum/scripts/collect.py --from-finding implicit-state:implicit-state-0001 --findings /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/enum-guard-smoke-pn956gs4/findings.json --project-root /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/enum-guard-smoke-pn956gs4 --output /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/enum-guard-smoke-pn956gs4/targets.json
RC 2
STDOUT
STDERR error: finding implicit-state-0001 is introduce_fk_candidate; run /introduce-fk instead of /extract-enum
OUTPUT_EXISTS False
```

### extract-enum explicit target smoke

```text
COMMAND .venv/bin/python .claude/skills/extract-enum/scripts/collect.py --target app/models.py::status::Job --project-root /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/enum-target-smoke-scxqa9pi/root --output /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/enum-target-smoke-scxqa9pi/targets.json
RC 0
STDOUT
STDERR [collect_extract_enum] wrote /var/folders/nw/gxp07twj3cx2yfyvbbc1n_8r0000gn/T/enum-target-smoke-scxqa9pi/targets.json: Job.status — 2 literals (0 case-variants) across 1 files (1 comparisons, 1 assignments)
LITERALS ['done', 'pending']
COMPARISONS 1
ASSIGNMENTS 1
```

### Skill metadata lint

```text
OK — 74 skills, 74 declaring new contract
```

### Extract tests

```text
........                                                                 [100%]
8 passed, 361 deselected in 0.12s
```
