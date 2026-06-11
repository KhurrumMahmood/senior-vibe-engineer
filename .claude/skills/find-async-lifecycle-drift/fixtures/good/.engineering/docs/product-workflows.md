# Product workflow — find-async-lifecycle-drift fixture

Host-authored scan scope for this fixture. The detector reads `## Targets` via
`workflow_targets` (`.claude/skills/_common/workflows.py`) instead of a baked-in
`/sites` path list.

## Targets
- app/api/site_config
- static/js/site-config-*.js
