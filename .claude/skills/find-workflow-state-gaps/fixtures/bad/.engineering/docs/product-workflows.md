# Product workflow — find-workflow-state-gaps fixture

Host-authored scan scope for this fixture. The detector reads these targets via
`.claude/skills/_common/workflows.py` (`workflow_targets`) instead of any
baked-in `/sites` path list, so the fixture doubles as a dogfood of the
host-authored scope mechanism.

## Targets
- app/pages/sites
- static/js/site-config-*.js
