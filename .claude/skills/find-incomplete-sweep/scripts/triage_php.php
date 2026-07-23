<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/_php-project-lexical/php_project_lexical.php';

const PHP_SWEEP_VERDICTS = ['forgotten', 'deliberate', 'optional', 'not-applicable'];

try {
    $options = ppl_cli($argv, ['project-root', 'scan-dir', 'verdicts'], []);
    $root = ppl_project_root($options['project-root']);
    $scan = ppl_inside_path($root, $options['scan-dir'], 'scan directory');
    $verdictsPath = ppl_inside_path($root, $options['verdicts'], 'verdicts');
    $allowed = $root . '/reports/find-incomplete-sweep';
    if (!ppl_is_inside($allowed, $scan) || $scan === $allowed) {
        throw new InvalidArgumentException('scan directory must stay beneath reports/find-incomplete-sweep');
    }
    ppl_assert_output($root, $scan);
    if (!is_file($scan . '/manifest.json') || !is_file($verdictsPath) || is_link($verdictsPath)) {
        throw new InvalidArgumentException('manifest and verdicts must be regular files');
    }
    $manifest = json_decode((string) file_get_contents($scan . '/manifest.json'), true, 512, JSON_THROW_ON_ERROR);
    $raw = json_decode((string) file_get_contents($verdictsPath), true, 512, JSON_THROW_ON_ERROR);
    if (!is_array($raw['verdicts'] ?? null)) {
        throw new InvalidArgumentException('verdicts must contain a verdicts array');
    }
    $byId = [];
    foreach ($raw['verdicts'] as $verdict) {
        if (!is_array($verdict) || !is_string($verdict['candidate_id'] ?? null) || !is_string($verdict['candidate_sha256'] ?? null)
            || !in_array($verdict['verdict'] ?? null, PHP_SWEEP_VERDICTS, true) || !is_string($verdict['rationale'] ?? null)) {
            throw new InvalidArgumentException('verdict has invalid PHP sweep schema');
        }
        $byId[$verdict['candidate_id']] = $verdict;
    }
    $triaged = [];
    foreach ($manifest['findings'] as $candidate) {
        $verdict = $byId[$candidate['candidate_id']] ?? null;
        if ($verdict === null || $verdict['candidate_sha256'] !== $candidate['candidate_sha256']) {
            throw new InvalidArgumentException('every candidate needs a current hash-bound verdict');
        }
        $triaged[] = [...$candidate, 'human_verdict' => $verdict['verdict'], 'rationale' => $verdict['rationale'], 'completion' => $verdict['completion'] ?? null];
    }
    $lines = ['# PHP incomplete-sweep triage', ''];
    foreach (PHP_SWEEP_VERDICTS as $bucket) {
        $rows = array_values(array_filter($triaged, fn (array $row): bool => $row['human_verdict'] === $bucket));
        $lines[] = '## ' . ucfirst($bucket) . ' (' . count($rows) . ')';
        $lines[] = '';
        foreach ($rows as $row) {
            $lines[] = "- `{$row['candidate_id']}` — {$row['rationale']}";
        }
        $lines[] = '';
    }
    ppl_atomic_json($scan . '/triaged.json', ['schema_version' => 1, 'language' => 'php', 'triaged' => $triaged]);
    ppl_atomic_text($scan . '/triaged.md', implode("\n", $lines));
    exit(0);
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
