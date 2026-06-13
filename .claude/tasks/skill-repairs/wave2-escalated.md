# Wave 2 escalated repair report

Scope owned: `explain-code`, `find-test-obligation-drift`,
`map-product-workflow`, `mature-existing-ideas`. No git commit made.

## explain-code

### Findings verified

| Finding | Verdict | Ground truth |
|---|---|---|
| Stage 3 required the orchestrator to use `knowledge/explanation-format.md`, while the repository layout said the orchestrator never reads `knowledge/` | TRUE | Pre-repair `SKILL.md` had both mandates, and `agents/annotate.md` did not read the format file. A run could not satisfy both. |
| `unexplained.txt` and `surprises.txt` were consumed by Stage 4 but not explicitly mandated as Stage 3 outputs | TRUE | Pre-repair Stage 4 counted both sidecars and had defensive defaults; Stage 3 did not require writing them as postconditions. |
| Missing activation-standard details beyond the triage item | TRUE | The skill had a success block and failure table, but artifact-truth gates, declared-verdict dispatch wording, and replay evidence were not explicit enough. |

### Edits made

- Made `knowledge/explanation-format.md` an orchestrator-read output-format reference.
- Added artifact-truth gates requiring real inventory, annotation-count, sidecar-count, and effectiveness-log output.
- Added declared-verdict wording to `agents/annotate.md`.
- Made Stage 3 write `unexplained.txt` and `surprises.txt` as mandatory sidecar outputs, empty when count is zero.
- Added failure rows for missing/empty format knowledge and sidecar write failures.
- Added a replay case using `.venv/bin/python`.
- Updated helper usage docs from bare `python3` to `.venv/bin/python`.

Knowledge reference check:

```text
$ rg -n "knowledge/" .claude/skills/explain-code/SKILL.md .claude/skills/explain-code/agents/annotate.md .claude/skills/explain-code/knowledge/explanation-format.md
.claude/skills/explain-code/SKILL.md:45:- `knowledge/explanation-format.md` — the exact shape of
.claude/skills/explain-code/SKILL.md:95:- **Output-format conventions:** `knowledge/explanation-format.md`.
.claude/skills/explain-code/SKILL.md:97:  `knowledge/`; they follow `agents/annotate.md`.
.claude/skills/explain-code/SKILL.md:221:Read `knowledge/explanation-format.md`, then read every annotation
.claude/skills/explain-code/SKILL.md:322:| `knowledge/explanation-format.md` is missing or empty | Abort before synthesis; the top-level doc shape is undefined |
.claude/skills/explain-code/SKILL.md:341:Then verify `knowledge/explanation-format.md` is non-empty and that
.claude/skills/explain-code/SKILL.md:345:test -s .claude/skills/explain-code/knowledge/explanation-format.md && \
.claude/skills/explain-code/SKILL.md:358:└── knowledge/                       # orchestrator output-format reference

$ test -s .claude/skills/explain-code/knowledge/explanation-format.md && wc -l .claude/skills/explain-code/knowledge/explanation-format.md
     278 .claude/skills/explain-code/knowledge/explanation-format.md
```

## find-test-obligation-drift

### Findings verified

| Finding | Verdict | Ground truth |
|---|---|---|
| No near-top "How success is judged" block and no artifact-truth gates | TRUE | Pre-repair file went from intro directly to `## Pipeline`; nothing required pasted report output. |
| No "When things go sideways" table | TRUE | Pre-repair file ended after detector bands and promotion guidance. |
| Host-specific `/sites` surface was baked into shipped-kit prose | TRUE | Pre-repair frontmatter/body named backend `/sites` code and `/sites` noise. |
| Script argparse mismatch with documented flags | FALSE | `run.py --help` matched positional `paths`, `--project-root`, `--staged`, `--changed-from`, and `--skip-effectiveness-log`; `detect.py --help` showed required `--output` for the lower-level helper. |
| Script behavior still had host-specific product defaults | TRUE, additional ground-truth finding | `detect.py` hardcoded product backend/UI path prefixes. I replaced those with descriptor-derived workflow scope patterns. |

