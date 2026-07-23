<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/_php-project-lexical/php_project_lexical.php';

function php_glossary_scalar(string $value): mixed
{
    $value = trim($value);
    if ($value === '') {
        return '';
    }
    if (str_starts_with($value, '[')) {
        $decoded = json_decode(str_replace("'", '"', $value), true, 512, JSON_THROW_ON_ERROR);
        if (!is_array($decoded)) {
            throw new RuntimeException('glossary flow list must decode to an array');
        }
        return $decoded;
    }
    if ((str_starts_with($value, '"') && str_ends_with($value, '"'))
        || (str_starts_with($value, "'") && str_ends_with($value, "'"))) {
        return substr($value, 1, -1);
    }
    return $value;
}

/** @return array<string, mixed> */
function php_load_glossary(string $path): array
{
    $text = @file_get_contents($path);
    if ($text === false) {
        throw new RuntimeException('glossary could not be read');
    }
    try {
        $decoded = json_decode($text, true, 512, JSON_THROW_ON_ERROR);
        if (is_array($decoded)) {
            return $decoded;
        }
    } catch (JsonException) {
        // Continue through the bounded block-list profile used by copied installs.
    }
    $data = ['concepts' => [], 'flagged_ambiguities' => []];
    $collection = null;
    $current = null;
    $listKey = null;
    $flush = static function () use (&$data, &$collection, &$current): void {
        if ($collection !== null && is_array($current)) {
            $data[$collection][] = $current;
        }
        $current = null;
    };
    foreach (preg_split('/\R/', $text) ?: [] as $raw) {
        if (trim($raw) === '' || str_starts_with(ltrim($raw), '#')) {
            continue;
        }
        $indent = strlen($raw) - strlen(ltrim($raw, ' '));
        $line = trim($raw);
        if ($indent === 0 && preg_match('/\A(concepts|flagged_ambiguities):(?:\s*\[\])?\z/', $line, $match) === 1) {
            $flush();
            $collection = $match[1];
            $listKey = null;
            continue;
        }
        if ($collection === null) {
            throw new RuntimeException('unsupported glossary top-level shape');
        }
        if ($indent === 2 && str_starts_with($line, '- ')) {
            $flush();
            $current = [];
            $listKey = null;
            $entry = substr($line, 2);
            if (str_contains($entry, ':')) {
                [$key, $value] = explode(':', $entry, 2);
                $current[trim($key)] = php_glossary_scalar($value);
            }
            continue;
        }
        if (!is_array($current)) {
            if ($line === '[]') {
                continue;
            }
            throw new RuntimeException('glossary item content appears before a list item');
        }
        if ($indent === 4 && str_contains($line, ':')) {
            [$key, $value] = explode(':', $line, 2);
            $key = trim($key);
            $value = trim($value);
            $current[$key] = $value === '' ? [] : php_glossary_scalar($value);
            $listKey = $value === '' ? $key : null;
            continue;
        }
        if ($indent >= 6 && $listKey !== null && str_starts_with($line, '- ')) {
            $current[$listKey][] = php_glossary_scalar(substr($line, 2));
            continue;
        }
        throw new RuntimeException("unsupported glossary line: {$line}");
    }
    $flush();
    if (!is_array($data['concepts'])) {
        throw new RuntimeException('glossary must contain a concepts list');
    }
    return $data;
}

/** @return list<array<string, mixed>> */
function php_term_hits(array $row, string $term): array
{
    $source = $row['_source'];
    $pattern = '/(?<![A-Za-z0-9_])' . preg_quote($term, '/') . '(?![A-Za-z0-9_])/i';
    $matched = preg_match_all($pattern, $source, $matches, PREG_OFFSET_CAPTURE);
    if ($matched === false) {
        throw new RuntimeException("invalid glossary term pattern: {$term}");
    }
    $hits = [];
    foreach ($matches[0] as [$spelling, $offset]) {
        $hits[] = [
            'term' => $term,
            'match' => $spelling,
            'line' => substr_count(substr($source, 0, $offset), "\n") + 1,
            'span' => ppl_span($source, $offset, $offset + strlen($spelling)),
            'spelling_sha256' => ppl_hash($spelling),
        ];
    }
    return $hits;
}

