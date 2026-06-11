# Product workflow — find-contract-drift fixture

Host-authored scan scope for this fixture. The detector reads `## Targets` via
`workflow_targets` and `## Template roots` via `workflow_template_roots`
(`.claude/skills/_common/workflows.py`) instead of baked-in `/sites` defaults.

## Targets
- app/services/sites
- static/js/site-config-*.js
- templates/core/site_config_base.html

## Template roots
- templates/core
