# W3-4 MINOR Batch 3 Repair Report

Owned skill dirs:

- `.claude/skills/plan-feature/`
- `.claude/skills/plan-spec/`
- `.claude/skills/propose-folder-reorganization/`
- `.claude/skills/teach-pattern/`
- `.claude/skills/track-idea/`
- `.claude/skills/which-skill/`

Standard read first: `.claude/skills/repair-skill/knowledge/skill-standard.md`.
Reference exemplars read: `fix-workflow`, `converge`, and `audit-decisions`.

## plan-feature

Findings verified:

- TRUE: batch-5 said the skill recommends `--force` for an existing spec, but its argument surface only listed `<feature-name> [--subsystems <a,b,c>]`. Ground truth: `scripts/specs.py init --help` exposes `--force`, and the skill did recommend it on collision. Fixed by adding `--force` to `argument-hint`, documenting its decision gate, and passing `${FORCE_FLAG}` to `scripts/specs.py init`.
- TRUE: executable-as-written drift found during the standard pass: the skill documented bare `python3` for `scripts/specs.py`, `scripts/decisions.py`, and `scripts/log_effectiveness.py`; the repo scripts use the repo dependency set. Fixed documented invocations to `.venv/bin/python`.
- TRUE: declared-verdict dispatch was weak for the Explore dispatch and scout prompt. Fixed both dispatch texts to say how the output will be judged and that evidence paths, not claims, are required.
- TRUE: scaffold wording drift found during the standard pass: the skill described a proposed-status spec and "six sections"; the real `specs.py init` scaffold has five narrative sections and optional `lifecycle:` frontmatter. Fixed to say populated `draft` spec with `lifecycle: proposed`, and "five narrative sections".
- FALSE: none.

Edits made:

- Updated `.claude/skills/plan-feature/SKILL.md` argument contract, Python commands, force pass-through, dispatch verdict, and scaffold/status wording.
- Updated `.claude/skills/plan-feature/agents/impact-scout.md` with a declared output judgment gate.

## plan-spec

Findings verified:

- TRUE: adversarial-4-5 said Stage 4 claimed six standard sections and `Lifecycle <- proposed`, but `scripts/specs.py` emits five `##` sections and `plans.py promote` never passes `--lifecycle`. Verified from `scripts/specs.py` and `scripts/plans.py promote --help`. Fixed Stage 4 to name the five narrative sections and removed lifecycle reporting.
- TRUE: adversarial-4-5 said Stage 5 used `${SPEC_ID}` before assignment. Fixed by assigning `SPEC_ID` in setup and documenting optional `--spec-id <id>`.
- TRUE: executable-as-written drift found during the standard pass: the skill documented bare `python3` for PyYAML-backed `plans.py` / `specs.py`. Fixed to `.venv/bin/python`.
- FALSE: none.

Edits made:

- Updated `.claude/skills/plan-spec/SKILL.md` argument hint, setup, promote/audit/inventory-check commands, scaffold section wording, and summary contract.

## propose-folder-reorganization

Findings verified:

- TRUE: batch-5 said the early stop threshold used "fewer than 2 sibling files" while the helper and later calibration use the ADR 0006 `<3` threshold. Verified `inspect.py --help` default `--min-cluster-size 3` and existing defer text "fewer than 3". Fixed the early stop text to "fewer than 3 sibling files".
- FALSE: none.

Edits made:

- Updated `.claude/skills/propose-folder-reorganization/SKILL.md` threshold prose only.

## teach-pattern

Findings verified:

- TRUE: batch-5 said the Scope read path used stale `reports/<find-*>/latest/` while Stage 4 correctly says on-disk dirs omit the `find-` prefix. Fixed Scope to `reports/<smell>/latest/` with the same convention note.
- TRUE: small standard cleanup found during the pass: the skill has no helper script, so `Python: python3 (stdlib-only)` was loadless. Replaced it with "no helper script is shipped; use shell reads/greps only."
- FALSE: none.

Edits made:

- Updated `.claude/skills/teach-pattern/SKILL.md` Scope read/Python text.

## track-idea

Findings verified:

- TRUE: batch-5 said `/promote-idea-to-pattern` handoffs point to a missing skill. Verified no such skill dir exists. Fixed all handoffs to manual Tier 2 promotion via `.claude/docs/pattern-library.md`.
- TRUE: standard pass found no near-top "How success is judged" block. Added one covering append-only behavior, script-output truth, read-form output, and manual Tier 2 handling.
- TRUE: executable-as-written cleanup: documented helper invocations now use `.venv/bin/python`.
- FALSE: none.

Edits made:

- Updated `.claude/skills/track-idea/SKILL.md` success gate, Tier 2 promotion wording, non-goals, stop stage, and helper commands.

