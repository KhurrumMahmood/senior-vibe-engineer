# Wave 3 W3-1 drift scanners repair report

## Scope

Owned skill directories repaired:

- `find-folder-topology-drift`
- `find-frontend-contract-drift`
- `find-comment-drift`
- `find-complexity-hotspots`
- `find-concept-divergence`
- `find-doc-route-drift`

Touched files:

- `.claude/skills/find-folder-topology-drift/SKILL.md`
- `.claude/skills/find-folder-topology-drift/scripts/detect.py`
- `.claude/skills/find-frontend-contract-drift/SKILL.md`
- `.claude/skills/find-frontend-contract-drift/scripts/report.py`
- `.claude/skills/find-comment-drift/SKILL.md`
- `.claude/skills/find-comment-drift/scripts/detect.py`
- `.claude/skills/find-comment-drift/scripts/report.py`
- `.claude/skills/find-complexity-hotspots/SKILL.md`
- `.claude/skills/find-concept-divergence/SKILL.md`
- `.claude/skills/find-doc-route-drift/SKILL.md`

No commits were made. Pre-existing unrelated worktree changes were left
alone.

## Per-skill triage verification

### find-folder-topology-drift

- F1 `Default-root contract contradicts argparse`: TRUE. The old
  `SKILL.md` documented `app/` and invoked `detect.py --root app`, while
  `detect.py --help` says `--root` defaults to the whole repo narrowed by
  scope/ignore descriptors. Fixed the scope prose and pipeline to omit
  `--root` by default and label the report target `default scope`.
- F2 `Frontmatter/scope also disagree`: TRUE. The old argument hint used
  `--root core` while the scope text said `app/`. Changed the hint to
  `--root PATH`.
- F3 `Missing declared verdict, honest failure path, replay case`: TRUE.
  Added `How success is judged`, artifact-truth gates, verdict vocabulary,
  replay commands, and a `When things go sideways` table.
- Additional verified cleanup: public detector help still had a baked
  application-root route-mirror example. Genericized it to
  route-mirrored `pages/` folders without changing detector behavior.

### find-frontend-contract-drift

- F1 `Documented template/JS defaults contradict argparse`: TRUE. The old
  scope text said default roots were `templates/` and `static/js/`; the
  detector defaults both flags to `None` and scans the scope universe.
  Fixed prose and argument hint to make those roots optional narrowing
  flags.
- F2 `Pipeline omits flags that would make documented defaults true`:
  TRUE. The correct fix was to update the documented default to match the
  detector, not to bake roots into the command. The pipeline now uses
  `.venv/bin/python` and target label `default scope`.
- F3 `Missing declared verdict, failure path, replay case`: TRUE. Added
  the success block, artifact gates, verdict vocabulary, replay commands,
  and failure table.
- Additional verified cleanup: removed the stale public `/sites` alias
  from the reporter target-scope helper. Existing non-default workflow
  buckets remain scanner behavior.

### find-comment-drift

- F1 `Declared verdict and honest failure path missing`: TRUE. The smoke
  existed, but the skill lacked a near-top success gate and sideways
  table. Added both, plus artifact-truth gates and verdict vocabulary.
- Additional verified cleanup: changed public help/report wording from a
  hard `/sites` label to `legacy site-workflow surface` while preserving
  the detector's actual legacy default target list. That list and one bad
  fixture still contain `app/...` paths because they are current detector
  semantics/fixture evidence, not stale prose.

### find-complexity-hotspots

- F1 `Declared verdict and honest failure path missing`: TRUE. Added a
  near-top success block, artifact gates, verdict vocabulary, Agent
  citation contract, and failure table.
- F2 `Replay wiring absent from skill text`: TRUE. `scripts/smoke.py`
  existed but was not documented. Added it as the replay case and changed
  example commands from placeholders to executable skill-dir targets.
- Reference check: `references/reading-notes.md` and `agents/openai.yaml`
  exist and are non-empty.

### find-concept-divergence

- F1 `Declared verdict/failure gates missing`: TRUE. Added the success
  block, artifact gates, verdict vocabulary, Agent citation contract, and
  failure table.
- F2 `Replay-case element absent`: TRUE. No fixture smoke exists for this
  scanner, so added a bounded self-scan replay that exercises the real
  glossary and output contract without claiming whole-repo cleanliness.
