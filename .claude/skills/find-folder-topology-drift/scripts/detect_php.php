<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/_php-project-lexical/php_project_lexical.php';

function php_topology_prefix(string $stem): ?string
{
    if (preg_match('/\A([A-Za-z][A-Za-z0-9]*?)[_-]/', $stem, $match) === 1) {
        return $match[1];
    }
    if (preg_match('/\A([A-Z][a-z0-9]+)(?=[A-Z])/', $stem, $match) === 1) {
        return $match[1];
    }
    return null;
}

try {
    $options = ppl_cli(
        $argv,
        ['project-root', 'target', 'output'],
        [
            'php' => 'php',
            'composer' => 'composer',
            'minimum-php' => '8.1.0',
            'minimum-composer' => '2.2.0',
            'min-cluster-size' => '3',
        ],
    );
    if (filter_var($options['min-cluster-size'], FILTER_VALIDATE_INT) === false || (int) $options['min-cluster-size'] < 2) {
        throw new InvalidArgumentException('--min-cluster-size must be an integer >= 2');
    }
    $minimum = (int) $options['min-cluster-size'];
    $root = ppl_project_root($options['project-root']);
    $target = ppl_inside_path($root, $options['target'], 'target');
    $output = ppl_inside_path($root, $options['output'], 'output');
    ppl_assert_output($root, $output);
    $report = dirname($output) . '/report.md';
    $finalJson = dirname($output) . '/findings.json';
    $scanJson = dirname($output) . '/scan.json';
    ppl_clear_artifacts([$output, $report, $finalJson, $scanJson]);
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
    $groups = [];
    if ($snapshot['status'] !== 'failed') {
        foreach ($snapshot['inventory'] as $row) {
            if ($row['role'] !== 'eligible') {
                continue;
            }
            $stem = pathinfo($row['file'], PATHINFO_FILENAME);
            $prefix = php_topology_prefix($stem);
            if ($prefix === null || strlen($prefix) < 2) {
                continue;
            }
            $directory = str_replace('\\', '/', dirname($row['file']));
            $groups[$directory . "\0" . $prefix][] = $row['file'];
        }
    }
    $findings = [];
    foreach ($groups as $key => $files) {
        if (count($files) < $minimum) {
            continue;
        }
        [$directory, $prefix] = explode("\0", $key, 2);
        sort($files);
        $findings[] = [
            'pattern' => 'flat_prefix_cluster',
            'language' => 'php',
            'file' => $directory,
            'prefix' => $prefix,
            'count' => count($files),
            'files' => $files,
            'evidence_sha256' => ppl_hash(implode("\n", $files)),
            'recommendation' => 'Human triage only; no Composer/import-safe move is implied.',
        ];
    }
    usort($findings, fn (array $left, array $right): int => [$left['file'], $left['prefix']] <=> [$right['file'], $right['prefix']]);
    $analysis = ppl_public_snapshot($snapshot);
    $outcome = $snapshot['status'] === 'failed'
        ? 'failed'
        : ($snapshot['status'] === 'partial'
            ? 'incomplete'
            : ($findings === [] ? 'clean' : 'drift-found'));
    $jsonl = implode('', array_map(
        fn (array $item): string => json_encode($item, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n",
        $findings,
    ));
    ppl_atomic_text($output, $jsonl);
    ppl_atomic_json($scanJson, $analysis);
    ppl_atomic_json($finalJson, [
        'schema_version' => 1,
        'status' => $snapshot['status'],
        'outcome' => $outcome,
        'scan_meta' => [
            'language' => 'php',
            'target' => ppl_relative($root, $target),
            'patterns' => array_values(array_unique(array_column($findings, 'pattern'))),
        ],
        'analysis' => ['php' => $analysis],
        'detections_sha256' => ppl_hash($jsonl),
        'findings' => $findings,
    ]);
    $lines = [
        '# Folder-topology drift audit — PHP',
        '',
        "**Status:** `{$snapshot['status']}`",
        "**Outcome:** `{$outcome}`",
        '**Target:** `' . ppl_relative($root, $target) . '`',
        '',
    ];
    if ($findings !== []) {
        foreach ($findings as $finding) {
            $lines[] = "- `{$finding['file']}` prefix `{$finding['prefix']}` — {$finding['count']} files";
        }
        $lines[] = '';
        $lines[] = 'Findings are lexical naming evidence only; do not move files automatically.';
    } else {
        $lines[] = $snapshot['status'] === 'complete'
            ? 'No PHP direct-sibling filename cluster met the threshold.'
            : 'Analysis is incomplete; no clean topology conclusion is available.';
    }
    ppl_atomic_text($report, implode("\n", $lines) . "\n");
    exit(ppl_terminal_code($snapshot));
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
