# PHP project/lexical family

Use this guide only for a selected PHP A1 skill. Keep this directory beside the
selected skill in the external on-demand library; a consumer-only ambient
install is incomplete.

The provider requires PHP 8.1+ and Composer 2.2+. It runs Composer validation,
per-file `php -l`, native token parsing, role inventory, lifecycle replacement,
and source-preservation checks. Defaults are `php` and `composer`; override
with `--php`, `--composer`, `--minimum-php`, and `--minimum-composer`.

Set `SKILL_ROOT=.agents/skills/on-demand/<skill>` and run the matching command:

- `adapt-project`: `php "$SKILL_ROOT/scripts/discover_php.php" --project-root "$PWD" --target src --output-dir "$PWD/reports/adapt-project/php"`
- `explain-code`: `php "$SKILL_ROOT/scripts/explain_php.php" --project-root "$PWD" --target src --output "$PWD/reports/explanations/php.md"`
- `find-concept-divergence`: `php "$SKILL_ROOT/scripts/scan_php.php" --project-root "$PWD" --target src --glossary "$PWD/.claude/contracts/concepts.yaml" --output "$PWD/reports/find-concept-divergence/php/findings.jsonl" --report "$PWD/reports/find-concept-divergence/php/report.md"`
- `find-duplication`: `php "$SKILL_ROOT/scripts/run_php.php" --project-root "$PWD" --target src --output-dir "$PWD/reports/duplication/php"`
- `find-folder-topology-drift`: `php "$SKILL_ROOT/scripts/detect_php.php" --project-root "$PWD" --target src --output "$PWD/reports/find-folder-topology-drift/php/detections.jsonl"`

These are bounded lexical/project outcomes. They do not establish resolved
symbol identity, types, calls, behavior, framework conventions, equivalence,
or safe consolidation/moves. Treat partial or failed tool/project evidence as
non-clean.
