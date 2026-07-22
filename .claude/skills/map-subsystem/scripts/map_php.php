<?php

declare(strict_types=1);

/**
 * Bounded PHP subsystem map using native lint plus Composer's declared PSR-4
 * project contract. This is deliberately family-local: copied skill users need
 * only this file, PHP 8.1+, and the host-owned Composer executable.
 */

const MAP_PHP_EXCLUDED_DIRECTORIES = [
    '.agents', '.claude', '.git', '.idea', '.venv', '.vscode', 'build',
    'coverage', 'dist', 'fixtures', 'gen', 'generated', 'node_modules',
    'out', 'reports', 'test', 'testdata', 'tests', 'vendor', 'venv',
];

final class MapPhpTerminal extends RuntimeException
{
    public function __construct(
        public readonly string $status,
        public readonly string $kind,
        string $message,
        public readonly int $exitCode = 0,
        public readonly bool $writeArtifacts = true,
    ) {
        parent::__construct($message);
    }
}

/** @return array<string, mixed> */
function map_php_parse_options(array $argv): array
{
    $arguments = array_slice($argv, 1);
    $allowed = [
        '--name', '--target', '--project-root', '--output', '--evidence',
        '--composer', '--minimum-php', '--minimum-composer',
    ];
    if (count($arguments) % 2 !== 0) {
        throw new InvalidArgumentException(map_php_usage());
    }

    $values = [];
    for ($index = 0; $index < count($arguments); $index += 2) {
        $flag = $arguments[$index];
        if (!in_array($flag, $allowed, true) || array_key_exists($flag, $values)) {
            throw new InvalidArgumentException(map_php_usage());
        }
        $values[$flag] = $arguments[$index + 1];
    }
    foreach (['--name', '--target', '--project-root', '--output', '--evidence'] as $required) {
        if (!array_key_exists($required, $values)) {
            throw new InvalidArgumentException(map_php_usage());
        }
    }
    if (!preg_match('/\A[a-z0-9][a-z0-9-]*\z/', $values['--name'])) {
        throw new InvalidArgumentException('--name must be lowercase kebab-case');
    }

    $rootInput = $values['--project-root'];
    if (!is_dir($rootInput) || is_link($rootInput)) {
        throw new InvalidArgumentException('project root must be a regular directory');
    }
    $root = realpath($rootInput);
    if ($root === false) {
        throw new InvalidArgumentException('project root could not be resolved');
    }

    return [
        'root' => $root,
        'name' => $values['--name'],
        'target' => map_php_resolve_inside($root, $values['--target'], 'target'),
        'output' => map_php_resolve_inside($root, $values['--output'], 'output'),
        'evidence' => map_php_resolve_inside($root, $values['--evidence'], 'evidence'),
        'composer' => $values['--composer'] ?? 'composer',
        'minimum_php' => map_php_version_argument($values['--minimum-php'] ?? '8.1.0', '--minimum-php'),
        'minimum_composer' => map_php_version_argument(
            $values['--minimum-composer'] ?? '2.2.0', '--minimum-composer'
        ),
    ];
}

function map_php_usage(): string
{
    return 'usage: map_php.php --name <kebab-name> --target <psr4-directory> '
        . '--project-root <root> --output .claude/docs/subsystems/<name>.md '
        . '--evidence reports/map/<name>/php-map.json [--composer composer] '
        . '[--minimum-php 8.1.0] [--minimum-composer 2.2.0]';
}

function map_php_version_argument(string $value, string $flag): string
{
    if (!preg_match('/\A\d+(?:\.\d+){0,2}\z/', $value)) {
        throw new InvalidArgumentException("{$flag} must be a numeric major.minor[.patch] version");
    }
    return $value;
}

function map_php_resolve_inside(string $root, string $supplied, string $label): string
{
    $candidate = map_php_is_absolute($supplied) ? $supplied : $root . DIRECTORY_SEPARATOR . $supplied;
    $candidate = map_php_normalize_path($candidate);
    if (!map_php_is_inside($root, $candidate)) {
        throw new InvalidArgumentException("{$label} must stay inside project root: {$supplied}");
    }
    return $candidate;
}

function map_php_is_absolute(string $path): bool
{
    return str_starts_with($path, DIRECTORY_SEPARATOR)
        || preg_match('/\A[A-Za-z]:[\\\\\/]/', $path) === 1;
}

function map_php_normalize_path(string $path): string
{
    $path = str_replace(['/', '\\'], DIRECTORY_SEPARATOR, $path);
    $prefix = '';
    if (preg_match('/\A([A-Za-z]:)/', $path, $match) === 1) {
        $prefix = $match[1];
        $path = substr($path, strlen($prefix));
    }
    $absolute = str_starts_with($path, DIRECTORY_SEPARATOR);
    $parts = [];
    foreach (explode(DIRECTORY_SEPARATOR, $path) as $part) {
        if ($part === '' || $part === '.') {
            continue;
        }
        if ($part === '..') {
            if ($parts !== []) {
                array_pop($parts);
            }
            continue;
        }
        $parts[] = $part;
    }
    $joined = implode(DIRECTORY_SEPARATOR, $parts);
    if ($absolute) {
        return $prefix . DIRECTORY_SEPARATOR . $joined;
    }
    return $prefix . $joined;
}