/** @return list<array<string, mixed>> */
function php_concept_findings(array $glossary, array $rows): array
{
    $findings = [];
    $concepts = array_values(array_filter($glossary['concepts'] ?? [], 'is_array'));
    $byName = [];
    foreach ($concepts as $concept) {
        if (is_string($concept['name'] ?? null)) {
            $byName[$concept['name']] = $concept;
        }
    }
    foreach ($concepts as $concept) {
        foreach ($concept['avoid'] ?? [] as $rawTerm) {
            if (!is_string($rawTerm)) {
                continue;
            }
            $term = rtrim(trim(explode('(', $rawTerm, 2)[0], " \t\n\r\0\x0B\"'"), ',.;:');
            foreach ($rows as $row) {
                foreach (php_term_hits($row, $term) as $hit) {
                    $findings[] = [
                        'band' => 'avoid_term_hit',
                        'concept' => $concept['name'] ?? '?',
                        'file' => $row['file'],
                        'language' => 'php',
                        'source_sha256' => $row['source_sha256'],
                        ...$hit,
                    ];
                }
            }
        }
        $replacement = $concept['superseded_by'] ?? null;
        if (!is_string($replacement) || !isset($byName[$replacement]) || isset($concept['coverage_lint'])) {
            continue;
        }
        $oldTerms = array_values(array_filter([$concept['name'] ?? null, ...($concept['aliases'] ?? [])], 'is_string'));
        $newConcept = $byName[$replacement];
        $newTerms = array_values(array_filter([$newConcept['name'] ?? null, ...($newConcept['aliases'] ?? [])], 'is_string'));
        foreach ($rows as $row) {
            $oldPresent = array_filter($oldTerms, fn (string $term): bool => php_term_hits($row, $term) !== []);
            $newPresent = array_filter($newTerms, fn (string $term): bool => php_term_hits($row, $term) !== []);
            if ($oldPresent === [] || $newPresent === []) {
                continue;
            }
            foreach ($oldTerms as $term) {
                foreach (php_term_hits($row, $term) as $hit) {
                    $findings[] = [
                        'band' => 'superseded_co_occurrence',
                        'concept' => $concept['name'],
                        'superseded_by' => $replacement,
                        'side' => 'old',
                        'file' => $row['file'],
                        'language' => 'php',
                        'source_sha256' => $row['source_sha256'],
                        ...$hit,
                    ];
                }
            }
        }
    }
    foreach ($glossary['flagged_ambiguities'] ?? [] as $ambiguity) {
        if (!is_array($ambiguity)) {
            continue;
        }
        $terms = array_values(array_filter($ambiguity['competing_terms'] ?? [], 'is_string'));
        foreach ($rows as $row) {
            $found = [];
            foreach ($terms as $term) {
                $hits = php_term_hits($row, $term);
                if ($hits !== []) {
                    $found[$term] = $hits;
                }
            }
            if (count($found) < 2) {
                continue;
            }
            foreach ($found as $hits) {
                foreach ($hits as $hit) {
                    $findings[] = [
                        'band' => 'competing_term_coexistence',
                        'ambiguity_id' => $ambiguity['id'] ?? '?',
                        'competing_terms' => array_keys($found),
                        'file' => $row['file'],
                        'language' => 'php',
                        'source_sha256' => $row['source_sha256'],
                        ...$hit,
                    ];
                }
            }
        }
    }
    usort($findings, fn (array $left, array $right): int => [$left['file'], $left['line'], $left['band'], $left['term']] <=> [$right['file'], $right['line'], $right['band'], $right['term']]);
    return $findings;
}

try {
    $options = ppl_cli(
        $argv,
        ['project-root', 'target', 'glossary', 'output', 'report'],
        ['php' => 'php', 'composer' => 'composer', 'minimum-php' => '8.1.0', 'minimum-composer' => '2.2.0'],
    );
    $root = ppl_project_root($options['project-root']);
    $target = ppl_inside_path($root, $options['target'], 'target');
    $glossaryPath = ppl_inside_path($root, $options['glossary'], 'glossary');
    $output = ppl_inside_path($root, $options['output'], 'output');
    $report = ppl_inside_path($root, $options['report'], 'report');
    ppl_assert_output($root, $output);
    ppl_assert_output($root, $report);
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
    try {
        $glossary = php_load_glossary($glossaryPath);
    } catch (Throwable $error) {
        $snapshot['status'] = 'failed';
        $snapshot['errors'][] = 'glossary-invalid: ' . $error->getMessage();
        $glossary = ['concepts' => [], 'flagged_ambiguities' => []];
    }
    if (!ppl_sources_preserved($snapshot)) {
        $snapshot['status'] = 'failed';
        $snapshot['errors'][] = 'unexpected-source-mutation';
    }
    $rows = array_values(array_filter(
        $snapshot['inventory'],
        fn (array $row): bool => $row['role'] === 'eligible' && $row['parse_state'] !== 'syntax-error',
    ));
    $findings = $snapshot['status'] === 'failed' ? [] : php_concept_findings($glossary, $rows);
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
    ppl_atomic_json($finalJson, [
        'schema_version' => 1,
        'status' => $snapshot['status'],
        'outcome' => $outcome,
        'analysis' => ['php' => $analysis],
        'detections_sha256' => ppl_hash($jsonl),
        'findings' => $findings,
    ]);
    ppl_atomic_json($scanJson, $analysis);
    $lines = [
        '# Concept-divergence scan — PHP',
        '',
        "**Status:** `{$snapshot['status']}`",
        "**Outcome:** `{$outcome}`",
        '',
    ];
    if ($findings !== []) {
        $lines[] = 'Total findings: **' . count($findings) . '**.';
        foreach ($findings as $finding) {
            $lines[] = "- `{$finding['file']}:{$finding['line']}` — `{$finding['term']}` — `{$finding['band']}`";
        }
    } else {
        $lines[] = $snapshot['status'] === 'complete'
            ? 'No strict glossary drift detected in authored PHP source.'
            : 'Analysis is incomplete; no absence-of-drift conclusion is available.';
    }
    ppl_atomic_text($report, implode("\n", $lines) . "\n");
    exit(ppl_terminal_code($snapshot));
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
