<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/_php-semantic/php_semantic_facts.php';

const PHP_STATE_REVIEW_SCHEMA = 'php-implicit-state-review-v1';
const PHP_STATE_VERDICTS = ['extract_enum_candidate', 'enum_already_used', 'legacy_allow_list'];

/** @return array<string,array<string,mixed>> */
function php_state_reviews(string $root, ?string $supplied): array
{
    if ($supplied === null) {
        return [];
    }
    $directory = ppl_inside_path($root, $supplied, 'reviews directory');
    if (!is_dir($directory) || is_link($directory) || ppl_has_symlink_component($root, $directory)) {
        throw new InvalidArgumentException('reviews directory must be a regular non-symlink directory');
    }
    $rows = [];
    foreach (glob($directory . '/*.json') ?: [] as $path) {
        if (is_link($path)) {
            throw new InvalidArgumentException('review files must not be symbolic links');
        }
        $item = json_decode((string) file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
        if (!is_array($item) || ($item['schema_version'] ?? null) !== PHP_STATE_REVIEW_SCHEMA
            || !is_string($item['candidate_id'] ?? null) || !is_string($item['candidate_sha256'] ?? null)
            || !in_array($item['human_verdict'] ?? null, PHP_STATE_VERDICTS, true)) {
            throw new InvalidArgumentException('review has an invalid PHP implicit-state schema');
        }
        $rows[$item['candidate_id']] = $item;
    }
    return $rows;
}

function php_state_report(array $payload): string
{
    $lines = ['# PHP implicit-state review', '', '> Detection only. A string field is not proof that the domain is closed.', '', "Status: `{$payload['status']}`", "Raw candidates: `{$payload['summary']['raw_candidates']}`", "Human-reviewed findings: `{$payload['summary']['accepted']}`", '', '## Reviewed candidates', ''];
    foreach ($payload['findings'] as $finding) {
        $lines[] = "- `{$finding['authority']['fqcn']}::\${$finding['authority']['field']}` — " . implode(', ', $finding['literals']) . "; `{$finding['human_verdict']}`";
    }
    if ($payload['findings'] === []) {
        $lines[] = 'None. Unreviewed candidates are not promoted.';
    }
    $lines[] = '';
    $lines[] = '## Boundaries';
    $lines[] = '';
    $lines[] = '- Only final Composer-owned classes and direct `$this->field` comparisons/assignments are considered.';
    $lines[] = '- Receiver inference, inherited fields, public mutation, ORM hydration, reflection, framework binding, and dynamic properties remain unresolved.';
    $lines[] = '';
    return implode("\n", $lines);
}

try {
    $options = ppl_cli($argv, ['project-root', 'target', 'output-dir'], [
        'php' => 'php', 'composer' => 'composer', 'minimum-php' => '8.1.0', 'minimum-composer' => '2.2.0', 'reviews-dir' => null,
    ]);
    $root = ppl_project_root($options['project-root']);
    $target = ppl_inside_path($root, $options['target'], 'target');
    $output = ppl_inside_path($root, $options['output-dir'], 'output directory');
    $allowed = $root . '/reports/implicit-state';
    if (!ppl_is_inside($allowed, $output) || $output === $allowed) {
        throw new InvalidArgumentException('output directory must stay beneath reports/implicit-state');
    }
    ppl_assert_output($root, $output);
    $artifacts = [$output . '/findings.json', $output . '/candidates.json', $output . '/report.md', $output . '/facts.json'];
    ppl_clear_artifacts($artifacts);
    $facts = pse_collect($root, $target, $options['php'], $options['composer'], $options['minimum-php'], $options['minimum-composer']);
    $candidates = [];
    if ($facts['status'] === 'complete') {
        foreach ($facts['classes'] as $class) {
            if (!$class['final']) {
                continue;
            }
            $properties = [];
            foreach ($class['properties'] as $property) {
                if (in_array(strtolower($property['name']), ['state', 'status', 'phase'], true) && $property['type'] === 'string') {
                    $properties[$property['name']] = $property;
                }
            }
            foreach ($properties as $name => $property) {
                $operations = array_values(array_filter(
                    $class['member_operations'],
                    fn (array $operation): bool => $operation['member'] === $name && $operation['literal'] !== null,
                ));
                $literals = array_values(array_unique(array_map(fn (array $operation): string => $operation['literal'], $operations)));
                sort($literals);
                if (count($operations) < 3 || count($literals) < 2) {
                    continue;
                }
                $authority = [
                    'fqcn' => $class['fqcn'], 'file' => $class['file'], 'line' => $property['line'], 'field' => $name,
                    'field_type' => 'string', 'source_sha256' => $class['source_sha256'],
                ];
                $candidate = ['authority' => $authority, 'operations' => $operations, 'literals' => $literals];
                $candidate['candidate_id'] = 'PHP-STATE-' . strtoupper(substr(ppl_hash(json_encode($candidate, JSON_THROW_ON_ERROR)), 0, 12));
                $candidate['candidate_sha256'] = ppl_hash(json_encode($candidate, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));
                $candidates[] = $candidate;
            }
        }
    }
    usort($candidates, fn (array $a, array $b): int => [$a['authority']['file'], $a['authority']['line']] <=> [$b['authority']['file'], $b['authority']['line']]);
    $reviews = php_state_reviews($root, $options['reviews-dir']);
    $findings = [];
    $missing = [];
    foreach ($candidates as $candidate) {
        $review = $reviews[$candidate['candidate_id']] ?? null;
        if ($review === null || $review['candidate_sha256'] !== $candidate['candidate_sha256']) {
            $missing[] = $candidate['candidate_id'];
            continue;
        }
        $findings[] = [...$candidate, 'human_verdict' => $review['human_verdict'], 'reviewed_at' => $review['reviewed_at'] ?? null];
    }
    $status = $facts['status'];
    $failureKind = $facts['failure_kind'];
    if ($status === 'complete' && $missing !== []) {
        $status = 'partial';
        $failureKind = 'human_review_required';
    }
    $payload = [
        'schema_version' => 1, 'language' => 'php', 'analyzer' => PSE_ANALYZER, 'status' => $status, 'failure_kind' => $failureKind,
        'read_only' => true, 'target' => $facts['target'], 'candidates' => $candidates, 'findings' => $findings,
        'missing_reviews' => $missing, 'summary' => ['raw_candidates' => count($candidates), 'accepted' => count($findings)],
        'project_identity' => $facts['project_identity'], 'semantic_tool' => $facts['semantic_tool'], 'source_manifest_sha256' => $facts['source_manifest_sha256'], 'limits' => $facts['limits'],
    ];
    ppl_atomic_json($artifacts[0], $payload);
    ppl_atomic_json($artifacts[1], ['schema_version' => PHP_STATE_REVIEW_SCHEMA, 'candidates' => $candidates]);
    ppl_atomic_text($artifacts[2], php_state_report($payload));
    ppl_atomic_json($artifacts[3], $facts);
    exit(ppl_terminal_code(['status' => $status]));
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
