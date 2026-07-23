# PHP semantic read-only family

Use this guide only for a selected PHP semantic skill. Keep `_php-semantic`
beside the consumer in the external on-demand library. PHP 8.1+, Composer 2.2+,
an exact PSR-4 mapping, and project-owned native checks are required.

Set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and run the matching command:

- `find-dormant`: `php "$SKILL_ROOT/scripts/detect_php_dormant.php" --project-root "$PWD" --target src --report-dir reports/find-dormant/php`
- `find-implicit-state`: `php "$SKILL_ROOT/scripts/detect_php_state.php" --project-root "$PWD" --target src --output-dir reports/implicit-state/php`
- `find-incomplete-sweep`: `php "$SKILL_ROOT/scripts/detect_php_incomplete_sweep.php" --project-root "$PWD" --target src --report-dir reports/find-incomplete-sweep/php`
- `find-semantic-duplication`: `php "$SKILL_ROOT/scripts/detect_php_semantic.php" --project-root "$PWD" --target src --report-dir reports/semantic-duplication/php`
- `rename-concept`: `php "$SKILL_ROOT/scripts/assess_php.php" --project-root "$PWD" --target src --old "${OLD_CONCEPT:?}" --new "${NEW_CONCEPT:?}" --output reports/rename-concept/php/assessment.json`

State and duplication findings require current hash-bound review files;
incomplete-sweep requires separate hash-bound triage. Composer identity supports
only direct declared relationships. Dynamic dispatch, reflection, frameworks,
external consumers, behavioral equivalence, deletion, mutation, and refactor
safety remain unresolved. A configured but unusable PHPStan/Psalm pair is a
visible partial result, not permission to fall back to token guesses.