function map_php_is_inside(string $root, string $candidate): bool
{
    $root = rtrim(map_php_normalize_path($root), DIRECTORY_SEPARATOR);
    $candidate = map_php_normalize_path($candidate);
    return $candidate === $root || str_starts_with($candidate, $root . DIRECTORY_SEPARATOR);
}

function map_php_relative(string $root, string $path): string
{
    if (!map_php_is_inside($root, $path)) {
        return str_replace(DIRECTORY_SEPARATOR, '/', $path);
    }
    $root = rtrim(map_php_normalize_path($root), DIRECTORY_SEPARATOR);
    $relative = ltrim(substr(map_php_normalize_path($path), strlen($root)), DIRECTORY_SEPARATOR);
    return str_replace(DIRECTORY_SEPARATOR, '/', $relative);
}

function map_php_path_has_symlink(string $root, string $candidate): bool
{
    if (!map_php_is_inside($root, $candidate)) {
        return true;
    }
    $current = rtrim($root, DIRECTORY_SEPARATOR);
    $relative = map_php_relative($root, $candidate);
    if ($relative === '') {
        return is_link($current);
    }
    foreach (explode('/', $relative) as $part) {
        $current .= DIRECTORY_SEPARATOR . $part;
        if (is_link($current)) {
            return true;
        }
    }
    return false;
}

/** @param array<string, mixed> $options */
function map_php_validate_artifact_paths(array $options): void
{
    $docs = $options['root'] . DIRECTORY_SEPARATOR . '.claude' . DIRECTORY_SEPARATOR . 'docs'
        . DIRECTORY_SEPARATOR . 'subsystems';
    $reports = $options['root'] . DIRECTORY_SEPARATOR . 'reports' . DIRECTORY_SEPARATOR . 'map';
    if (!map_php_is_inside($docs, $options['output']) || $options['output'] === $docs) {
        throw new InvalidArgumentException('output must stay below .claude/docs/subsystems');
    }
    if (!map_php_is_inside($reports, $options['evidence']) || $options['evidence'] === $reports) {
        throw new InvalidArgumentException('evidence must stay below reports/map');
    }
    if (map_php_path_has_symlink($options['root'], $options['output'])
        || map_php_path_has_symlink($options['root'], $options['evidence'])) {
        throw new InvalidArgumentException('artifact output must not traverse a symbolic link');
    }
}

/** @param array<string, mixed> $options
 *  @return array<string, mixed>
 */
