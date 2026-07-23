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
        'collapsed' => $output . '/collapsed.json',
        'ranked' => $output . '/ranked.json',
        'triage' => $output . '/triage.md',
        'findings' => $output . '/findings.json',
        'scan' => $output . '/scan.json',
    ];
    ppl_clear_artifacts(array_values($artifacts));
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
        foreach (ppl_functions($snapshot) as $fact) {
            if (!$fact['has_body'] || $fact['line_count'] < 5 || $fact['body_sha256'] === null) {
                continue;
            }
            $groups[$fact['body_sha256']][] = $fact;
        }
    }
    $findings = [];
    foreach ($groups as $digest => $facts) {
        if (count($facts) < 2) {
            continue;
        }
        $sites = array_map(
            fn (array $fact): array => [
                'file' => $fact['file'],
                'symbol' => $fact['qualified_symbol'],
                'start_line' => $fact['span']['start']['line'],
                'end_line' => $fact['span']['end']['line'],
                'span' => $fact['span'],
                'source_sha256' => $fact['source_sha256'],
                'spelling_sha256' => $fact['spelling_sha256'],
            ],
            $facts,
        );
        $multiplicity = count($sites);
        $priority = round($multiplicity * 1.5, 2);
        $findings[] = [
            'finding_id' => 'PHP-DUP-' . strtoupper(substr($digest, 0, 12)),
            'detector' => 'php-exact-token-normalized-function-body',
            'shape_hint' => 'cross_file_clone',
            'multiplicity' => $multiplicity,
            'shared_lines_min' => min(array_column($facts, 'line_count')),
            'shared_lines_max' => max(array_column($facts, 'line_count')),
            'normalized_body_sha256' => $digest,
            'sites' => $sites,
            'rank_meta' => [
                'priority' => $priority,
                'priority_tier' => $priority >= 5 ? 'P1' : 'P2',
                'divergence_risk' => 1.0,
                'bug_blast_radius' => 1.5,
                'effective_multiplicity' => $multiplicity,
                'effort_hint' => count(array_unique(array_column($sites, 'file'))) > 1 ? 'medium' : 'low',
            ],
        ];
    }
    usort($findings, fn (array $left, array $right): int => $right['rank_meta']['priority'] <=> $left['rank_meta']['priority']);
    $analysis = ppl_public_snapshot($snapshot);
    $scanMeta = [
        'language' => 'php',
        'target' => ppl_relative($root, $target),
        'project_root' => $root,
        'status' => $snapshot['status'],
        'analyzer' => 'php-exact-token-normalized-function-body',
        'analysis' => $analysis,
        'ast_finding_count' => count($findings),
    ];
    $intermediate = ['schema_version' => 1, 'scan_meta' => $scanMeta, 'findings' => $findings];
    ppl_atomic_json($artifacts['collapsed'], $intermediate);
    ppl_atomic_json($artifacts['ranked'], $intermediate);
    ppl_atomic_json($artifacts['findings'], [
        'scan_meta' => $scanMeta,
        'findings' => $findings,
        'dormant_candidates' => [],
    ]);
    ppl_atomic_json($artifacts['scan'], $analysis);
    $lines = [
        '# Duplication triage — PHP',
        '',
        '**Target:** `' . ppl_relative($root, $target) . '`',
        "**Scan status:** `{$snapshot['status']}`",
        '',
        '> **PHP v1 boundary:** This is exact token-normalized function-body clone evidence. '
            . 'Do not consolidate automatically; behavior, callers, ownership, and dynamic dispatch require human review.',
        '',
        '## Priority clusters (' . count($findings) . ')',
        '',
    ];
    foreach ($findings as $finding) {
        $lines[] = "### `{$finding['finding_id']}`";
        foreach ($finding['sites'] as $site) {
            $lines[] = "- `{$site['file']}::{$site['symbol']}` ({$site['start_line']}-{$site['end_line']})";
        }
        $lines[] = '';
    }
    if ($findings === []) {
        $lines[] = $snapshot['status'] === 'complete'
            ? 'No exact PHP token clone evidence found within the complete snapshot.'
            : 'Analysis incomplete; no clean conclusion is available.';
    }
    ppl_atomic_text($artifacts['triage'], implode("\n", $lines) . "\n");
    exit(ppl_terminal_code($snapshot));
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
