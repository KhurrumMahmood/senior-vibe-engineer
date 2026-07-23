# Ruby project/lexical family

Use this guide only for a selected Ruby A1 skill. Keep this directory beside
the selected skill in the external on-demand library; a consumer-only ambient
install is incomplete.

The provider requires Ruby 3.3+ and Bundler 2.6+, uses bundled Prism plus
per-file `ruby -c`, runs frozen Bundler/native checks, records roles and source
hashes, and replaces stale artifacts. Complete runs exit 0, partial evidence
exits 2, and failed runs exit 1. Use `--ruby`, `--bundler`, `--test`, and
`--smoke` when the host needs explicit commands.

Set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and run the matching command:

- `adapt-project`: `python3 -I -S "$SKILL_ROOT/scripts/discover_ruby.py" --project-root "$PWD" --output-dir "$PWD/reports/adapt-project/ruby" .`
- `explain-code`: `python3 -I -S "$SKILL_ROOT/scripts/explain_ruby.py" --project-root "$PWD" --target lib --output "$PWD/reports/explanations/ruby.md"`
- `find-concept-divergence`: `python3 -I -S "$SKILL_ROOT/scripts/scan_ruby.py" --project-root "$PWD" --glossary "$PWD/.claude/contracts/concepts.yaml" --output "$PWD/reports/find-concept-divergence/ruby/findings.jsonl" --report "$PWD/reports/find-concept-divergence/ruby/report.md" lib`
- `find-duplication`: `python3 -I -S "$SKILL_ROOT/scripts/run_ruby.py" --project-root "$PWD" --target lib --output-dir "$PWD/reports/duplication/ruby"`
- `find-folder-topology-drift`: `python3 -I -S "$SKILL_ROOT/scripts/detect_ruby.py" --project-root "$PWD" --ruby-root lib --output "$PWD/reports/find-folder-topology-drift/ruby/detections.jsonl"`

These are bounded plain-Ruby/gem and Prism lexical outcomes. Dynamic loading,
dispatch, reopening, mixins, metaprogramming, Rails/Zeitwerk, runtime identity,
behavior, equivalence, and safe consolidation/moves remain unresolved.