function map_php_run(array $options): array
{
    if (version_compare(PHP_VERSION, $options['minimum_php'], '<')) {
        throw new MapPhpTerminal(
            'unsupported',
            'php_version_too_old',
            'PHP ' . PHP_VERSION . ' is below required PHP ' . $options['minimum_php'] . '.',
        );
    }
    if (map_php_path_has_symlink($options['root'], $options['target']) || is_link($options['target'])) {
        throw new MapPhpTerminal(
            'unsupported', 'unsafe_target', 'Target must be a non-symlink directory inside the project root.',
        );
    }
    if (!is_dir($options['target'])) {
        throw new MapPhpTerminal(
            'unsupported', 'target_not_directory', 'PHP map v1 requires one existing production directory target.',
        );
    }
    if (map_php_is_excluded($options['root'], $options['target'])) {
        throw new MapPhpTerminal(
            'unsupported',
            'excluded_target',
            'Generated, vendor, test, and build targets are outside PHP map v1.',
        );
    }

    $manifestPath = $options['root'] . DIRECTORY_SEPARATOR . 'composer.json';
    if (!is_file($manifestPath)) {
        throw new MapPhpTerminal(
            'unsupported', 'composer_manifest_missing', 'Composer project metadata (composer.json) is required.',
        );
    }
    if (is_link($manifestPath)) {
        throw new MapPhpTerminal(
            'unsupported', 'unsafe_composer_manifest', 'composer.json must not be a symbolic link.',
        );
    }

    $composer = map_php_resolve_command($options['composer']);
    if ($composer === null) {
        throw new MapPhpTerminal(
            'unsupported', 'composer_tool_missing', 'Composer 2.2+ is required for the PHP PSR-4 map.',
        );
    }
    $composerVersion = map_php_composer_version($composer, $options['root']);
    if (version_compare($composerVersion, $options['minimum_composer'], '<')) {
        throw new MapPhpTerminal(
            'unsupported',
            'composer_version_too_old',
            'Composer ' . $composerVersion . ' is below required Composer ' . $options['minimum_composer'] . '.',
        );
    }
    $validation = map_php_process([...$composer, 'validate', '--no-check-publish', '--no-interaction'], $options['root']);
    if ($validation['exit'] !== 0) {
        throw new MapPhpTerminal(
            'failed',
            'composer_validation_failed',
            'composer validate failed: ' . map_php_process_summary($validation),
            2,
        );
    }

    try {
        $manifest = json_decode(
            (string) file_get_contents($manifestPath), true, 512, JSON_THROW_ON_ERROR
        );
    } catch (JsonException $error) {
        throw new MapPhpTerminal('failed', 'composer_manifest_invalid', $error->getMessage(), 2);
    }
    if (!is_array($manifest)) {
        throw new MapPhpTerminal('failed', 'composer_manifest_invalid', 'composer.json must contain an object.', 2);
    }

    $mappings = map_php_psr4_mappings($options['root'], $manifest);
    $targetMappings = array_values(array_filter(
        $mappings,
        static fn (array $mapping): bool => map_php_is_inside($mapping['root'], $options['target']),
    ));
    if ($targetMappings === []) {
        throw new MapPhpTerminal(
            'unsupported',
            'target_outside_psr4_roots',
            'Target must be inside one production Composer autoload.psr-4 source root.',
        );
    }

    $scan = map_php_collect_sources($options['root'], $mappings);
    foreach ($scan['symlinked'] as $source) {
        if (map_php_is_inside($options['target'], $source['absolute'])) {
            throw new MapPhpTerminal(
                'unsupported',
                'unsafe_source',
                'Selected PHP source must not be a symbolic link: ' . $source['file'],
            );
        }
    }
    $targetSources = array_values(array_filter(
        $scan['eligible'],
        static fn (array $source): bool => map_php_is_inside($options['target'], $source['absolute']),
    ));
    if ($targetSources === []) {
        throw new MapPhpTerminal(
            'unsupported', 'no_eligible_php_source', 'Target contains no eligible production PHP source.',
        );
    }

    map_php_lint_sources($options['root'], $scan['eligible']);
    $parsed = [];
    foreach ($scan['eligible'] as $source) {
        try {
            $parsed[$source['absolute']] = map_php_parse_source($source['absolute'], $source['file']);
        } catch (Throwable $error) {
            throw new MapPhpTerminal(
                'failed', 'php_tokenizer_failure', 'Could not collect PHP declarations/imports: ' . $error->getMessage(), 2,
            );
        }
    }

    $classes = [];
    $duplicateDeclarations = [];
    foreach ($parsed as $source) {
        foreach ($source['declarations'] as $declaration) {
            $qualified = $declaration['qualified_name'];
            if (array_key_exists($qualified, $classes)) {
                $duplicateDeclarations[] = $qualified;
                continue;
            }
            $classes[$qualified] = $declaration;
        }
    }
    ksort($classes, SORT_STRING);

    $targetPaths = array_fill_keys(array_column($targetSources, 'absolute'), true);
    $targetDeclarations = [];
    foreach ($classes as $declaration) {
        if (isset($targetPaths[$declaration['absolute']])) {
            $targetDeclarations[] = map_php_public_symbol($declaration, $mappings, $options['root']);
        }
    }
    usort($targetDeclarations, static fn (array $left, array $right): int => [$left['file'], $left['line'], $left['qualified_name']]
        <=> [$right['file'], $right['line'], $right['qualified_name']]);

    $targetSymbols = array_fill_keys(array_column($targetDeclarations, 'qualified_name'), true);
    $mappingIssues = [];
    foreach ($targetDeclarations as $declaration) {
        if ($declaration['resolution'] !== 'composer_psr4_declared') {
            $mappingIssues[] = $declaration['qualified_name'];
        }
    }

    $outbound = [];
    $inbound = [];
    $external = [];
    $unresolved = [];
    foreach ($parsed as $source) {
        $sourceIsTarget = isset($targetPaths[$source['absolute']]);
        foreach ($source['imports'] as $import) {
            $edge = map_php_import_edge($source, $import, $classes, $mappings, $options['root']);
            if ($edge['resolution'] === 'unresolved_first_party_psr4' && $sourceIsTarget) {
                $unresolved[] = map_php_unresolved_edge($edge);
            }
            if ($sourceIsTarget && $edge['resolution'] === 'composer_psr4_first_party') {
                $outbound[] = $edge;
            } elseif ($sourceIsTarget && $edge['resolution'] === 'external_import') {
                $external[] = $edge;
            }
            if (!$sourceIsTarget && $edge['resolution'] === 'composer_psr4_first_party'
                && isset($targetSymbols[$edge['target_symbol']])) {
                $inbound[] = $edge;
            }
        }
    }
    map_php_sort_edges($outbound);
    map_php_sort_edges($inbound);
    map_php_sort_edges($external);
    map_php_sort_edges($unresolved);

    $targetExcluded = [];
    foreach (array_merge($scan['excluded'], $scan['generated']) as $source) {
        if (map_php_is_inside($options['target'], $source['absolute'])) {
            $targetExcluded[] = $source['file'];
        }
    }
    sort($targetExcluded, SORT_STRING);

    $partialKinds = [];
    if ($unresolved !== [] || $mappingIssues !== [] || $duplicateDeclarations !== []) {
        $partialKinds[] = 'psr4_resolution_incomplete';
    }
    if ($scan['symlinked'] !== []) {
        $partialKinds[] = 'symlinked_source_excluded';
    }
    if ($scan['missing_roots'] !== []) {
        $partialKinds[] = 'psr4_root_missing';
    }
    $status = $partialKinds === [] ? 'complete' : 'partial';
    $failureKind = $partialKinds === [] ? null : implode('+', $partialKinds);

    $eligibleFiles = array_column($scan['eligible'], 'file');
    sort($eligibleFiles, SORT_STRING);
    $targetFiles = array_column($targetSources, 'file');
    sort($targetFiles, SORT_STRING);

    return [
        'schema_version' => 1,
        'status' => $status,
        'failure_kind' => $failureKind,
        'message' => $status === 'complete'
            ? 'PHP syntax and Composer PSR-4 static import facts were established.'
            : 'The static map is partial; inspect unresolved or excluded source evidence.',
        'language' => 'php',
        'analyzer' => 'native-php-lint+composer-psr4-static',
        'php' => ['version' => PHP_VERSION, 'minimum_version' => $options['minimum_php'], 'lint' => 'passed'],
        'composer' => [
            'path' => implode(' ', $composer),
            'version' => $composerVersion,
            'minimum_version' => $options['minimum_composer'],
            'validation' => 'passed',
        ],
        'target' => [
            'path' => map_php_relative($options['root'], $options['target']),
            'kind' => 'psr4_directory',
            'source_files' => count($targetFiles),
            'eligible_files' => $targetFiles,
            'excluded_files' => $targetExcluded,
        ],
        'source_inventory' => [
            'eligible_files' => $eligibleFiles,
            'excluded_files' => array_values(array_map(static fn (array $source): string => $source['file'], $scan['excluded'])),
            'generated_files' => array_values(array_map(static fn (array $source): string => $source['file'], $scan['generated'])),
            'symlinked_files' => array_values(array_map(static fn (array $source): string => $source['file'], $scan['symlinked'])),
            'missing_psr4_roots' => $scan['missing_roots'],
        ],
        'psr4_roots' => array_values(array_map(static fn (array $mapping): array => [
            'prefix' => $mapping['prefix'],
            'path' => $mapping['path'],
        ], $mappings)),
        'counts' => [
            'source_files' => count($targetFiles),
            'declared_symbols' => count($targetDeclarations),
            'outbound_imports' => count($outbound),
            'inbound_imports' => count($inbound),
            'external_imports' => count($external),
            'unresolved_imports' => count($unresolved),
        ],
        'exported_surface' => $targetDeclarations,
        'outbound_imports' => $outbound,
        'inbound_imports' => $inbound,
        'external_imports' => $external,
        'unresolved_imports' => $unresolved,
        'duplicate_declarations' => array_values(array_unique($duplicateDeclarations)),
        'completeness' => [
            'source_inventory' => $scan['symlinked'] === [] && $scan['missing_roots'] === [] ? 'complete' : 'partial',
            'php_syntax' => 'complete',
            'composer_manifest' => 'complete',
            'composer_psr4_static_resolution' => $unresolved === [] && $mappingIssues === [] && $duplicateDeclarations === []
                ? 'complete' : 'partial',
            'dynamic_calls_and_types' => 'unavailable',
        ],
        'unavailable_fields' => [
            [
                'field' => 'dynamic_call_targets',
                'reason' => 'Composer PSR-4 maps class-file candidates; it does not resolve dynamic PHP calls.',
            ],
            [
                'field' => 'types',
                'reason' => 'PHP v1 does not run PHPStan, Psalm, or another project-owned semantic analyzer.',
            ],
            [
                'field' => 'framework_behavior',
                'reason' => 'No Laravel, Symfony, WordPress, or other framework behavior is inferred.',
            ],
        ],
    ];
}

