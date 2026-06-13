---
name: find-dead-route-surface
description: |
  Advisory SUSPECT scan for configured product route-surface
  reachability: routes, templates, static JS, inline handlers,
  prototype pages, and orphaned page/API surfaces. Reuses
  `/find-dormant` URL extraction where useful, but focuses on the
  route/template/static wiring in configured targets or explicit paths.
argument-hint: "[paths... - defaults to workflow_targets(project_root); empty without .engineering/docs/product-workflows.md]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Finding old prototype routes, templates that no route/view renders,
  template script tags pointing at missing JS, loaded/unloaded static JS
  mismatches, and route views that reference missing templates.
not_for: |
  Whole-repo Python dead-code audits, deletion decisions, or blocking
  commits in v1. Use `/find-dormant` for broad dead-code archaeology and
  verify before deleting any route/template/static file.
language: any
framework: django
scans: [python, javascript, templates]
---

# /find-dead-route-surface

Run this when a product workflow feels like it has old pages, unloaded
JS, or template/static reachability drift. The report is a candidate
list for triage; deletion still needs human authorization and targeted
checks.

Default scope is not hard-coded to `/sites`. With no positional paths,
`scripts/run.py` passes `None` into `detect()`, and
`product_health.expand_paths()` scans `workflow_targets(project_root)`
from `.engineering/docs/product-workflows.md` (`## Targets`). If that
descriptor or section is absent, the default workflow target set is
empty. To scan a concrete surface, pass explicit positional paths after
`scripts/run.py`.
`legacy_prototype_route` may still inspect route records from
`app/urls.py` when present; pass explicit paths when you need exact
route/template/static scan scope.

## How success is judged

- The runner exits 0 and prints the scan directory it wrote.
- `reports/find-dead-route-surface/scan-<UTC>/detections.jsonl`,
  `report.md`, `findings.json`, and `latest` exist under the selected
  `--project-root`.
- The target scope is explicit in the command or comes from
  `workflow_targets(project_root)`; do not describe a no-descriptor run
  as a `/sites` scan.
- Findings are grouped by route/template/static detector bands and are
  treated as deletion-review candidates, never deletion authorization.

## Pipeline

```
.venv/bin/python .claude/skills/find-dead-route-surface/scripts/run.py <paths...>
```

`<paths...>` are positional path or glob arguments. Omit them only when
the host repo has declared `## Targets` in
`.engineering/docs/product-workflows.md`.

Standard report artifacts are written under
`reports/find-dead-route-surface/scan-<UTC>/`.

## Detector Bands

- `legacy_prototype_route`: URL pattern still exposes a prototype/dev
  surface.
- `route_template_missing`: Python view references a template that is
  absent from scanned template roots.
- `unreferenced_template_surface`: site template exists but no scanned
  view/template reference points at it.
- `missing_static_js`: template references a static JS asset that does
  not exist.
- `unloaded_site_static_js`: site static JS exists but no scanned site
  template loads it.

## When things go sideways

| Symptom | Action |
|---|---|
| Descriptor absent | Treat the default workflow target set as empty; pass explicit positional paths or add `## Targets` to `.engineering/docs/product-workflows.md`. |
| Zero findings | Check whether `detections.jsonl` is empty because the workflow target set expanded to no `.py`, `.js`, or `.html` files; rerun with explicit paths before calling route/template/static reachability clean. |
| Script failure | Re-run the exact `.venv/bin/python .claude/skills/find-dead-route-surface/scripts/run.py ...` command, capture stderr, and fix the path/import/argparse failure before interpreting results. |
