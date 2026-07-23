<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/_php-semantic/php_semantic_facts.php';

function php_rename_normalize(string $value): string
{
    $value = preg_replace('/(?<=[a-z0-9])(?=[A-Z])/', '-', $value) ?? $value;
    return strtolower(preg_replace('/[^A-Za-z0-9]+/', '', $value) ?? '');
}

function php_rename_matches(string $fqcn, string $concept): bool
{
    $name = substr($fqcn, strrpos($fqcn, '\\') + 1);
    return php_rename_normalize($name) === php_rename_normalize($concept);
}

function php_rename_report(array $payload): string
{
    $evidence = $payload['php_identifier_evidence'];
    $lines = ['# PHP concept-rename assessment', '', "Verdict: **{$payload['verdict']}**", "Semantic identity status: `{$evidence['status']}`", '', '## Resolved identifier evidence', ''];
    foreach ($evidence['occurrences'] as $occurrence) {
        $lines[] = "- `{$occurrence['file']}:{$occurrence['line']}` — `{$occurrence['symbol']}` (`{$occurrence['classification']}`)";
    }
    if ($evidence['occurrences'] === []) {
        $lines[] = 'None.';
    }
    $lines[] = '';
    $lines[] = '## Boundaries';
    $lines[] = '';
    foreach ($evidence['boundaries'] as $boundary) {
        $lines[] = '- ' . $boundary;
    }
    $lines[] = '';
    return implode("\n", $lines);
}

try {
    $options = ppl_cli($argv, ['project-root', 'target', 'old', 'new', 'output'], [
        'php' => 'php', 'composer' => 'composer', 'minimum-php' => '8.1.0', 'minimum-composer' => '2.2.0',
    ]);
    $root = ppl_project_root($options['project-root']);
    $target = ppl_inside_path($root, $options['target'], 'target');
    $output = ppl_inside_path($root, $options['output'], 'output');
    $allowed = $root . '/reports/rename-concept';
    if (!ppl_is_inside($allowed, $output) || $output === $allowed) {
        throw new InvalidArgumentException('output must stay beneath reports/rename-concept');
    }
    ppl_assert_output($root, $output);
    ppl_clear_artifacts([$output, dirname($output) . '/report.md', dirname($output) . '/facts.json']);
    $facts = pse_collect($root, $target, $options['php'], $options['composer'], $options['minimum-php'], $options['minimum-composer']);
    $oldSymbols = [];
    $newSymbols = [];
    $declarations = ['old' => [], 'new' => []];
    $occurrences = [];
    if ($facts['status'] === 'complete') {
        foreach ($facts['classes'] as $class) {
            if (php_rename_matches($class['fqcn'], $options['old'])) {
                $oldSymbols[$class['fqcn']] = true;
            }
            if (php_rename_matches($class['fqcn'], $options['new'])) {
                $newSymbols[$class['fqcn']] = true;
            }
        }
        foreach ($facts['classes'] as $class) {
            foreach (['old' => $oldSymbols, 'new' => $newSymbols] as $side => $symbols) {
                if (isset($symbols[$class['fqcn']])) {
                    $declarations[$side][] = ['file' => $class['file'], 'line' => $class['line'], 'symbol' => $class['fqcn'], 'kind' => $class['kind']];
                    $occurrences[] = ['file' => $class['file'], 'line' => $class['line'], 'symbol' => $class['fqcn'], 'classification' => $side . '_concept_symbol'];
                }
            }
            foreach ($class['methods'] as $method) {
                foreach ($method['parameters'] as $parameter) {
                    foreach (['old' => $oldSymbols, 'new' => $newSymbols] as $side => $symbols) {
                        if (is_string($parameter['type']) && isset($symbols[$parameter['type']])) {
                            $occurrences[] = ['file' => $method['file'], 'line' => $method['line'], 'symbol' => $parameter['type'], 'classification' => $side . '_concept_symbol'];
                        }
                    }
                }
                foreach (['old' => $oldSymbols, 'new' => $newSymbols] as $side => $symbols) {
                    if (is_string($method['return_type']) && isset($symbols[$method['return_type']])) {
                        $occurrences[] = ['file' => $method['file'], 'line' => $method['line'], 'symbol' => $method['return_type'], 'classification' => $side . '_concept_symbol'];
                    }
                }
            }
            foreach ($class['new_expressions'] as $expression) {
                foreach (['old' => $oldSymbols, 'new' => $newSymbols] as $side => $symbols) {
                    if (($expression['resolution'] ?? null) === 'composer-psr4' && is_string($expression['class']) && isset($symbols[$expression['class']])) {
                        $occurrences[] = ['file' => $expression['file'], 'line' => $expression['line'], 'symbol' => $expression['class'], 'classification' => $side . '_concept_symbol'];
                    }
                }
            }
        }
    }
    usort($occurrences, fn (array $a, array $b): int => [$a['file'], $a['line'], $a['symbol']] <=> [$b['file'], $b['line'], $b['symbol']]);
    $status = $facts['status'] === 'complete' ? 'resolved' : 'unavailable';
    $oldUses = array_values(array_filter($occurrences, fn (array $row): bool => $row['classification'] === 'old_concept_symbol'));
    $verdict = $status !== 'resolved'
        ? 'INCONCLUSIVE'
        : ($oldUses === [] ? 'IDENTIFIER_SWEEP_CLEAR_REQUIRES_HUMAN_PROSE_REVIEW' : 'HALF-APPLIED / INCOMPLETE');
    $boundaries = [
        'Only Composer PSR-4 class identity, direct typed parameters/returns, and direct `new` references are resolved.',
        'Strings, comments, array keys, dynamic class names, class_alias, reflection, framework containers, inheritance, and external consumers remain unresolved.',
    ];
    foreach ($facts['boundaries'] as $boundary) {
        $boundaries[] = ($boundary['file'] ?? 'project') . ': ' . $boundary['kind'];
    }
    $payload = [
        'schema_version' => 1, 'language' => 'php', 'old' => $options['old'], 'new' => $options['new'], 'verdict' => $verdict,
        'php_identifier_evidence' => [
            'status' => $status, 'analyzer' => PSE_ANALYZER, 'project_identity' => $facts['project_identity'],
            'declarations' => $declarations, 'occurrences' => $occurrences, 'boundaries' => $boundaries,
            'source_manifest_sha256' => $facts['source_manifest_sha256'],
        ],
        'open_items' => $status === 'resolved'
            ? ['Human review must inspect unresolved prose/runtime/framework references before a rename is considered complete.']
            : ['PHP semantic evidence is unavailable or incomplete; do not make a completeness claim.'],
    ];
    ppl_atomic_json($output, $payload);
    ppl_atomic_text(dirname($output) . '/report.md', php_rename_report($payload));
    ppl_atomic_json(dirname($output) . '/facts.json', $facts);
    exit($facts['status'] === 'failed' ? 1 : ($facts['status'] === 'partial' ? 2 : 0));
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
