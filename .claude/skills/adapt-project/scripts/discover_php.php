<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/_php-project-lexical/php_project_lexical.php';

try {
    $options = ppl_cli(
        $argv,
        ['project-root', 'target', 'output-dir'],
        ['php' => 'php', 'composer' => 'composer', 'minimum-php' => '8.1.0', 'minimum-composer' => '2.2.0'],
    );
    $root = ppl_project_root($options['project-root']);
    $target = ppl_inside_path($root, $options['target'], 'target');
    $output = ppl_inside_path($root, $options['output-dir'], 'output directory');
    ppl_assert_output($root, $output);
    $artifacts = [
        $output . '/adapter.yml',
        $output . '/adapter.json',
        $output . '/report.md',
        $output . '/evidence.json',
    ];
    ppl_clear_artifacts($artifacts);
    $snapshot = ppl_collect_snapshot(
        $root,
        $target,
        $options['php'],
        $options['composer'],
        $options['minimum-php'],
        $options['minimum-composer'],
    );
    if (!ppl_sources_preserved($snapshot)) {
        $snapshot['status'] = 'failed';
        $snapshot['errors'][] = 'unexpected-source-mutation';
    }
    $analysis = ppl_public_snapshot($snapshot);
    $authored = array_values(array_filter(
        $snapshot['inventory'],
        fn (array $row): bool => $row['role'] === 'eligible',
    ));
    $count = $snapshot['status'] === 'failed' ? 0 : count($authored);
    $manifest = $snapshot['composer_manifest'];
    $adapter = [
        'schema_version' => 1,
        'status' => $snapshot['status'],
        'analysis' => ['php' => $analysis],
        'project' => ['name' => basename($root), 'root' => $root],
        'stack' => [
            'frameworks' => [],
            'languages' => $count > 0 ? ['php'] : [],
            'package_managers' => $manifest === null ? [] : ['composer'],
        ],
        'composer' => ['psr4' => $manifest['psr4'] ?? []],
        'commands' => [
            'validate' => ['composer validate --no-check-publish --no-interaction'],
            'lint' => is_file($root . '/tests/lint.php') ? ['php tests/lint.php'] : ['php -l <authored-file.php>'],
            'test' => is_file($root . '/tests/smoke.php') ? ['php tests/smoke.php'] : [],
        ],
        'source_roots' => [[
            'path' => ppl_relative($root, $target),
            'php_files' => $count,
            'source_languages' => $count > 0 ? ['php'] : [],
        ]],
        'standardization' => ['cautions' => [
            'Observed Composer/PHP layout is objective evidence, not proof that it is a healthy standard.',
        ]],
        'open_questions' => ['Which observed PHP patterns are healthy enough to teach future agents?'],
    ];
    $serialized = json_encode($adapter, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n";
    ppl_atomic_text($artifacts[0], $serialized);
    ppl_atomic_text($artifacts[1], $serialized);
    $outcome = $snapshot['status'] === 'complete' ? 'complete' : 'incomplete';
    ppl_atomic_text(
        $artifacts[2],
        "# Adapt Project Report — PHP\n\n"
        . "**Status:** `{$snapshot['status']}`\n\n"
        . "**Outcome:** `{$outcome}`\n\n"
        . "Authored PHP files: {$count}. Composer facts are project-declared and source-preserving. "
        . "No framework behavior is inferred.\n",
    );
    ppl_atomic_json($artifacts[3], [
        'skill' => 'adapt-project',
        'status' => $snapshot['status'],
        'evidence' => ['adapter' => 'adapter.yml', 'report' => 'report.md'],
    ]);
    echo $output, "\n";
    exit(ppl_terminal_code($snapshot));
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