## which-skill

Findings verified:

- TRUE: adversarial-4-5 said Stage 1 and Stage 3 documented bare `python3`, but `match.py` imports the shared YAML frontmatter parser. Fixed matcher and effectiveness commands to `.venv/bin/python`.
- TRUE: standard pass found no near-top "How success is judged" block. Added one covering matcher exit-code truth, frontmatter-only scope, and effectiveness row contents.
- FALSE: none.

Edits made:

- Updated `.claude/skills/which-skill/SKILL.md` success gate and Python commands.

## Reference Target Check

All checked concrete references existed and were non-empty:

```text
OK file .claude/skills/plan-feature/agents/impact-scout.md
OK file .claude/skills/plan-feature/knowledge/rules.md
OK file .claude/skills/_common/dispatch_scout.sh
OK file .claude/skills/_common/skill-frontmatter.md
OK file .claude/skills/_common/structural-design-principles.md
OK file .claude/skills/_common/ideas_lib.py
OK file .claude/docs/canonical-patterns.md
OK file .claude/docs/architectural-smells.md
OK file .claude/docs/skill-catalog.md
OK file .claude/docs/idea-ledger.md
OK file .claude/docs/pattern-library.md
OK file .claude/CLAUDE.md
OK file ai-docs/decisions/README.md
OK file ai-docs/decisions/0006-folder-organization.md
OK file ai-docs/decisions/0013-idea-tracking-system.md
OK dir  ai-docs/decisions (30 files)
OK dir  ai-docs/specs (1 files)
OK file scripts/specs.py
OK file scripts/decisions.py
OK file scripts/plans.py
OK file scripts/log_effectiveness.py
OK file scripts/_lib/yaml_frontmatter.py
OK file .claude/skills/propose-folder-reorganization/scripts/inspect.py
OK file .claude/skills/track-idea/scripts/track.py
OK file .claude/skills/which-skill/scripts/match.py
OK file .claude/skills/find-orphaned-ideas/SKILL.md
OK file .claude/skills/query-patterns/SKILL.md
OK file .claude/skills/refactor-subsystem/SKILL.md
OK file .claude/skills/scope-feature/SKILL.md
OK file .claude/skills/impact-feature/SKILL.md
OK file .claude/skills/architecture-fit/SKILL.md
OK file .claude/skills/find-folder-topology-drift/SKILL.md
OK file .claude/skills/decide/SKILL.md
OK file .claude/skills/which-skill/SKILL.md
```

## Verification Output

### `.venv/bin/python scripts/skill_meta.py lint`

```text
OK — 76 skills, 76 declaring new contract
```

### `.venv/bin/python .claude/skills/find-skill-artifact-drift/scripts/detect.py --gate plan-feature plan-spec propose-folder-reorganization teach-pattern track-idea which-skill`

```text
<no output; exit 0>
```

### `.venv/bin/python .claude/skills/track-idea/scripts/track.py --help`

```text
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

### `.venv/bin/python .claude/skills/which-skill/scripts/match.py --help`

```text
usage: match.py [-h] [--skills-dir SKILLS_DIR] [--project-root PROJECT_ROOT]
                [--top TOP] [--threshold THRESHOLD] [--json]
                task

Rank skills against a free-text task description.