- Reference check: `.claude/contracts/concepts.yaml` exists and is
  non-empty. `host_excludes.txt` remains optional by script design and is
  not a mandated reader target.

### find-doc-route-drift

- F1 `Missing success gate, failure path, replay case`: TRUE. Added
  near-top success gates, artifact truth requirements, verdict vocabulary,
  Agent citation contract, replay commands, and a failure table.
- Reference check: `.claude/docs` exists and contains files; the root
  URL source remains auto-discovered unless `--root-urls` is supplied.

## Cross-cutting checks

- `dispatch_scout_cheap.sh` / `tools.code_agent`: no owned skill routes
  through that path, so no Agent-tool default needed to be changed.
- Public default-root contradictions were fixed against real argparse
  behavior.
- Knowledge/reference targets used by these skills were checked for
  existence and non-empty content where applicable.
- Forbidden tracked-content guard: no matches for the forbidden token or
  local absolute user-path form in the touched skill directories.

Reference/output checks:

```text
$ wc -c .claude/skills/find-complexity-hotspots/references/reading-notes.md .claude/skills/find-complexity-hotspots/agents/openai.yaml
    1863 .claude/skills/find-complexity-hotspots/references/reading-notes.md
     232 .claude/skills/find-complexity-hotspots/agents/openai.yaml
    2095 total
```

```text
$ wc -c .claude/skills/_common/product_topology.py
   29378 .claude/skills/_common/product_topology.py
```

```text
$ wc -c .claude/skills/_common/structural-design-principles.md
   12371 .claude/skills/_common/structural-design-principles.md
```

```text
$ wc -c .claude/contracts/concepts.yaml
   11498 .claude/contracts/concepts.yaml
```

```text
$ find .claude/docs -maxdepth 1 -type f | wc -l
      17
```

## Verification output

### Required gates

```text
$ .venv/bin/python scripts/skill_meta.py lint
OK — 76 skills, 76 declaring new contract
```

```text
$ .venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/detect.py --gate find-folder-topology-drift find-frontend-contract-drift find-comment-drift find-complexity-hotspots find-concept-divergence find-doc-route-drift
(no stdout/stderr; exit 0)
```

```text
$ git diff --check -- .claude/skills/find-folder-topology-drift .claude/skills/find-frontend-contract-drift .claude/skills/find-comment-drift .claude/skills/find-complexity-hotspots .claude/skills/find-concept-divergence .claude/skills/find-doc-route-drift
(no stdout/stderr; exit 0)
```

### Help, smoke, and bounded replay checks

```text
$ .venv/bin/python .claude/skills/find-folder-topology-drift/scripts/detect.py --help
usage: detect.py [-h] [--root ROOT] [--project-root PROJECT_ROOT]
                 [--min-cluster-size MIN_CLUSTER_SIZE] [--exclude EXCLUDE]
                 --output OUTPUT

Detect drift on the folder-topology surface (ADR 0006). Stage 1 detection
bands: - flat_prefix_cluster: a directory contains N+ Python modules sharing
the same `<prefix>_` token, where `prefix` names a domain (>= 2 chars). -
tests_by_prefix: a directory contains N+ files matching `tests_*.py` AND has
no `tests/` subfolder. - sparse_folder_package: a folder package (has
`__init__.py`) contains FEWER than N source modules at its top level — the
demotion direction added by ADR 0006 Rule 5. The threshold is the same N as
the promotion bands; folders earn packaging at ≥3 siblings and lose it below
≥3. - pages_route_mirror: a file under `pages/<parent>/` whose basename starts
with a token matching a singularization of the parent folder name (e.g.
`pages/sites/site_wizard.py` — the `site_` prefix duplicates the parent
`sites/`). Implements ADR 0010: filenames under route-mirrored `pages/`
folders strip parent-folder prefixes so a reader who knows the route knows the
file. Stage 2 bands (deferred — see SKILL.md): - route_folder_misalignment -
same_domain_helper_sprawl Output: JSONL with one finding per line. Each record
has the keys `pattern`, `file`, `lineno`, `summary`, `recommendation` so the
shared render_simple_report helper can render it.

options:
  -h, --help            show this help message and exit
  --root ROOT           Optional subtree to narrow the scan to (per-invocation
                        override). Default: the whole repo, narrowed only by
                        the host's scope/ignore descriptors
                        (.engineering/docs/<skill>-scope.md and ignore.md).
  --project-root PROJECT_ROOT
                        Project root for relative-path display (default: cwd)
  --min-cluster-size MIN_CLUSTER_SIZE
                        Minimum siblings to count as a cluster (default: 3,
                        per ADR 0006)
  --exclude EXCLUDE     Additional ignore glob, additive on top of scope
                        (repeatable)
  --output OUTPUT
```

