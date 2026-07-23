# PHP syntax family

Use this guide only for a selected PHP syntax skill. Keep this directory beside
the consumer in the external on-demand library; a consumer-only ambient install
is incomplete. PHP 8.1+ and Composer 2.2+ are required.

Set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and run the matching command:

- `audit-decisions`: `python3 -I -S "$SKILL_ROOT/scripts/audit_php.py" --project-root "$PWD" --target . --output-dir "$PWD/reports/audit-decisions/php"`
- `find-complexity-hotspots`: `python3 -I -S "$SKILL_ROOT/scripts/run_php.py" --project-root "$PWD" --target src --output-dir "$PWD/reports/find-complexity-hotspots/php"`
- `find-omnibus`: `python3 -I -S "$SKILL_ROOT/scripts/run_php.py" --project-root "$PWD" --target src --output-dir "$PWD/reports/find-omnibus/php" --scout-dir "$PWD/reports/find-omnibus/php/scouts"`
- `find-standard-gaps`: `python3 -I -S "$SKILL_ROOT/scripts/scan_coverage_php.py" --project-root "$PWD" --target src --ideas "${PHP_STANDARDS:?}" --output-dir "$PWD/reports/find-standard-gaps/php"`

The provider owns token syntax, roles, native gates, fingerprints, and terminal
lifecycle. These outcomes do not establish symbol/callee identity, behavior,
runtime cost, exception flow, framework truth, equivalence, decomposition, or
refactor authority. Omnibus candidates require hash-bound human scout evidence.