/** @param list<string> $command
 *  @return array{exit: int, stdout: string, stderr: string}
 */
function map_php_process(array $command, string $cwd): array
{
    $descriptors = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w'],
    ];
    $process = @proc_open($command, $descriptors, $pipes, $cwd);
    if (!is_resource($process)) {
        return ['exit' => 127, 'stdout' => '', 'stderr' => 'could not start process'];
    }
    fclose($pipes[0]);
    $stdout = stream_get_contents($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    return ['exit' => proc_close($process), 'stdout' => $stdout ?: '', 'stderr' => $stderr ?: ''];
}

/** @return list<string>|null */
function map_php_resolve_command(string $requested): ?array
{
    if (str_contains($requested, DIRECTORY_SEPARATOR)) {
        return is_file($requested) && is_executable($requested) ? [realpath($requested) ?: $requested] : null;
    }
    $path = getenv('PATH') ?: '';
    foreach (explode(PATH_SEPARATOR, $path) as $directory) {
        if ($directory === '') {
            continue;
        }
        $candidate = $directory . DIRECTORY_SEPARATOR . $requested;
        if (is_file($candidate) && is_executable($candidate)) {
            return [realpath($candidate) ?: $candidate];
        }
    }
    return null;
}

/** @param list<string> $composer */
function map_php_composer_version(array $composer, string $root): string
{
    $result = map_php_process([...$composer, '--version'], $root);
    if ($result['exit'] !== 0) {
        throw new MapPhpTerminal(
            'unsupported', 'composer_tool_unusable', 'Composer could not report a version: ' . map_php_process_summary($result),
        );
    }
    if (preg_match('/Composer version\s+(\d+(?:\.\d+){1,2})/i', $result['stdout'] . "\n" . $result['stderr'], $match) !== 1) {
        throw new MapPhpTerminal(
            'unsupported', 'composer_version_unknown', 'Could not parse Composer version output.',
        );
    }
    return $match[1];
}

/** @param array{exit: int, stdout: string, stderr: string} $result */
function map_php_process_summary(array $result): string
{
    $text = trim($result['stderr']) !== '' ? trim($result['stderr']) : trim($result['stdout']);
    $line = preg_split('/\R/', $text)[0] ?? 'no process output';
    return 'exit ' . $result['exit'] . ': ' . $line;
}

/** @param array<string, mixed> $manifest
 *  @return list<array{prefix: string, root: string, path: string}>
 */