```text
$ .venv/bin/python .claude/skills/find-folder-topology-drift/scripts/detect.py --root .claude/skills/find-folder-topology-drift --output /tmp/find-folder-topology-drift-replay.jsonl && .venv/bin/python .claude/skills/find-folder-topology-drift/scripts/report.py --detections /tmp/find-folder-topology-drift-replay.jsonl --output-md /tmp/find-folder-topology-drift-report.md --output-json /tmp/find-folder-topology-drift-findings.json --target .claude/skills/find-folder-topology-drift
detect: wrote 0 findings to /tmp/find-folder-topology-drift-replay.jsonl
wrote /tmp/find-folder-topology-drift-report.md
wrote /tmp/find-folder-topology-drift-findings.json
```

```text
$ .venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/detect.py --help
usage: detect.py [-h] [--project-root PROJECT_ROOT]
                 [--template-root TEMPLATE_ROOT] [--js-root JS_ROOT]
                 [--boot-threshold BOOT_THRESHOLD] --output OUTPUT

Detect implicit frontend boot contracts between templates and JS.

options:
  -h, --help            show this help message and exit
  --project-root PROJECT_ROOT
  --template-root TEMPLATE_ROOT
                        optional per-invocation override; default is the whole
                        repo, narrowed only by the host's scope/ignore
                        descriptors.
  --js-root JS_ROOT     optional per-invocation override; default is the whole
                        repo, narrowed only by the host's scope/ignore
                        descriptors.
  --boot-threshold BOOT_THRESHOLD
  --output OUTPUT
```

```text
$ .venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/report.py --help
usage: report.py [-h] --detections DETECTIONS --output-md OUTPUT_MD
                 --output-json OUTPUT_JSON --scan-id SCAN_ID --target TARGET
                 [--project-root PROJECT_ROOT] [--skip-effectiveness-log]

Render frontend-contract-drift findings.

options:
  -h, --help            show this help message and exit
  --detections DETECTIONS
  --output-md OUTPUT_MD
  --output-json OUTPUT_JSON
  --scan-id SCAN_ID
  --target TARGET
  --project-root PROJECT_ROOT
  --skip-effectiveness-log
```

```text
$ .venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/detect.py --template-root .claude/skills/find-frontend-contract-drift --js-root .claude/skills/find-frontend-contract-drift --output /tmp/find-frontend-contract-drift-replay.jsonl && .venv/bin/python .claude/skills/find-frontend-contract-drift/scripts/report.py --detections /tmp/find-frontend-contract-drift-replay.jsonl --output-md /tmp/find-frontend-contract-drift-report.md --output-json /tmp/find-frontend-contract-drift-findings.json --scan-id scan-replay --target .claude/skills/find-frontend-contract-drift --skip-effectiveness-log
wrote /tmp/find-frontend-contract-drift-replay.jsonl: 0 findings
wrote /tmp/find-frontend-contract-drift-report.md
wrote /tmp/find-frontend-contract-drift-findings.json
```

```text
$ .venv/bin/python .claude/skills/find-comment-drift/scripts/detect.py --help
usage: detect.py [-h] --output OUTPUT [--project-root PROJECT_ROOT]
                 [paths ...]

Detect comment/docstring/JSDoc drift.

positional arguments:
  paths                 Files or directories to scan. Defaults to the legacy
                        site-workflow surface.

options:
  -h, --help            show this help message and exit
  --output OUTPUT       JSONL output path.
  --project-root PROJECT_ROOT
                        Target project root anchoring relative paths (default:
                        git toplevel of cwd, else cwd)
```

```text
$ .venv/bin/python .claude/skills/find-comment-drift/scripts/report.py --help
usage: report.py [-h] --output OUTPUT [--target TARGET] detections

Render comment-drift findings.

positional arguments:
  detections

options:
  -h, --help       show this help message and exit
  --output OUTPUT
  --target TARGET
```

