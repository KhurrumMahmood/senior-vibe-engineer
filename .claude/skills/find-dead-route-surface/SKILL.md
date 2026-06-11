---
name: find-dead-route-surface
description: |
  Advisory SUSPECT scan for `/sites` route-surface reachability:
  routes, templates, static JS, inline handlers, prototype pages, and
  orphaned page/API surfaces. Reuses `/find-dormant` URL extraction
  where useful, but focuses on `/sites` route/template/static wiring.
argument-hint: "[paths... - defaults to the /sites route surface]"
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

Run this when `/sites` feels like it has old pages, unloaded JS, or
template/static reachability drift. The report is a candidate list for
triage; deletion still needs human authorization and targeted checks.

## Pipeline

```
.venv/bin/python .claude/skills/find-dead-route-surface/scripts/run.py <paths...>
```

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