function map_php_psr4_mappings(string $root, array $manifest): array
{
    $psr4 = $manifest['autoload']['psr-4'] ?? null;
    if (!is_array($psr4) || $psr4 === []) {
        throw new MapPhpTerminal(
            'unsupported', 'psr4_autoload_missing', 'Composer autoload.psr-4 is required for PHP map v1.',
        );
    }
    $mappings = [];
    foreach ($psr4 as $prefix => $rawPaths) {
        if (!is_string($prefix) || $prefix === '' || !str_ends_with($prefix, '\\')) {
            throw new MapPhpTerminal(
                'unsupported', 'psr4_autoload_invalid', 'Composer PSR-4 prefixes must be non-empty and end with a namespace separator.',
            );
        }
        $paths = is_array($rawPaths) ? $rawPaths : [$rawPaths];
        foreach ($paths as $path) {
            if (!is_string($path) || $path === '') {
                throw new MapPhpTerminal(
                    'unsupported', 'psr4_autoload_invalid', 'Composer PSR-4 paths must be non-empty strings.',
                );
            }
            try {
                $absolute = map_php_resolve_inside($root, $path, 'Composer PSR-4 path');
            } catch (InvalidArgumentException $error) {
                throw new MapPhpTerminal('unsupported', 'unsafe_psr4_root', $error->getMessage());
            }
            if (map_php_path_has_symlink($root, $absolute)) {
                throw new MapPhpTerminal(
                    'unsupported', 'unsafe_psr4_root', 'Composer PSR-4 source roots must not traverse a symbolic link.',
                );
            }
            $mappings[] = [
                'prefix' => $prefix,
                'root' => $absolute,
                'path' => map_php_relative($root, $absolute),
            ];
        }
    }
    usort($mappings, static fn (array $left, array $right): int => [$left['prefix'], $left['path']]
        <=> [$right['prefix'], $right['path']]);
    return $mappings;
}

function map_php_is_excluded(string $root, string $path): bool
{
    $parts = explode('/', map_php_relative($root, $path));
    foreach ($parts as $part) {
        if (in_array(strtolower($part), MAP_PHP_EXCLUDED_DIRECTORIES, true)) {
            return true;
        }
    }
    $basename = end($parts) ?: '';
    return preg_match('/(?:Test|\.test|\.stub)\.php\z/i', $basename) === 1;
}

function map_php_is_generated(string $path): bool
{
    $name = basename($path);
    if (preg_match('/(?:Generated|Proxy|Container)\.php\z/i', $name) === 1) {
        return true;
    }
    $contents = file_get_contents($path, false, null, 0, 8192);
    return is_string($contents) && preg_match('/(?:@generated|code generated|do not edit)/i', $contents) === 1;
}

/** @param list<array{prefix: string, root: string, path: string}> $mappings
 *  @return array{eligible: list<array{absolute: string, file: string}>, excluded: list<array{absolute: string, file: string}>, generated: list<array{absolute: string, file: string}>, symlinked: list<array{absolute: string, file: string}>, missing_roots: list<string>}
 */
function map_php_collect_sources(string $root, array $mappings): array
{
    $result = [
        'eligible' => [], 'excluded' => [], 'generated' => [], 'symlinked' => [], 'missing_roots' => [],
    ];
    $seen = [];
    foreach ($mappings as $mapping) {
        if (!is_dir($mapping['root'])) {
            $result['missing_roots'][] = $mapping['path'];
            continue;
        }
        map_php_scan_directory($root, $mapping['root'], $result, $seen);
    }
    foreach (['eligible', 'excluded', 'generated', 'symlinked'] as $key) {
        usort($result[$key], static fn (array $left, array $right): int => $left['file'] <=> $right['file']);
    }
    $result['missing_roots'] = array_values(array_unique($result['missing_roots']));
    sort($result['missing_roots'], SORT_STRING);
    return $result;
}

/** @param array<string, list<array{absolute: string, file: string}>|list<string>> $result
 *  @param array<string, true> $seen
 */
function map_php_scan_directory(string $root, string $directory, array &$result, array &$seen): void
{
    $entries = scandir($directory);
    if ($entries === false) {
        return;
    }
    foreach ($entries as $entry) {
        if ($entry === '.' || $entry === '..') {
            continue;
        }
        $path = $directory . DIRECTORY_SEPARATOR . $entry;
        $file = map_php_relative($root, $path);
        if (is_link($path)) {
            $result['symlinked'][] = ['absolute' => $path, 'file' => $file];
            continue;
        }
        if (is_dir($path)) {
            if (map_php_is_excluded($root, $path)) {
                continue;
            }
            map_php_scan_directory($root, $path, $result, $seen);
            continue;
        }
        if (!is_file($path) || !str_ends_with(strtolower($entry), '.php') || isset($seen[$path])) {
            continue;
        }
        $seen[$path] = true;
        $record = ['absolute' => $path, 'file' => $file];
        if (map_php_is_excluded($root, $path)) {
            $result['excluded'][] = $record;
        } elseif (map_php_is_generated($path)) {
            $result['generated'][] = $record;
        } else {
            $result['eligible'][] = $record;
        }
    }
}

/** @param list<array{absolute: string, file: string}> $sources */
function map_php_lint_sources(string $root, array $sources): void
{
    foreach ($sources as $source) {
        $result = map_php_process([PHP_BINARY, '-l', $source['absolute']], $root);
        if ($result['exit'] !== 0) {
            throw new MapPhpTerminal(
                'failed',
                'syntax_error',
                'PHP syntax error in ' . $source['file'] . ': ' . map_php_process_summary($result),
                2,
            );
        }
    }
}