```text
$ .venv/bin/python .claude/skills/find-comment-drift/scripts/smoke.py
OK - 17 bad fixture findings, good fixtures clean
```

```text
$ .venv/bin/python .claude/skills/find-comment-drift/scripts/detect.py --output /tmp/find-comment-drift-replay.jsonl .claude/skills/find-comment-drift && .venv/bin/python .claude/skills/find-comment-drift/scripts/report.py /tmp/find-comment-drift-replay.jsonl --output /tmp/find-comment-drift-report.md --target .claude/skills/find-comment-drift
scanned 9 files; wrote 18 findings to /tmp/find-comment-drift-replay.jsonl
wrote /tmp/find-comment-drift-report.md
```

```text
$ .venv/bin/python .claude/skills/find-complexity-hotspots/scripts/run.py --help
usage: run.py [-h] [--project-root PROJECT_ROOT] [--include-tests]
              [--max-findings MAX_FINDINGS] [--skip-effectiveness-log]
              paths [paths ...]

Run find-complexity-hotspots and write the standard report directory.

positional arguments:
  paths                 Files, directories, or globs to scan.

options:
  -h, --help            show this help message and exit
  --project-root PROJECT_ROOT
  --include-tests
  --max-findings MAX_FINDINGS
  --skip-effectiveness-log
```

```text
$ .venv/bin/python .claude/skills/find-complexity-hotspots/scripts/smoke.py
OK - 6 bad fixture findings, good fixture clean
```

```text
$ .venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py --help
usage: scan.py [-h] [--glossary GLOSSARY] [--project-root PROJECT_ROOT]
               --output OUTPUT --report REPORT
               [targets ...]

Strict concept-divergence scan.

positional arguments:
  targets               paths to scan (relative to repo root)

options:
  -h, --help            show this help message and exit
  --glossary GLOSSARY   glossary path (default: <project-
                        root>/.claude/contracts/concepts.yaml)
  --project-root PROJECT_ROOT
                        Target project root anchoring scan targets, labels,
                        and the glossary default (default: git toplevel of
                        cwd, else cwd)
  --output OUTPUT       JSONL findings path
  --report REPORT       Markdown report path
```

```text
$ .venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py --output /tmp/find-concept-divergence-replay.jsonl --report /tmp/find-concept-divergence-report.md .claude/skills/find-concept-divergence
wrote 0 findings → /tmp/find-concept-divergence-replay.jsonl
report → /tmp/find-concept-divergence-report.md
```

```text
$ .venv/bin/python .claude/skills/find-doc-route-drift/scripts/detect.py --help
usage: detect.py [-h] [--project-root PROJECT_ROOT] [--docs-root DOCS_ROOT]
                 [--root-urls ROOT_URLS] --output OUTPUT

Detect docs that drift from Django route and redirect reality.

options:
  -h, --help            show this help message and exit
  --project-root PROJECT_ROOT
  --docs-root DOCS_ROOT
  --root-urls ROOT_URLS
                        Single urlconf override (default: auto-discover all
                        urls.py + *_urls.py)
  --output OUTPUT
```

```text
$ .venv/bin/python .claude/skills/find-doc-route-drift/scripts/detect.py --docs-root .claude/docs --output /tmp/find-doc-route-drift-replay.jsonl && .venv/bin/python .claude/skills/find-doc-route-drift/scripts/report.py --detections /tmp/find-doc-route-drift-replay.jsonl --output-md /tmp/find-doc-route-drift-report.md --output-json /tmp/find-doc-route-drift-findings.json --scan-id scan-replay --target .claude/docs --skip-effectiveness-log
wrote /tmp/find-doc-route-drift-replay.jsonl: 0 findings
wrote /tmp/find-doc-route-drift-report.md
wrote /tmp/find-doc-route-drift-findings.json
```

### Pytest

```text
$ rg --files | rg '(find_(folder_topology|frontend_contract|comment|complexity|concept|doc_route)|folder-topology|frontend-contract|comment-drift|complexity-hotspots|concept-divergence|doc-route|doc_route|test_.*(folder|frontend|comment|complexity|concept|doc))'
(no matching pytest files found; exit 1)
```

No matching pytest suite exists for these six skills. The verification
coverage for this lane is the required meta lint, artifact-drift gate,
script help checks, fixture smokes where shipped, and bounded
detector/report replays.
