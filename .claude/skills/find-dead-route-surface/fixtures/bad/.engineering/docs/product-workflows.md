# Product workflow — find-dead-route-surface fixture

Host-authored scan scope for this fixture. The detector reads `## Targets` via
`workflow_targets` (`.claude/skills/_common/workflows.py`) instead of a baked-in
`/sites` path list; `app/urls.py` is discovered directly by the route walker.

## Targets
- app/pages/sites
- app/api/ptid.py
- static/js/site-config-*.js
