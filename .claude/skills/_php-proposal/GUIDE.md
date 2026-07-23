# PHP accepted-evidence proposals and guard

Use this guide only after the matching PHP producer artifact has a current
SHA-bound acceptance file. Keep `_php-proposal` beside the selected consumer
in the external library. Set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and
pass the project-local PHP and Composer executables explicitly.

- `extract-enum`: run `collect_php_state.py --project-root "$PWD" --evidence <state-findings> --acceptance <accepted-state-review> --output-dir "$PWD/reports/extract-enum/php/run" --php <php> --composer <composer>`.
- `prevent-regression`: run `generate_php_state_guard.py` with the accepted enum proposal, then `verify_php_state_guard.py --project-root "$PWD" --stage <stage-dir> --php <php> --composer <composer>`.
- `propose-boundary`: run `propose_php.py` with the accepted omnibus selection and a nested `reports/propose-boundary/` output directory.
- `propose-folder-reorganization`: run `propose_php.py` with the accepted topology cluster/convention and a nested `reports/propose-folder-reorganization/` output directory.
- `unify-shadows`: run `propose_php.py` with the accepted A3 duplication review and a nested `reports/unify-shadows/` output directory.

The scripts validate current source and Composer identity, replay native checks
in disposable copies, and replace stale terminal artifacts. They never rerun
detection or edit production source. Dynamic/framework/external behavior,
runtime equivalence, enum safety, and refactor safety remain human-owned.