positional arguments:
  task                  Free-text description of the task ('add per-site
                        export TTL override').

options:
  -h, --help            show this help message and exit
  --skills-dir SKILLS_DIR
                        Override the skills directory (default:
                        .claude/skills/)
  --project-root PROJECT_ROOT
                        Repo whose .engineering/manifest.json declares skill
                        activation; inactive skills are excluded from
                        recommendations (default: this repo).
  --top TOP             How many candidates to show
  --threshold THRESHOLD
                        Minimum score to count as a real recommendation
                        (default: 5)
  --json                Emit JSON instead of text
```

### `.venv/bin/python .claude/skills/propose-folder-reorganization/scripts/inspect.py --help`

```text
usage: inspect.py [-h] --parent PARENT --prefix PREFIX
                  [--project-root PROJECT_ROOT]
                  [--min-cluster-size MIN_CLUSTER_SIZE] [--exclude EXCLUDE]
                  --output OUTPUT

Inspect a folder-topology cluster and its import impact. Given a parent
directory and a leading-underscore prefix, gather: - cluster_files: each
cluster file's path, line count, public symbols - import_impact: every import
line in the project that resolves to a cluster member, with the after-rename
target precomputed - matched_tests: tests_<prefix>_*.py files at the parent
(or at the project root / an app root) that exercise cluster members -
singletons_at_parent: count of sibling files at the parent that are NOT in the
cluster and NOT in noise tokens - defer_signals: guardrail trips
(cluster_below_threshold, scratch_code, framework_convention) Output: JSON
with the keys above. Stdlib only.

options:
  -h, --help            show this help message and exit
  --parent PARENT       Parent directory containing the cluster (e.g.
                        <package>/views).
  --prefix PREFIX       Leading-underscore prefix without trailing _ (e.g.
                        site_config). Special value `tests` triggers
                        tests_by_prefix mode.
  --project-root PROJECT_ROOT
                        Project root (default: cwd).
  --min-cluster-size MIN_CLUSTER_SIZE
                        Minimum siblings to count as a cluster (default: 3).
  --exclude EXCLUDE     Additional glob pattern to exclude (additive;
                        repeatable).
  --output OUTPUT
```

### `.venv/bin/python scripts/plans.py promote --help && .venv/bin/python scripts/specs.py init --help && .venv/bin/python scripts/specs.py inventory-check --help`

```text
usage: plans.py promote [-h] [--spec-id SPEC_ID] --code-roots CODE_ROOTS
                        [--allow-missing] [--force]
                        slug

positional arguments:
  slug

options:
  -h, --help            show this help message and exit
  --spec-id SPEC_ID     Spec slug (defaults to plan slug)
  --code-roots CODE_ROOTS
                        Spec code roots (repeat)
  --allow-missing       Allow missing code roots in scaffold
  --force               Overwrite existing spec
usage: specs.py init [-h] --code-roots CODE_ROOTS [--title TITLE]
                     [--date DATE] [--force] [--allow-missing]
                     [--motivating-decision MOTIVATING_DECISION]
                     [--lifecycle {proposed,planned,active,shipped}]
                     spec_id

Create a new stub spec for a legacy code cluster. Any .py code root above the
inventory LOC threshold gets an auto-generated inventory table extracted via
AST walk. All narrative sections are left as empty placeholders. The resulting
spec is marked as a stub so `inventory-check` reports status=STUB until a
human has authored real content.

positional arguments:
  spec_id               New spec id — lowercase slug (e.g. 'crawling-views').

options:
  -h, --help            show this help message and exit
  --code-roots CODE_ROOTS
                        Repo-relative path to include as a code_root. Repeat
                        for multiple roots (e.g. --code-roots
                        core/views/crawling.py --code-roots
                        core/services/crawling_service.py).
  --title TITLE         Override the spec title (default: derived from
                        spec_id).
  --date DATE           Override last_audited date (default: today in ISO
                        8601).
  --force               Overwrite the spec file if it already exists.
  --allow-missing       Allow code_roots that do not exist on disk yet.
  --motivating-decision MOTIVATING_DECISION
                        Optional ADR id (e.g. '0042') linking this spec back
                        to the decision that authorized the work. Used by
                        /plan-feature and the System-tier planning chain.
  --lifecycle {proposed,planned,active,shipped}
                        Optional planning-tier lifecycle marker.
                        proposed=plan-feature stub; planned=approved for
                        execution; active=in flight; shipped=closed.
usage: specs.py inventory-check [-h] [--strict] spec_id

positional arguments:
  spec_id

options:
  -h, --help  show this help message and exit
  --strict    Exit 1 if any mismatch or stub warning is detected
```

### `.venv/bin/python -m pytest tests/test_which_skill_recommendations.py tests/scripts/test_project_root_debaking.py tests/test_skill_taxonomy.py`

Path note: `rootdir` is shortened to `~/...` here to avoid writing the local username into a tracked file.

```text
============================= test session starts ==============================
platform darwin -- Python 3.11.10, pytest-9.0.3, pluggy-1.6.0
rootdir: ~/Projects/engineering-skills
configfile: pyproject.toml
collected 17 items

tests/test_which_skill_recommendations.py ......                         [ 35%]
tests/scripts/test_project_root_debaking.py ........                     [ 82%]
tests/test_skill_taxonomy.py ...                                         [100%]

============================== 17 passed in 1.49s ==============================
```

### `git diff --check -- .claude/skills/plan-feature .claude/skills/plan-spec .claude/skills/propose-folder-reorganization .claude/skills/teach-pattern .claude/skills/track-idea .claude/skills/which-skill`

```text
<no output; exit 0>
```

### Stale-string / forbidden-path scan

Command:

```bash
rg -n "<targeted stale strings and forbidden local-path/token patterns>" .claude/skills/plan-feature .claude/skills/plan-spec .claude/skills/propose-folder-reorganization .claude/skills/teach-pattern .claude/skills/track-idea .claude/skills/which-skill
```

Result:

```text
<no output; exit 1/no matches>
```

## Matching pytest

Matching pytest existed and was run:

- `tests/test_which_skill_recommendations.py`
- `tests/scripts/test_project_root_debaking.py`
- `tests/test_skill_taxonomy.py`

No commits were made.