/** @return array{absolute: string, file: string, declarations: list<array<string, mixed>>, imports: list<array<string, mixed>>} */
function map_php_parse_source(string $path, string $file): array
{
    $contents = file_get_contents($path);
    if ($contents === false) {
        throw new RuntimeException("could not read {$file}");
    }
    $tokens = token_get_all($contents);
    $namespace = '';
    $namespaceDepth = 0;
    $braceDepth = 0;
    $declarations = [];
    $imports = [];
    for ($index = 0; $index < count($tokens); $index++) {
        $token = $tokens[$index];
        if ($token === '{') {
            $braceDepth++;
            continue;
        }
        if ($token === '}') {
            $braceDepth = max(0, $braceDepth - 1);
            if ($braceDepth < $namespaceDepth) {
                $namespace = '';
                $namespaceDepth = 0;
            }
            continue;
        }
        if (!is_array($token)) {
            continue;
        }
        [$kind, $text, $line] = $token;
        if ($kind === T_NAMESPACE) {
            [$raw, $end, $terminator] = map_php_collect_until($tokens, $index + 1, [';', '{']);
            $namespace = trim(str_replace([' ', "\t", "\n"], '', $raw), '\\');
            $namespaceDepth = $terminator === '{' ? $braceDepth + 1 : $braceDepth;
            $index = $end - 1;
            continue;
        }
        if ($kind === T_USE && $braceDepth === $namespaceDepth) {
            [$raw, $end] = map_php_collect_until($tokens, $index + 1, [';']);
            foreach (map_php_parse_use_statement($raw, $line) as $import) {
                $imports[] = $import;
            }
            $index = $end;
            continue;
        }
        if (in_array($kind, [T_CLASS, T_INTERFACE, T_TRAIT, T_ENUM], true) && $braceDepth === $namespaceDepth) {
            $nameToken = map_php_next_name_token($tokens, $index + 1);
            if ($nameToken === null) {
                continue;
            }
            $name = $nameToken[1];
            $qualified = $namespace === '' ? $name : $namespace . '\\' . $name;
            $declarations[] = [
                'name' => $name,
                'qualified_name' => $qualified,
                'kind' => match ($kind) {
                    T_INTERFACE => 'interface', T_TRAIT => 'trait', T_ENUM => 'enum', default => 'class',
                },
                'file' => $file,
                'absolute' => $path,
                'line' => $line,
            ];
        }
    }
    return ['absolute' => $path, 'file' => $file, 'declarations' => $declarations, 'imports' => $imports];
}

/** @param list<int|string|array{int, string, int}> $tokens
 *  @param list<string> $terminators
 *  @return array{string, int, string}
 */
function map_php_collect_until(array $tokens, int $start, array $terminators): array
{
    $raw = '';
    for ($index = $start; $index < count($tokens); $index++) {
        $token = $tokens[$index];
        if (is_string($token) && in_array($token, $terminators, true)) {
            return [$raw, $index, $token];
        }
        $raw .= is_array($token) ? $token[1] : $token;
    }
    return [$raw, count($tokens), ''];
}

/** @param list<int|string|array{int, string, int}> $tokens
 *  @return array{int, string, int}|null
 */
function map_php_next_name_token(array $tokens, int $start): ?array
{
    for ($index = $start; $index < count($tokens); $index++) {
        $token = $tokens[$index];
        if (!is_array($token)) {
            return null;
        }
        if (in_array($token[0], [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT, T_FINAL, T_ABSTRACT, T_READONLY], true)) {
            continue;
        }
        return $token[0] === T_STRING ? $token : null;
    }
    return null;
}

/** @return list<array{import: string, alias: string, line: int}> */
function map_php_parse_use_statement(string $raw, int $line): array
{
    $raw = trim($raw);
    if ($raw === '' || preg_match('/\A(?:function|const)\b/i', $raw) === 1) {
        return [];
    }
    $items = [];
    if (preg_match('/\A(.+\\\\)\{(.+)\}\z/s', $raw, $group) === 1) {
        foreach (explode(',', $group[2]) as $item) {
            $items[] = $group[1] . trim($item);
        }
    } else {
        $items = explode(',', $raw);
    }
    $imports = [];
    foreach ($items as $item) {
        $item = trim($item);
        if ($item === '') {
            continue;
        }
        $alias = null;
        if (preg_match('/\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\z/i', $item, $match) === 1) {
            $alias = $match[1];
            $item = trim(substr($item, 0, -strlen($match[0])));
        }
        $import = trim($item, " \\t\\r\\n\\\\");
        if ($import === '') {
            continue;
        }
        $parts = explode('\\', $import);
        $imports[] = [
            'import' => $import,
            'alias' => $alias ?? (end($parts) ?: $import),
            'line' => $line,
        ];
    }
    return $imports;
}

/** @param list<array{prefix: string, root: string, path: string}> $mappings
 *  @param array<string, mixed> $declaration
 *  @return array<string, mixed>
 */
