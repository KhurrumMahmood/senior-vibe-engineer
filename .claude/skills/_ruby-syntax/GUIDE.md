# Ruby syntax family

Use this guide only for a selected Ruby syntax skill. Keep this directory beside
the consumer in the external on-demand library; a consumer-only ambient install
is incomplete. Ruby 3.3+, Bundler 2.6+, and bundled/default Prism are required.

Set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and run the matching command:

- `audit-decisions`: `python3 -I -S "$SKILL_ROOT/scripts/audit_ruby.py" --project-root "$PWD" --target . --output-dir "$PWD/reports/audit-decisions/ruby"`
- `find-complexity-hotspots`: `python3 -I -S "$SKILL_ROOT/scripts/run_ruby.py" --project-root "$PWD" --target lib --output-dir "$PWD/reports/find-complexity-hotspots/ruby"`
- `find-omnibus`: `python3 -I -S "$SKILL_ROOT/scripts/run_ruby.py" --project-root "$PWD" --target lib --output-dir "$PWD/reports/find-omnibus/ruby" --scout-dir "$PWD/reports/find-omnibus/ruby/scouts"`
- `find-standard-gaps`: `python3 -I -S "$SKILL_ROOT/scripts/scan_coverage_ruby.py" --project-root "$PWD" --target lib --ideas "${RUBY_STANDARDS:?}" --output-dir "$PWD/reports/find-standard-gaps/ruby"`

Complete runs exit 0, partial evidence exits 2, and failed runs exit 1. Prism
syntax does not establish runtime identity/dispatch/loading, metaprogramming,
Rails/Zeitwerk behavior, equivalence, decomposition, or refactor authority.
Omnibus candidates require separate human scout evidence.
