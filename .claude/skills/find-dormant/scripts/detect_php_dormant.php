<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/_php-semantic/php_semantic_facts.php';

function php_dormant_report(array $payload): string
{
    $lines = [
        '# PHP dormant-code review', '',
        "Status: **{$payload['status']}**. Composer-identity and direct final-class \$this call facts only.", '',
        '## Never safe deletion from static evidence', '',
        'Every candidate requires runtime-aware human review. Reflection, dynamic member names, class aliases, framework callbacks, containers, traits, inheritance, external consumers, and generated code are not reachability facts.', '',
        '## Review-required candidates', '',
    ];
    if ($payload['candidates'] === []) {
        $lines[] = 'None.';
    }
    foreach ($payload['candidates'] as $candidate) {
        $lines[] = "- `{$candidate['file']}:{$candidate['line']}` — `{$candidate['fqmn']}`; zero direct resolved \$this calls.";
    }
    $lines[] = '';
    $lines[] = '## Uncertain boundaries';
    $lines[] = '';
    foreach ($payload['uncertain'] as $item) {
        $lines[] = "- `{$item['file']}:{$item['line']}` — {$item['reason']}";
    }
    if ($payload['uncertain'] === []) {
        $lines[] = 'None.';
    }
    $lines[] = '';
    return implode("\n", $lines);
}

try {
    $options = ppl_cli($argv, ['project-root', 'target', 'report-dir'], [
        'php' => 'php', 'composer' => 'composer', 'minimum-php' => '8.1.0', 'minimum-composer' => '2.2.0',
    ]);
    $root = ppl_project_root($options['project-root']);
    $target = ppl_inside_path($root, $options['target'], 'target');
    $report = ppl_inside_path($root, $options['report-dir'], 'report directory');
    $allowed = $root . '/reports/find-dormant';
    if (!ppl_is_inside($allowed, $report) || $report === $allowed) {
        throw new InvalidArgumentException('report directory must stay beneath reports/find-dormant');
    }
    ppl_assert_output($root, $report);
    $artifacts = [$report . '/findings.json', $report . '/report.md', $report . '/facts.json'];
    ppl_clear_artifacts($artifacts);
    $facts = pse_collect($root, $target, $options['php'], $options['composer'], $options['minimum-php'], $options['minimum-composer']);
    $candidates = [];
    $uncertain = [];
    if ($facts['status'] === 'complete') {
        foreach ($facts['classes'] as $class) {
            $directCalls = [];
            $classHasDynamicDispatch = false;
            foreach ($class['boundaries'] as $boundary) {
                if (($boundary['kind'] ?? null) === 'dynamic_member_dispatch') {
                    $classHasDynamicDispatch = true;
                }
            }
            foreach ($class['methods'] as $method) {
                foreach ($method['direct_calls'] as $call) {
                    $directCalls[strtolower($call['name'])] = true;
                }
            }
            foreach ($class['methods'] as $method) {
                if (!$class['final'] || $method['visibility'] !== 'private' || strtolower($method['name']) === '__construct') {
                    continue;
                }
                if ($method['dynamic_boundary'] || $classHasDynamicDispatch) {
                    $uncertain[] = ['file' => $method['file'], 'line' => $method['line'], 'fqmn' => $method['fqmn'], 'reason' => 'class has dynamic member dispatch'];
                    continue;
                }
                if (isset($directCalls[strtolower($method['name'])])) {
                    continue;
                }
                $id = 'PHP-DORMANT-' . strtoupper(substr(ppl_hash($method['fqmn'] . "\0" . $method['source_sha256']), 0, 12));
                $candidates[] = [
                    'finding_id' => $id, 'file' => $method['file'], 'line' => $method['line'], 'fqmn' => $method['fqmn'],
                    'resolved_direct_references' => 0, 'verdict' => 'review_required', 'recommendation' => 'human_review_only',
                    'source_sha256' => $method['source_sha256'],
                ];
            }
        }
    }
    foreach ($facts['boundaries'] as $boundary) {
        $uncertain[] = ['file' => $boundary['file'], 'line' => $boundary['line'] ?? 0, 'reason' => $boundary['kind'] . ': ' . ($boundary['detail'] ?? '')];
    }
    usort($candidates, fn (array $a, array $b): int => [$a['file'], $a['line']] <=> [$b['file'], $b['line']]);
    $payload = [
        'schema_version' => 1, 'language' => 'php', 'analyzer' => PSE_ANALYZER, 'status' => $facts['status'],
        'target' => $facts['target'], 'read_only' => true, 'candidates' => $candidates, 'uncertain' => $uncertain,
        'summary' => ['review_required' => count($candidates), 'uncertain' => count($uncertain), 'certain_delete' => 0],
        'project_identity' => $facts['project_identity'], 'semantic_tool' => $facts['semantic_tool'],
        'source_manifest_sha256' => $facts['source_manifest_sha256'], 'limits' => $facts['limits'],
    ];
    ppl_atomic_json($artifacts[0], $payload);
    ppl_atomic_text($artifacts[1], php_dormant_report($payload));
    ppl_atomic_json($artifacts[2], $facts);
    exit(ppl_terminal_code(['status' => $facts['status']]));
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
