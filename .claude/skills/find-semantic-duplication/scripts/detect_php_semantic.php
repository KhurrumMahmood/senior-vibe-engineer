<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/_php-semantic/php_semantic_facts.php';

const PHP_SEMANTIC_REVIEW_SCHEMA = 'php-semantic-duplication-review-v1';
const PHP_SEMANTIC_VERDICTS = ['confirm_candidate', 'keep_separate', 'uncertain'];

/** @return array<string,array<string,mixed>> */
function php_semantic_reviews(string $root, ?string $supplied): array
{
    if ($supplied === null) {
        return [];
    }
    $directory = ppl_inside_path($root, $supplied, 'reviews directory');
    if (!is_dir($directory) || is_link($directory) || ppl_has_symlink_component($root, $directory)) {
        throw new InvalidArgumentException('reviews directory must be a regular non-symlink directory');
    }
    $reviews = [];
    foreach (glob($directory . '/*.json') ?: [] as $path) {
        $row = json_decode((string) file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
        if (!is_array($row) || ($row['schema_version'] ?? null) !== PHP_SEMANTIC_REVIEW_SCHEMA
            || !is_string($row['candidate_id'] ?? null) || !is_string($row['candidate_sha256'] ?? null)
            || !in_array($row['human_verdict'] ?? null, PHP_SEMANTIC_VERDICTS, true)) {
            throw new InvalidArgumentException('review has an invalid PHP semantic-duplication schema');
        }
        $reviews[$row['candidate_id']] = $row;
    }
    return $reviews;
}

function php_semantic_triage(array $payload): string
{
    $lines = ['# PHP semantic-duplication triage', '', "Status: `{$payload['status']}`", '', '## Confirmed only after hash-bound human review', ''];
    foreach ($payload['confirmed'] as $finding) {
        $members = implode('`, `', array_column($finding['members'], 'fqmn'));
        $lines[] = "- `{$finding['finding_id']}` — `{$members}`; `{$finding['human_verdict']}`";
    }
    if ($payload['confirmed'] === []) {
        $lines[] = 'None.';
    }
    $lines[] = '';
    $lines[] = '## Limits';
    $lines[] = '';
    $lines[] = '- The lead shares only Composer-resolved direct return construction identity and named-field shape.';
    $lines[] = '- It never establishes behavioral equivalence, caller equivalence, ownership, framework behavior, or refactor safety.';
    $lines[] = '';
    return implode("\n", $lines);
}

try {
    $options = ppl_cli($argv, ['project-root', 'target', 'report-dir'], [
        'php' => 'php', 'composer' => 'composer', 'minimum-php' => '8.1.0', 'minimum-composer' => '2.2.0', 'reviews-dir' => null,
    ]);
    $root = ppl_project_root($options['project-root']);
    $target = ppl_inside_path($root, $options['target'], 'target');
    $report = ppl_inside_path($root, $options['report-dir'], 'report directory');
    $allowed = $root . '/reports/semantic-duplication';
    if (!ppl_is_inside($allowed, $report) || $report === $allowed) {
        throw new InvalidArgumentException('report directory must stay beneath reports/semantic-duplication');
    }
    ppl_assert_output($root, $report);
    $artifacts = [$report . '/findings.json', $report . '/candidates.jsonl', $report . '/triage.md', $report . '/analysis.json', $report . '/facts.json'];
    ppl_clear_artifacts($artifacts);
    $facts = pse_collect($root, $target, $options['php'], $options['composer'], $options['minimum-php'], $options['minimum-composer']);
    $methods = [];
    if ($facts['status'] === 'complete') {
        foreach ($facts['classes'] as $class) {
            if (!$class['final']) {
                continue;
            }
            foreach ($class['methods'] as $method) {
                if ($method['visibility'] !== 'public' || count($method['return_news']) !== 1) {
                    continue;
                }
                $returned = $method['return_news'][0];
                if (($returned['resolution'] ?? null) !== 'composer-psr4') {
                    continue;
                }
                $methods[] = [
                    'fqmn' => $method['fqmn'], 'file' => $method['file'], 'line' => $method['line'],
                    'returned_class' => $returned['class'], 'named_arguments' => $returned['named_arguments'],
                    'direct_calls' => array_column($method['direct_calls'], 'name'), 'source_sha256' => $method['source_sha256'],
                ];
            }
        }
    }
    $candidates = [];
    $rejected = [];
    for ($left = 0; $left < count($methods); $left++) {
        for ($right = $left + 1; $right < count($methods); $right++) {
            $a = $methods[$left];
            $b = $methods[$right];
            if ($a['returned_class'] !== $b['returned_class']) {
                continue;
            }
            $fieldsA = $a['named_arguments']; sort($fieldsA);
            $fieldsB = $b['named_arguments']; sort($fieldsB);
            if ($fieldsA === [] || $fieldsA !== $fieldsB) {
                $rejected[] = ['members' => [$a['fqmn'], $b['fqmn']], 'reason_code' => 'resolved_return_construction_shape_differs'];
                continue;
            }
            if (in_array(substr($b['fqmn'], strrpos($b['fqmn'], '::') + 2), $a['direct_calls'], true)
                || in_array(substr($a['fqmn'], strrpos($a['fqmn'], '::') + 2), $b['direct_calls'], true)) {
                $rejected[] = ['members' => [$a['fqmn'], $b['fqmn']], 'reason_code' => 'direct_wrapper_relationship'];
                continue;
            }
            $candidate = [
                'members' => [$a, $b], 'return_construction' => ['class' => $a['returned_class'], 'named_arguments' => $fieldsA],
                'investigation_status' => 'human_review_required',
                'notes' => 'Composer-resolved direct construction lead; not proof of behavioral equivalence or refactor safety.',
                'source_manifest_sha256' => $facts['source_manifest_sha256'],
            ];
            $candidate['candidate_id'] = 'PHP-SD-' . strtoupper(substr(ppl_hash(json_encode($candidate, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR)), 0, 12));
            $candidate['candidate_sha256'] = ppl_hash(json_encode($candidate, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));
            $candidates[] = $candidate;
        }
    }
    $reviews = php_semantic_reviews($root, $options['reviews-dir']);
    $confirmed = [];
    $uncertain = [];
    $missing = [];
    foreach ($candidates as $candidate) {
        $review = $reviews[$candidate['candidate_id']] ?? null;
        if ($review === null || $review['candidate_sha256'] !== $candidate['candidate_sha256']) {
            $missing[] = $candidate['candidate_id'];
            continue;
        }
        $reviewed = [...$candidate, 'human_verdict' => $review['human_verdict'], 'rationale' => $review['rationale'] ?? null];
        if ($review['human_verdict'] === 'confirm_candidate') {
            $reviewed['finding_id'] = $candidate['candidate_id'];
            $reviewed['investigation_status'] = 'confirmed';
            $confirmed[] = $reviewed;
        } else {
            $uncertain[] = $reviewed;
        }
    }
    $status = $facts['status'];
    $failureKind = $facts['failure_kind'];
    if ($status === 'complete' && $missing !== []) {
        $status = 'partial';
        $failureKind = 'human_review_required';
    }
    $payload = [
        'schema_version' => 1, 'language' => 'php', 'analyzer' => PSE_ANALYZER, 'status' => $status, 'failure_kind' => $failureKind,
        'read_only' => true, 'target' => $facts['target'], 'confirmed' => $confirmed, 'candidates' => $candidates,
        'rejected' => $rejected, 'uncertain' => $uncertain, 'missing_reviews' => $missing,
        'capability_matrix' => ['composer_psr4_direct_return_construction_leads' => 'available', 'behavioral_equivalence' => 'unavailable'],
        'project_identity' => $facts['project_identity'], 'semantic_tool' => $facts['semantic_tool'], 'source_manifest_sha256' => $facts['source_manifest_sha256'], 'limits' => $facts['limits'],
    ];
    ppl_atomic_json($artifacts[0], $payload);
    ppl_atomic_text($artifacts[1], implode('', array_map(fn (array $candidate): string => json_encode($candidate, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n", $candidates)));
    ppl_atomic_text($artifacts[2], php_semantic_triage($payload));
    ppl_atomic_json($artifacts[3], ['status' => $status, 'rejected' => $rejected, 'uncertain' => $uncertain]);
    ppl_atomic_json($artifacts[4], $facts);
    exit(ppl_terminal_code(['status' => $status]));
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
