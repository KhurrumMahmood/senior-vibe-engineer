# Ruby accepted-evidence proposals and guard

Use this guide only after the matching Ruby artifact has a current hash-bound
human acceptance. Keep `_ruby-semantic` beside the selected consumer in the
external library and run the copied Python adapter with isolated/no-site
Python.

- `extract-enum`: run `collect_ruby_state.py --project-root "$PWD" --evidence <state-findings> --facts <semantic-facts> --acceptance <accepted-state-review> --output-dir "$PWD/reports/extract-enum/ruby/run"`.
- `prevent-regression`: run `generate_ruby_state_guard.py --project-root "$PWD" --targets <enum-targets> --accepted-review <guard-review> --output-dir "$PWD/reports/prevent-regression/ruby/run" --ruby <ruby>`.
- `propose-boundary`: run `propose_ruby.py` with the accepted omnibus finding.
- `propose-folder-reorganization`: run `propose_ruby.py` with the accepted lexical topology cluster and convention.
- `unify-shadows`: run `propose_ruby.py` with the accepted duplication artifact, its RBS fact pack, and the accepted consolidation decision.

All branches are read-only against production source and never rerun detection.
RBS is contract evidence, not runtime proof. Rails/ActiveRecord, Zeitwerk,
dynamic loading/dispatch, reopening, refinements, metaprogramming, external
consumers, and behavioral equivalence remain explicit review boundaries.
