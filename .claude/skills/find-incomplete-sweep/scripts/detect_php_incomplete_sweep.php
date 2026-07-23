<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/_php-semantic/php_semantic_facts.php';

function php_sweep_git_time(string $root, array $site): array
{
    $result = ppl_process(['git', 'blame', '--line-porcelain', '-L', $site['line'] . ',' . $site['line'], '--', $site['file']], $root);
    if ($result['returncode'] !== 0) {
        return ['state' => 'failed', 'timestamp' => null];
    }
    if (preg_match('/^committer-time (\d+)$/m', $result['stdout'], $match) !== 1 || str_starts_with($result['stdout'], str_repeat('0', 40))) {
        return ['state' => 'insufficient', 'timestamp' => null];
    }
    return ['state' => 'available', 'timestamp' => (int) $match[1]];
}

function php_sweep_report(array $payload): string
{
    $lines = ['# PHP incomplete-sweep findings', '', "Status: **{$payload['status']}**. Composer-resolved direct named constructor calls only.", '', '## Gated IN — human verdict required', ''];
    foreach ($payload['findings'] as $finding) {
        $lines[] = "- `{$finding['class']}` missing `{$finding['parameter']}` at `{$finding['straggler']['file']}:{$finding['straggler']['line']}`; {$finding['present_count']}/{$finding['group_size']} later comparable calls include it.";
    }
    if ($payload['findings'] === []) {
        $lines[] = '_none_';
    }
    $lines[] = '';
    $lines[] = '## Deferred boundaries';
    $lines[] = '';
    foreach ($payload['deferred'] as $item) {
        $lines[] = "- `{$item['file']}:{$item['line']}` — {$item['reason']}";
    }
    if ($payload['deferred'] === []) {
        $lines[] = '_none_';
    }
    $lines[] = '';
    return implode("\n", $lines);
}

try {
    $options = ppl_cli($argv, ['project-root', 'target', 'report-dir'], [
        'php' => 'php', 'composer' => 'composer', 'minimum-php' => '8.1.0', 'minimum-composer' => '2.2.0',
        'min-callsites' => '4', 'majority-frac' => '0.75', 'min-present' => '3',
    ]);
    $root = ppl_project_root($options['project-root']);
    $target = ppl_inside_path($root, $options['target'], 'target');
    $report = ppl_inside_path($root, $options['report-dir'], 'report directory');
    $allowed = $root . '/reports/find-incomplete-sweep';
    if (!ppl_is_inside($allowed, $report) || $report === $allowed) {
        throw new InvalidArgumentException('report directory must stay beneath reports/find-incomplete-sweep');
    }
    ppl_assert_output($root, $report);
    $minCallsites = (int) $options['min-callsites'];
    $minPresent = (int) $options['min-present'];
    $majority = (float) $options['majority-frac'];
    if ($minCallsites < 4 || $minPresent < 3 || $majority < 0.75 || $majority > 1.0) {
        throw new InvalidArgumentException('sweep thresholds must preserve the conservative 4/3/75% floor');
    }
    $artifacts = [$report . '/manifest.json', $report . '/findings.md', $report . '/facts.json'];
    ppl_clear_artifacts($artifacts);
    $facts = pse_collect($root, $target, $options['php'], $options['composer'], $options['minimum-php'], $options['minimum-composer']);
    $constructors = [];
    $calls = [];
    foreach ($facts['classes'] as $class) {
        foreach ($class['methods'] as $method) {
            if (strtolower($method['name']) === '__construct') {
                $constructors[$class['fqcn']] = $method['parameters'];
            }
        }
        foreach ($class['new_expressions'] as $expression) {
            if (($expression['resolution'] ?? null) === 'composer-psr4' && $expression['named_arguments'] !== []) {
                $calls[$expression['class']][] = $expression;
            }
        }
    }
    $findings = [];
    $deferred = [];
    $gitState = 'not-required';
    if ($facts['status'] === 'complete') {
        foreach ($calls as $class => $sites) {
            if (count($sites) < $minCallsites || !isset($constructors[$class])) {
                continue;
            }
            foreach ($constructors[$class] as $parameter) {
                if (!$parameter['required']) {
                    continue;
                }
                $present = array_values(array_filter($sites, fn (array $site): bool => in_array($parameter['name'], $site['named_arguments'], true)));
                $missing = array_values(array_filter($sites, fn (array $site): bool => !in_array($parameter['name'], $site['named_arguments'], true)));
                if (count($present) < $minPresent || count($missing) !== 1 || count($present) / count($sites) < $majority) {
                    continue;
                }
                $times = array_map(fn (array $site): array => php_sweep_git_time($root, $site), [...$present, $missing[0]]);
                $states = array_column($times, 'state');
                if (count(array_unique($states)) !== 1 || $states[0] !== 'available') {
                    $gitState = in_array('failed', $states, true) ? 'failed' : 'insufficient';
                    $deferred[] = ['file' => $missing[0]['file'], 'line' => $missing[0]['line'], 'reason' => $gitState . '_git_evidence', 'detail' => $class . ':' . $parameter['name']];
                    continue;
                }
                $presentTimes = array_slice(array_column($times, 'timestamp'), 0, count($present));
                $stragglerTime = $times[count($times) - 1]['timestamp'];
                if (min($presentTimes) <= $stragglerTime) {
                    $deferred[] = ['file' => $missing[0]['file'], 'line' => $missing[0]['line'], 'reason' => 'nonmonotonic_git_trajectory', 'detail' => $class . ':' . $parameter['name']];
                    continue;
                }
                $candidate = [
                    'class' => $class, 'parameter' => $parameter['name'], 'parameter_type' => $parameter['type'],
                    'group_size' => count($sites), 'present_count' => count($present), 'majority_frac' => round(count($present) / count($sites), 3),
                    'straggler' => $missing[0], 'present_sites' => $present, 'trajectory' => 'all present direct calls are newer than the omitted call',
                    'source_manifest_sha256' => $facts['source_manifest_sha256'], 'human_verdict' => 'required',
                ];
                $candidate['candidate_id'] = 'PHP-SWEEP-' . strtoupper(substr(ppl_hash(json_encode($candidate, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR)), 0, 12));
                $candidate['candidate_sha256'] = ppl_hash(json_encode($candidate, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));
                $findings[] = $candidate;
            }
        }
    }
    if ($facts['status'] === 'complete' && $gitState !== 'not-required') {
        $facts['status'] = 'partial';
        $facts['failure_kind'] = $gitState . '_git_evidence';
    }
    $payload = [
        'schema_version' => 1, 'language' => 'php', 'band' => 'php-composer-named-constructor-omission', 'analyzer' => PSE_ANALYZER,
        'status' => $facts['status'], 'failure_kind' => $facts['failure_kind'], 'read_only' => true, 'target' => $facts['target'],
        'findings' => $findings, 'gated_out' => [], 'deferred' => $deferred,
        'summary' => ['gated_in' => count($findings), 'gated_out' => 0, 'deferred' => count($deferred)],
        'project_resolution' => ['composer_identity' => $facts['project_identity'], 'git_evidence' => $gitState],
        'semantic_tool' => $facts['semantic_tool'], 'source_manifest_sha256' => $facts['source_manifest_sha256'], 'limits' => $facts['limits'],
    ];
    ppl_atomic_json($artifacts[0], $payload);
    ppl_atomic_text($artifacts[1], php_sweep_report($payload));
    ppl_atomic_json($artifacts[2], $facts);
    exit(ppl_terminal_code(['status' => $payload['status']]));
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
