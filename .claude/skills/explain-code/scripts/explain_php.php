<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/_php-project-lexical/php_project_lexical.php';

try {
    $options = ppl_cli(
        $argv,
        ['project-root', 'target', 'output'],
        ['php' => 'php', 'composer' => 'composer', 'minimum-php' => '8.1.0', 'minimum-composer' => '2.2.0'],
    );
    $root = ppl_project_root($options['project-root']);
    $target = ppl_inside_path($root, $options['target'], 'target');
    $output = ppl_inside_path($root, $options['output'], 'output');
    ppl_assert_output($root, $output);
    $sidecar = preg_replace('/\.md\z/', '', $output) ?: $output . '-artifacts';
    $annotations = $sidecar . '/annotations';
    $artifacts = [
        $output,
        $sidecar . '/targets.json',
        $sidecar . '/scan.json',
        $sidecar . '/unexplained.txt',
        $sidecar . '/surprises.txt',
    ];
    ppl_clear_artifacts($artifacts);
    if (is_dir($annotations)) {
        foreach (glob($annotations . '/*.md') ?: [] as $old) {
            unlink($old);
        }
    }
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
    $facts = $snapshot['status'] === 'failed' ? [] : ppl_declarations($snapshot);
    $unexplained = $snapshot['status'] === 'failed' ? [] : ppl_unresolved($snapshot);
    $selected = array_slice($facts, 0, 15);
    $overflow = array_slice($facts, 15);
    foreach ($selected as &$fact) {
        $fact['symbol_key'] = preg_replace('/[^A-Za-z0-9_-]+/', '-', $fact['qualified_symbol'])
            . '-' . substr($fact['spelling_sha256'], 0, 12);
        ppl_atomic_text(
            $annotations . '/' . $fact['symbol_key'] . '.md',
            "# `{$fact['symbol']}`\n\n"
            . "- Kind: `{$fact['kind']}`\n"
            . "- Source: `{$fact['file']}`\n"
            . "- Contract: direct public PHP lexical declaration with an exact source span.\n"
            . "- Preconditions: unexplained without resolved caller/type evidence.\n"
            . "- Postconditions: unexplained without resolved caller/type evidence.\n"
            . "- Invariants: lexical declaration; behavior remains unexplained.\n"
            . "- Unexplained regions: body behavior, dynamic dispatch, types, and callers.\n",
        );
    }
    unset($fact);
    $analysis = ppl_public_snapshot($snapshot);
    $targets = [
        'schema_version' => 1,
        'target' => ppl_relative($root, $target),
        'language' => 'php',
        'status' => $snapshot['status'],
        'analysis' => ['php' => $analysis],
        'public_symbol_count' => count($facts),
        'selected' => $selected,
        'overflow' => $overflow,
        'unexplained' => $unexplained,
    ];
    ppl_atomic_json($artifacts[1], $targets);
    ppl_atomic_json($artifacts[2], $analysis);
    $unresolvedLines = array_map(
        fn (array $item): string => "- `{$item['file']}` — `{$item['symbol']}`: {$item['reason']}",
        $unexplained,
    );
    ppl_atomic_text($artifacts[3], implode("\n", $unresolvedLines) . ($unresolvedLines === [] ? '' : "\n"));
    ppl_atomic_text($artifacts[4], '');
    $contracts = array_map(
        fn (array $fact): string => "### `{$fact['symbol']}`\n\n"
            . "- Kind: `{$fact['kind']}`\n"
            . "- Source: `{$fact['file']}`\n"
            . "- Invariant: lexical declaration; behavior remains unexplained.\n"
            . "- Evidence: exact source span and spelling hash in `targets.json`.",
        $selected,
    );
    $markdown = "# Explanation — " . ppl_relative($root, $target) . "\n\n"
        . "| Field | Value |\n|---|---|\n"
        . "| Status | {$snapshot['status']} |\n"
        . "| Public symbols | " . count($facts) . " |\n"
        . "| Annotated this run | " . count($selected) . " |\n"
        . "| Overflow | " . count($overflow) . " |\n\n"
        . "## Summary\n\nDirect public PHP declarations from native lexical tokens. "
        . "This is source explanation evidence, not resolved behavior, Composer symbol identity, or framework behavior.\n\n"
        . "## Public contracts\n\n"
        . ($contracts === [] ? 'No complete public declaration inventory.' : implode("\n\n", $contracts));
    if ($unresolvedLines !== []) {
        $markdown .= "\n\n## Unexplained regions\n\n" . implode("\n", $unresolvedLines);
    }
    ppl_atomic_text($output, $markdown . "\n");
    exit(ppl_terminal_code($snapshot));
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(64);
}
