# Wave 1 Host-Residue Repair

## Scope

Owned edits landed in:

- `.claude/skills/_common/dispatch_scout_cheap.sh`
- `.claude/skills/find-dormant/SKILL.md`
- `.claude/skills/find-async-lifecycle-drift/SKILL.md`
- `.claude/skills/find-contract-drift/SKILL.md`
- `.claude/skills/find-dead-route-surface/SKILL.md`
- `.claude/skills/which-cleanup/SKILL.md`
- `.claude/skills/propose-boundary/SKILL.md`

`rg -n "dispatch_scout_cheap" .claude/skills -g 'SKILL.md'` also found references in other SKILL.mds outside this lane's ownership. Those were not edited.

## Per-Skill Results

### find-dormant

Findings verified: TRUE.

- `dispatch_scout_cheap.sh` hard-invoked `-m tools.code_agent`; `tools.code_agent` is not importable in this toolkit repo.
- `tools/agent-config.json` is not a shipped toolkit file; the SKILL now marks that registry as a `<!-- host-adapter -->` slot.
- `allowed-tools` included `Edit` even though the skill is detection-only.

Edits made:

- Removed `Edit` from `allowed-tools`.
- Added the cheap-dispatch caveat: host `tools.code_agent` backend required; inline scouting applies when absent.
- Reworded the model-alias paragraph so `tools/agent-config.json` is explicitly host-adapter-only and absent from this toolkit repo.

### find-async-lifecycle-drift

Findings verified: TRUE.

- `scripts/run.py` defines positional `paths`, `--project-root`, and `--skip-effectiveness-log`.
- With no positional paths, `detect()` receives `None`; `product_health.expand_paths()` then uses `workflow_targets(project_root)`.
- `.engineering/docs/product-workflows.md` is absent in this repo, so the workflow target set is empty.

Edits made:

- Replaced the `/sites` default claim with the descriptor-driven `workflow_targets(project_root)` default.
- Documented explicit positional paths.
- Added skill-specific "How success is judged" and "When things go sideways" blocks using the async detector bands.

### find-contract-drift

Findings verified: PARTLY.

- The documented `/sites` route-surface default was false: `scripts/run.py` passes positional `paths` or `None`, and `product_health.expand_paths()` uses `workflow_targets(project_root)` when paths are omitted.
- `.engineering/docs/product-workflows.md` is absent in this repo, so the workflow target set is empty.
- Additional grounded nuance: `scripts/detect.py` imports boot-global findings via `workflow_template_roots(project_root)` and has a no-path `templates/core/includes` expansion. The SKILL now avoids promising a `/sites` default and tells callers to pass explicit paths for concrete scope.

Edits made:

- Replaced `/sites` default wording with configured product-workflow target wording.
- Documented explicit positional paths.
- Added skill-specific "How success is judged" and "When things go sideways" blocks using contract detector bands.

### find-dead-route-surface

Findings verified: PARTLY.

- The documented `/sites` route-surface default was false: `scripts/run.py` passes positional `paths` or `None`, and `product_health.expand_paths()` uses `workflow_targets(project_root)` when paths are omitted.
- `.engineering/docs/product-workflows.md` is absent in this repo, so the workflow target set is empty.
- Additional grounded nuance: `scripts/detect.py` still has route-record logic for `legacy_prototype_route`; the SKILL now avoids promising a `/sites` default and tells callers to pass explicit paths for concrete route/template/static scope.

Edits made:

- Replaced `/sites` default wording with configured product route-surface wording.
- Documented explicit positional paths.
- Added skill-specific "How success is judged" and "When things go sideways" blocks using route/template/static detector bands.

### which-cleanup

Findings verified: TRUE for the in-scope line.

Edits made:

- Added the one-line caveat at the `dispatch_scout_cheap.sh` mention: host `tools.code_agent` backend required; inline scouting applies when absent.

### propose-boundary

Findings verified: TRUE for the in-scope line.

Edits made:

- Added the one-line caveat at the `dispatch_scout_cheap.sh` mention: host `tools.code_agent` backend required; inline scouting applies when absent.

## Verification Output

Command:

```bash
.venv/bin/python scripts/skill_meta.py lint
```

Output:

```text
OK — 74 skills, 74 declaring new contract
```

Command:

```bash
bash -n .claude/skills/_common/dispatch_scout_cheap.sh
```

Output:

```text
<no output; exit 0>
```

Command:

```bash
.venv/bin/python .claude/skills/find-async-lifecycle-drift/scripts/run.py --project-root <temp-project-root> --skip-effectiveness-log static/js/sample.js
```

Output:

```text
wrote <temp-project-root>/reports/find-async-lifecycle-drift/scan-20260613-010628
```

Argparse note: the product-health runners expose positional `paths`, not a `--paths` flag, so the smoke used an explicit positional path.