### Edits made

- Added success gates, artifact-truth requirements, declared verdict dispatch, failure table, and replay case.
- Replaced product backend/UI hardcoded path detection with
  `.engineering/docs/product-workflows.md` descriptor-derived patterns.
- Made `run.py` print `workflow scope patterns: <N>` and `findings: <N>`.
- Updated fixture smoke to copy fixtures to a temporary project and inject a temporary descriptor there; no fixture files were changed.
- Clarified `run.py` exit code behavior: exit 0 means report artifacts were written, not that obligations are absent.

Knowledge reference check: no `knowledge/` references in this skill.

## map-product-workflow

### Findings verified

| Finding | Verdict | Ground truth |
|---|---|---|
| No near-top "How success is judged" block | TRUE | Pre-repair file entered `## Scope` without declared gates. |
| No artifact-truth gate and no executable check for empty maps | TRUE | Pre-repair text did not require pasted `wrote ...` lines or descriptor-scope counts. |
| No "When things go sideways" table | TRUE | Pre-repair file ended after `## Next Skills`. |
| Host descriptor dependency was dishonest | PARTLY | The pre-repair scope honestly said no descriptor means an empty map, and the script shipped no baked-in profile. The missing repair-grade part was that the output did not expose descriptor-scope counts, so an empty map could be misread as a clean topology verdict. |
| Script argparse mismatch | FALSE | `generate.py` supports positional `workflow`, `--project-root`, `--output`, `--json-output`, `--scan-id`, and `--skip-effectiveness-log`; the documented invocation remains valid. |

### Edits made

- Added success gates, artifact-truth requirements, decision points, failure table, and replay case.
- Added a `Descriptor Scope` section to generated maps.
- Added matching `descriptor_scope` counts to the JSON scratch artifact.
- Updated script subprocess logging to use `sys.executable`.
- Updated documented commands to `.venv/bin/python`.

Knowledge reference check: no `knowledge/` references in this skill.

## mature-existing-ideas

### Findings verified

| Finding | Verdict | Ground truth |
|---|---|---|
| `scripts/mature.py` was orphaned | TRUE | It was referenced only by layout/prose, while the pipeline wrote via `track-idea/scripts/track.py`. |
| Frontmatter/layout said the helper script wrote events, contradicting the pipeline | TRUE | Pre-repair Stage 2 used `track.py event`; the helper script claim described a different writer. |
| `/promote-idea-to-pattern` was referenced but not installed | TRUE | `.claude/skills/promote-idea-to-pattern/` is absent. |
| `argument-hint` omitted `--external-research` | TRUE | The documented forms accepted it, but the hint omitted it. |
| `--adversarial` prose contradicted `.claude/docs/review-lane.md` | PARTLY | The default `general-purpose` and "not true cross-model" claims matched `review-lane.md`; the missing standard piece was declared-verdict wording in the dispatch. |

### Edits made

- Deleted orphan `scripts/mature.py`.
- Made `track-idea/scripts/track.py` the only ledger writer in the skill text.
- Marked Tier 2 promotion as planned/future because no promotion skill is installed; routed current action to adoption evidence plus `.claude/docs/pattern-library.md`.
- Added `--external-research` to the argument hint.
- Added artifact-truth gates requiring pasted `track.py` output.
- Added declared-verdict wording for adversarial sub-agent dispatch.
- Added failure handling for `track.py` write failures.
- Added a no-production-write replay case using a temporary ledger.

Knowledge reference check: no `knowledge/` references in this skill.

## Verification output

Changed-script smoke/help checks:

```text
$ .venv/bin/python .claude/skills/explain-code/scripts/inventory_symbols.py --target .claude/skills/explain-code/scripts/inventory_symbols.py --output /tmp/explain-code-targets.json --max 3
wrote /tmp/explain-code-targets.json: 1 annotated / 1 public / 11 total

$ .venv/bin/python .claude/skills/find-test-obligation-drift/scripts/run.py --help
usage: run.py [-h] [--project-root PROJECT_ROOT] [--staged]
              [--changed-from CHANGED_FROM] [--skip-effectiveness-log]
              [paths ...]

Run find-test-obligation-drift and write the standard report directory.

positional arguments:
  paths

options:
  -h, --help            show this help message and exit
  --project-root PROJECT_ROOT
  --staged
  --changed-from CHANGED_FROM
  --skip-effectiveness-log

$ .venv/bin/python .claude/skills/find-test-obligation-drift/scripts/detect.py --help
usage: detect.py [-h] [--project-root PROJECT_ROOT] [--staged]
                 [--changed-from CHANGED_FROM] --output OUTPUT
                 [paths ...]

Detect verification obligation drift for touched files.

positional arguments:
  paths

options:
  -h, --help            show this help message and exit
  --project-root PROJECT_ROOT
  --staged
  --changed-from CHANGED_FROM
  --output OUTPUT

$ .venv/bin/python .claude/skills/find-test-obligation-drift/scripts/smoke.py
find-test-obligation-drift smoke OK

$ .venv/bin/python .claude/skills/map-product-workflow/scripts/generate.py sample-workflow --scan-id replay-map-product-workflow --output /tmp/map-product-workflow.md --json-output /tmp/map-product-workflow.json --skip-effectiveness-log
wrote /tmp/map-product-workflow.md
wrote /tmp/map-product-workflow.json

$ .venv/bin/python .claude/skills/track-idea/scripts/track.py --help
usage: track.py [-h] {intake,event,lesson,list,show} ...

Idea ledger writer

positional arguments:
  {intake,event,lesson,list,show}
    intake              Append a new intake record
    event               Append an event record
    lesson              Append a lesson record
    list                List ideas with optional filters
    show                Show one idea's projection

options:
  -h, --help            show this help message and exit
```

Descriptor-absent map replay excerpt:

```text
$ sed -n '1,24p' /tmp/map-product-workflow.md
# Product workflow map — sample-workflow

Generated by `/map-product-workflow sample-workflow`.

## Descriptor Scope

| Field | Count |
|---|---:|
| Workflow steps | 0 |
| Target patterns | 0 |
| UI template patterns | 0 |
| UI script patterns | 0 |

_No workflow descriptor patterns were found; this map is expected to be mostly empty until `.engineering/docs/product-workflows.md` declares the host workflow._

## Workflow Steps

| Step | Canonical route | Canonical path | Actual route present |
|---|---|---|---|

## Page Routes

| Route | Name | View | File |
|---|---|---|---|
```

Required lint/test commands:

```text
$ .venv/bin/python scripts/skill_meta.py lint
OK — 74 skills, 74 declaring new contract

$ .venv/bin/python -m pytest -k 'explain or obligation or product_workflow or mature' -q
..                                                                       [100%]
2 passed, 367 deselected in 0.12s
```

Diff hygiene and forbidden-token checks:

```text
$ git diff --check -- .claude/skills/explain-code .claude/skills/find-test-obligation-drift .claude/skills/map-product-workflow .claude/skills/mature-existing-ideas

$ .venv/bin/python - <<'PY'
from pathlib import Path

paths = [
    *[Path(p) for p in __import__("subprocess").check_output(
        [
            "git", "ls-files",
            ".claude/skills/explain-code",
            ".claude/skills/find-test-obligation-drift",
            ".claude/skills/map-product-workflow",
            ".claude/skills/mature-existing-ideas",
        ],
        text=True,
    ).splitlines()],
    Path(".claude/tasks/skill-repairs/wave2-escalated.md"),
]
needles = ["p" + "nci", str(Path.home())]
hits = []
for path in paths:
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for needle in needles:
        if needle in text:
            hits.append(str(path))
if hits:
    print("\n".join(hits))
    raise SystemExit(1)
print("forbidden-token check OK")
PY
forbidden-token check OK
```

`git diff --check` produced no output and exited 0.