function map_php_public_symbol(array $declaration, array $mappings, string $root): array
{
    $expected = map_php_expected_paths($declaration['qualified_name'], $mappings, $root);
    $relative = $declaration['file'];
    return [
        'name' => $declaration['name'],
        'qualified_name' => $declaration['qualified_name'],
        'kind' => $declaration['kind'],
        'file' => $relative,
        'line' => $declaration['line'],
        'resolution' => in_array($relative, $expected, true)
            ? 'composer_psr4_declared' : 'unverified_psr4_declaration',
    ];
}

/** @param list<array{prefix: string, root: string, path: string}> $mappings
 *  @return list<string>
 */
function map_php_expected_paths(string $qualified, array $mappings, string $root): array
{
    $paths = [];
    foreach ($mappings as $mapping) {
        if (!str_starts_with($qualified, $mapping['prefix'])) {
            continue;
        }
        $suffix = substr($qualified, strlen($mapping['prefix']));
        if ($suffix === '') {
            continue;
        }
        $paths[] = map_php_relative(
            $root,
            $mapping['root'] . DIRECTORY_SEPARATOR . str_replace('\\', DIRECTORY_SEPARATOR, $suffix) . '.php',
        );
    }
    sort($paths, SORT_STRING);
    return array_values(array_unique($paths));
}

/** @param array{absolute: string, file: string, declarations: list<array<string, mixed>>, imports: list<array<string, mixed>>} $source
 *  @param array{import: string, alias: string, line: int} $import
 *  @param array<string, array<string, mixed>> $classes
 *  @param list<array{prefix: string, root: string, path: string}> $mappings
 *  @return array<string, mixed>
 */
function map_php_import_edge(array $source, array $import, array $classes, array $mappings, string $root): array
{
    $from = $source['declarations'][0]['qualified_name'] ?? $source['file'];
    $expected = map_php_expected_paths($import['import'], $mappings, $root);
    if ($expected === []) {
        return [
            'from_symbol' => $from,
            'file' => $source['file'],
            'line' => $import['line'],
            'import' => $import['import'],
            'alias' => $import['alias'],
            'resolution' => 'external_import',
        ];
    }
    $declaration = $classes[$import['import']] ?? null;
    if ($declaration === null || !in_array($declaration['file'], $expected, true)) {
        return [
            'from_symbol' => $from,
            'file' => $source['file'],
            'line' => $import['line'],
            'import' => $import['import'],
            'alias' => $import['alias'],
            'resolution' => 'unresolved_first_party_psr4',
        ];
    }
    return [
        'from_symbol' => $from,
        'file' => $source['file'],
        'line' => $import['line'],
        'import' => $import['import'],
        'alias' => $import['alias'],
        'target_symbol' => $declaration['qualified_name'],
        'target_file' => $declaration['file'],
        'resolution' => 'composer_psr4_first_party',
    ];
}

/** @param array<string, mixed> $edge
 *  @return array<string, mixed>
 */
function map_php_unresolved_edge(array $edge): array
{
    return [
        'from_symbol' => $edge['from_symbol'],
        'file' => $edge['file'],
        'line' => $edge['line'],
        'import' => $edge['import'],
        'alias' => $edge['alias'],
        'resolution' => $edge['resolution'],
    ];
}

/** @param list<array<string, mixed>> $edges */
function map_php_sort_edges(array &$edges): void
{
    usort($edges, static fn (array $left, array $right): int => [
        $left['file'], $left['line'], $left['import'], $left['from_symbol'],
    ] <=> [
        $right['file'], $right['line'], $right['import'], $right['from_symbol'],
    ]);
}

/** @param array<string, mixed> $options
 *  @return array<string, mixed>
 */
function map_php_terminal_payload(array $options, MapPhpTerminal $terminal): array
{
    return [
        'schema_version' => 1,
        'status' => $terminal->status,
        'failure_kind' => $terminal->kind,
        'message' => $terminal->getMessage(),
        'language' => 'php',
        'analyzer' => 'native-php-lint+composer-psr4-static',
        'target' => ['path' => map_php_relative($options['root'], $options['target'])],
        'counts' => [
            'source_files' => 0,
            'declared_symbols' => 0,
            'outbound_imports' => 0,
            'inbound_imports' => 0,
            'external_imports' => 0,
            'unresolved_imports' => 0,
        ],
        'completeness' => [
            'source_inventory' => 'unavailable',
            'php_syntax' => 'unavailable',
            'composer_manifest' => 'unavailable',
            'composer_psr4_static_resolution' => 'unavailable',
            'dynamic_calls_and_types' => 'unavailable',
        ],
        'exported_surface' => [],
        'outbound_imports' => [],
        'inbound_imports' => [],
        'external_imports' => [],
        'unresolved_imports' => [],
        'unavailable_fields' => [[
            'field' => 'dynamic_call_targets',
            'reason' => 'Terminal result: no dynamic PHP call-target resolution is claimed.',
        ]],
    ];
}

/** @param array<string, mixed> $options
 *  @param array<string, mixed> $payload
 */
function map_php_write_artifacts(array $options, array $payload): void
{
    $json = json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n";
    map_php_write_atomic($options['root'], $options['evidence'], $json);
    map_php_write_atomic($options['root'], $options['output'], map_php_render_document($payload));
}

