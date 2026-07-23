# Ruby semantic read-only family

Use this guide only for a selected Ruby semantic skill. Keep `_ruby-semantic`
beside the consumer in the external on-demand library. Ruby 3.3+, Bundler 2.6+,
Prism, RBS, project-owned `sig/**/*.rbs`, and native test/smoke commands are
required.

Set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and run the matching command:

- `find-dormant`: `python3 -I -S "$SKILL_ROOT/scripts/detect_ruby_dormant.py" --project-root "$PWD" --target lib --output-dir reports/find-dormant/ruby`
- `find-implicit-state`: `python3 -I -S "$SKILL_ROOT/scripts/detect_ruby_state.py" --project-root "$PWD" --target lib --output-dir reports/find-implicit-state/ruby`
- `find-incomplete-sweep`: `python3 -I -S "$SKILL_ROOT/scripts/detect_ruby_incomplete_sweep.py" --project-root "$PWD" --target lib --output-dir reports/find-incomplete-sweep/ruby`
- `find-semantic-duplication`: `python3 -I -S "$SKILL_ROOT/scripts/detect_ruby_semantic.py" --project-root "$PWD" --target lib --output-dir reports/semantic-duplication/ruby`
- `rename-concept`: `python3 -I -S "$SKILL_ROOT/scripts/assess_ruby_rename.py" "${OLD_CONCEPT:?}" "${NEW_CONCEPT:?}" --project-root "$PWD" --target lib --output reports/rename-concept/ruby/assessment.json`

Pass the host's `--test` and `--smoke` paths; state and duplication promotion
also require current hash-bound verdicts. RBS is the declared semantic
authority, while Prism supplies spans and explicit dynamic boundaries only.
Dynamic dispatch, reopening, callbacks, metaprogramming, Rails/Zeitwerk,
external consumers, behavioral equivalence, deletion, mutation, and refactor
safety remain unresolved. Projects without authored RBS return partial.