/** @param array<string, mixed> $payload */
function map_php_render_document(array $payload): string
{
    $target = $payload['target']['path'] ?? 'unavailable';
    $out = "---\n";
    $out .= 'subsystem: ' . ($payload['target']['path'] ?? 'unknown') . "\n";
    $out .= "language: php\n";
    $out .= 'status: ' . $payload['status'] . "\n";
    $out .= "---\n\n";
    $out .= '# ' . ($payload['target']['path'] ?? 'PHP subsystem') . "\n\n";
    $out .= 'Status: **' . $payload['status'] . "**\n\n";
    if (in_array($payload['status'], ['failed', 'unsupported'], true)) {
        $out .= 'Failure kind: `' . ($payload['failure_kind'] ?? 'unavailable') . "`\n\n";
        $out .= $payload['message'] . "\n";
        return $out;
    }
    if ($payload['status'] === 'partial') {
        $out .= 'Failure kind: `' . ($payload['failure_kind'] ?? 'unavailable') . "`\n\n";
        $out .= $payload['message'] . "\n\n";
    }
    $out .= 'Composer PSR-4 static map for `' . $target . '`, after native PHP lint and Composer validation.' . "\n\n";
    $out .= "## Source inventory\n\n";
    $out .= '- Target files: ' . $payload['counts']['source_files'] . "\n";
    foreach ($payload['target']['eligible_files'] as $file) {
        $out .= '- `' . $file . "`\n";
    }
    $out .= "\n## Exported surface\n\n";
    if ($payload['exported_surface'] === []) {
        $out .= "No class-like declarations found.\n";
    }
    foreach ($payload['exported_surface'] as $symbol) {
        $out .= '- `' . $symbol['qualified_name'] . '` (' . $symbol['kind'] . ') — `' . $symbol['file'] . "`\n";
    }
    $out .= "\n## Composer PSR-4 static resolution\n\n";
    foreach (['outbound_imports' => 'Outbound', 'inbound_imports' => 'Inbound'] as $key => $label) {
        $out .= '**' . $label . " imports:**\n";
        if ($payload[$key] === []) {
            $out .= "- none\n";
        }
        foreach ($payload[$key] as $edge) {
            $out .= '- `' . $edge['from_symbol'] . '` → `' . $edge['target_symbol'] . '` (`' . $edge['file'] . "`)\n";
        }
    }
    if ($payload['unresolved_imports'] !== []) {
        $out .= "\n**Unresolved first-party imports:**\n";
        foreach ($payload['unresolved_imports'] as $edge) {
            $out .= '- `' . $edge['import'] . '` from `' . $edge['file'] . "`\n";
        }
    }
    $out .= "\n## Boundaries\n\n";
    $out .= '- This map does not resolve dynamic calls, runtime class loading, or PHP types.\n';
    $out .= '- Composer PSR-4 class-file candidates are static project facts, not framework behavior or call-target semantics.\n';
    $out .= '- Run project-owned PHPStan or Psalm separately for analyzer-backed type/reference claims.\n';
    return $out;
}

function map_php_write_atomic(string $root, string $path, string $contents): void
{
    if (map_php_path_has_symlink($root, $path)) {
        throw new RuntimeException('artifact output must not traverse a symbolic link');
    }
    $directory = dirname($path);
    if (!is_dir($directory) && !mkdir($directory, 0775, true) && !is_dir($directory)) {
        throw new RuntimeException("could not create artifact directory {$directory}");
    }
    if (map_php_path_has_symlink($root, $path)) {
        throw new RuntimeException('artifact output must not traverse a symbolic link');
    }
    $temporary = tempnam($directory, basename($path) . '.tmp-');
    if ($temporary === false) {
        throw new RuntimeException("could not create temporary artifact for {$path}");
    }
    try {
        if (file_put_contents($temporary, $contents) === false) {
            throw new RuntimeException("could not write temporary artifact for {$path}");
        }
        if (!rename($temporary, $path)) {
            throw new RuntimeException("could not replace artifact {$path}");
        }
    } finally {
        if (is_file($temporary)) {
            unlink($temporary);
        }
    }
}

function map_php_main(array $argv): int
{
    $options = null;
    try {
        $options = map_php_parse_options($argv);
        map_php_validate_artifact_paths($options);
        map_php_write_artifacts($options, map_php_run($options));
        return 0;
    } catch (MapPhpTerminal $terminal) {
        fwrite(STDERR, '[map_php] ' . $terminal->kind . ': ' . $terminal->getMessage() . "\n");
        if ($terminal->writeArtifacts && is_array($options)) {
            try {
                map_php_write_artifacts($options, map_php_terminal_payload($options, $terminal));
            } catch (Throwable $writeError) {
                fwrite(STDERR, '[map_php] artifact_write_failed: ' . $writeError->getMessage() . "\n");
                return 2;
            }
        }
        return $terminal->exitCode;
    } catch (InvalidArgumentException $error) {
        fwrite(STDERR, '[map_php] ' . $error->getMessage() . "\n");
        return 2;
    } catch (Throwable $error) {
        fwrite(STDERR, '[map_php] unexpected_error: ' . $error->getMessage() . "\n");
        if (is_array($options)) {
            try {
                map_php_write_artifacts(
                    $options,
                    map_php_terminal_payload(
                        $options,
                        new MapPhpTerminal('failed', 'unexpected_error', $error->getMessage(), 2),
                    ),
                );
            } catch (Throwable $writeError) {
                fwrite(STDERR, '[map_php] artifact_write_failed: ' . $writeError->getMessage() . "\n");
            }
        }
        return 2;
    }
}

exit(map_php_main($argv));
