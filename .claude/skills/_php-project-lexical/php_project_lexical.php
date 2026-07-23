<?php

declare(strict_types=1);

/**
 * PHP-local project/lexical facts for five read-only skill consumers.
 *
 * The producer owns source roles, PHP/Composer probes, Composer validation,
 * php -l and token_get_all(..., TOKEN_PARSE) evidence, lexical declaration and
 * function-body spans, fingerprints, lifecycle writes, and source preservation.
 * Consumers retain their own final artifact schemas and interpretations. These
 * facts do not establish symbol identity, types, resolved calls, framework
 * behavior, runtime behavior, or safe rewrites.
 */

const PPL_TEST_DIRECTORIES = ['test', 'tests', 'spec', 'specs', 'fixtures', 'testdata'];
const PPL_GENERATED_DIRECTORIES = ['generated', 'gen'];
const PPL_BUILD_DIRECTORIES = ['build', 'dist', 'out', 'cache', 'coverage'];
const PPL_REPORT_DIRECTORIES = ['report', 'reports'];
const PPL_TOOLING_DIRECTORIES = ['.agents', '.claude', '.git', '.idea', '.vscode'];

/** @return array<string, string> */
function ppl_cli(array $argv, array $required, array $defaults = []): array
{
    $allowed = array_values(array_unique([...$required, ...array_keys($defaults)]));
    $arguments = array_slice($argv, 1);
    if (count($arguments) % 2 !== 0) {
        throw new InvalidArgumentException('options must be supplied as --name value pairs');
    }
    $values = $defaults;
    $seen = [];
    for ($index = 0; $index < count($arguments); $index += 2) {
        $flag = $arguments[$index];
        if (!str_starts_with($flag, '--')) {
            throw new InvalidArgumentException("unexpected positional argument: {$flag}");
        }
        $name = substr($flag, 2);
        if (!in_array($name, $allowed, true) || isset($seen[$name])) {
            throw new InvalidArgumentException("unknown or duplicate option: {$flag}");
        }
        $seen[$name] = true;
        $values[$name] = $arguments[$index + 1];
    }
    foreach ($required as $name) {
        if (!array_key_exists($name, $values) || $values[$name] === '') {
            throw new InvalidArgumentException("missing required option: --{$name}");
        }
    }
    return $values;
}

function ppl_normalize_path(string $path): string
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
    return $prefix . ($absolute ? DIRECTORY_SEPARATOR : '') . implode(DIRECTORY_SEPARATOR, $parts);
}

function ppl_is_absolute(string $path): bool
{
    return str_starts_with($path, DIRECTORY_SEPARATOR)
        || preg_match('/\A[A-Za-z]:[\\\\\/]/', $path) === 1;
}

function ppl_is_inside(string $root, string $candidate): bool
{
    $root = rtrim(ppl_normalize_path($root), DIRECTORY_SEPARATOR);
    $candidate = ppl_normalize_path($candidate);
    return $candidate === $root || str_starts_with($candidate, $root . DIRECTORY_SEPARATOR);
}

function ppl_project_root(string $supplied): string
{
    if (!is_dir($supplied) || is_link($supplied)) {
        throw new InvalidArgumentException('project root must be a regular non-symlink directory');
    }
    $root = realpath($supplied);
    if ($root === false) {
        throw new InvalidArgumentException('project root could not be resolved');
    }
    return $root;
}

function ppl_inside_path(string $root, string $supplied, string $label): string
{
    $candidate = ppl_is_absolute($supplied) ? $supplied : $root . DIRECTORY_SEPARATOR . $supplied;
    $candidate = ppl_normalize_path($candidate);
    $probe = $candidate;
    $tail = [];
    while (!file_exists($probe) && !is_link($probe) && dirname($probe) !== $probe) {
        array_unshift($tail, basename($probe));
        $probe = dirname($probe);
    }
    $resolvedProbe = realpath($probe);
    if ($resolvedProbe !== false) {
        $candidate = ppl_normalize_path(
            $resolvedProbe . ($tail === [] ? '' : DIRECTORY_SEPARATOR . implode(DIRECTORY_SEPARATOR, $tail)),
        );
    }
    if (!ppl_is_inside($root, $candidate)) {
        throw new InvalidArgumentException("{$label} must stay inside project root");
    }
    return $candidate;
}

function ppl_relative(string $root, string $path): string
{
    $relative = ltrim(substr(ppl_normalize_path($path), strlen(rtrim($root, DIRECTORY_SEPARATOR))), DIRECTORY_SEPARATOR);
    return str_replace(DIRECTORY_SEPARATOR, '/', $relative);
}

function ppl_has_symlink_component(string $root, string $path): bool
{
    if (!ppl_is_inside($root, $path)) {
        return true;
    }
    $current = rtrim($root, DIRECTORY_SEPARATOR);
    $relative = ppl_relative($root, $path);
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

function ppl_assert_output(string $root, string $path): void
{
    if (!ppl_is_inside($root, $path) || $path === $root) {
        throw new InvalidArgumentException('artifact path must stay below project root');
    }
    if (ppl_has_symlink_component($root, $path)) {
        throw new InvalidArgumentException('artifact path must not traverse a symbolic link');
    }
}

function ppl_atomic_text(string $path, string $text): void
{
    $directory = dirname($path);
    if (!is_dir($directory) && !mkdir($directory, 0777, true) && !is_dir($directory)) {
        throw new RuntimeException("could not create artifact directory: {$directory}");
    }
    $temporary = tempnam($directory, '.' . basename($path) . '.');
    if ($temporary === false) {
        throw new RuntimeException("could not create temporary artifact for {$path}");
    }
    try {
        if (file_put_contents($temporary, $text, LOCK_EX) === false || !rename($temporary, $path)) {
            throw new RuntimeException("could not publish artifact: {$path}");
        }
    } finally {
        if (is_file($temporary)) {
            unlink($temporary);
        }
    }
}

function ppl_atomic_json(string $path, array $payload): void
{
    ppl_atomic_text(
        $path,
        json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n",
    );
}

function ppl_clear_artifacts(array $paths): void
{
    foreach ($paths as $path) {
        if (is_file($path) || is_link($path)) {
            unlink($path);
        }
    }
}

/** @return array{returncode: int, stdout: string, stderr: string} */
function ppl_process(array $command, string $cwd): array
{
    $descriptors = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w'],
    ];
    $pipes = [];
    $process = @proc_open($command, $descriptors, $pipes, $cwd, null, ['bypass_shell' => true]);
    if (!is_resource($process)) {
        return ['returncode' => 124, 'stdout' => '', 'stderr' => 'process could not be started'];
    }
    fclose($pipes[0]);
    $stdout = stream_get_contents($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    $returncode = proc_close($process);
    return [
        'returncode' => $returncode,
        'stdout' => $stdout === false ? '' : $stdout,
        'stderr' => $stderr === false ? '' : $stderr,
    ];
}

function ppl_resolve_command(string $configured): ?string
{
    if (ppl_is_absolute($configured) || str_contains($configured, DIRECTORY_SEPARATOR)) {
        return is_file($configured) && is_executable($configured) ? realpath($configured) ?: $configured : null;
    }
    foreach (explode(PATH_SEPARATOR, getenv('PATH') ?: '') as $directory) {
        $candidate = rtrim($directory === '' ? '.' : $directory, DIRECTORY_SEPARATOR)
            . DIRECTORY_SEPARATOR . $configured;
        if (is_file($candidate) && is_executable($candidate)) {
            return realpath($candidate) ?: $candidate;
        }
    }
    return null;
}

/** @return array<string, mixed> */
function ppl_probe_tool(string $configured, string $name, string $minimum, string $root): array
{
    $path = ppl_resolve_command($configured);
    if ($path === null) {
        return ['state' => 'missing', 'failure_kind' => "{$name}-tool-missing", 'minimum_version' => $minimum];
    }
    $result = ppl_process([$path, '--version'], $root);
    if ($result['returncode'] !== 0) {
        return [
            'state' => 'failed',
            'path' => $path,
            'failure_kind' => "{$name}-version-failed",
            'detail' => trim($result['stderr'] . "\n" . $result['stdout']),
            'minimum_version' => $minimum,
        ];
    }
    $text = $result['stdout'] . "\n" . $result['stderr'];
    $pattern = $name === 'php'
        ? '/\bPHP\s+(\d+\.\d+(?:\.\d+)?)/i'
        : '/\bComposer(?:\s+version)?\s+(\d+\.\d+(?:\.\d+)?)/i';
    if (preg_match($pattern, $text, $match) !== 1) {
        return [
            'state' => 'failed',
            'path' => $path,
            'failure_kind' => "{$name}-version-unrecognized",
            'detail' => trim($text),
            'minimum_version' => $minimum,
        ];
    }
    $version = $match[1];
    return [
        'state' => version_compare($version, $minimum, '>=') ? 'ready' : 'too-old',
        'path' => $path,
        'version' => $version,
        'minimum_version' => $minimum,
        ...(version_compare($version, $minimum, '>=') ? [] : ['failure_kind' => "{$name}-version-too-old"]),
    ];
}

function ppl_status_merge(string $current, string $candidate): string
{
    $priority = ['complete' => 0, 'partial' => 1, 'failed' => 2];
    return $priority[$candidate] > $priority[$current] ? $candidate : $current;
}

function ppl_hash(string $content): string
{
    return hash('sha256', $content);
}

/** @return array<string, mixed> */
function ppl_span(string $source, int $start, int $end): array
{
    $beforeStart = substr($source, 0, $start);
    $beforeEnd = substr($source, 0, $end);
    $startLine = substr_count($beforeStart, "\n") + 1;
    $endLine = substr_count($beforeEnd, "\n") + 1;
    $startColumn = $start - (strrpos($beforeStart, "\n") === false ? -1 : strrpos($beforeStart, "\n"));
    $endColumn = $end - (strrpos($beforeEnd, "\n") === false ? -1 : strrpos($beforeEnd, "\n"));
    return [
        'start_byte' => $start,
        'end_byte' => $end,
        'start' => ['line' => $startLine, 'column' => $startColumn],
        'end' => ['line' => $endLine, 'column' => $endColumn],
    ];
}

/** @return list<array{id: int|null, text: string, line: int, start: int, end: int}> */
function ppl_token_records(string $source): array
{
    $tokens = token_get_all($source, TOKEN_PARSE);
    $records = [];
    $offset = 0;
    $line = 1;
    foreach ($tokens as $token) {
        $id = is_array($token) ? $token[0] : null;
        $text = is_array($token) ? $token[1] : $token;
        $tokenLine = is_array($token) ? $token[2] : $line;
        $end = $offset + strlen($text);
        $records[] = ['id' => $id, 'text' => $text, 'line' => $tokenLine, 'start' => $offset, 'end' => $end];
        $line += substr_count($text, "\n");
        $offset = $end;
    }
    return $records;
}

function ppl_significant(?int $id): bool
{
    return $id === null || !in_array($id, [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT], true);
}

function ppl_next_significant(array $tokens, int $index): ?int
{
    for ($cursor = $index + 1; $cursor < count($tokens); $cursor++) {
        if (ppl_significant($tokens[$cursor]['id'])) {
            return $cursor;
        }
    }
    return null;
}

function ppl_previous_significant(array $tokens, int $index): ?int
{
    for ($cursor = $index - 1; $cursor >= 0; $cursor--) {
        if (ppl_significant($tokens[$cursor]['id'])) {
            return $cursor;
        }
    }
    return null;
}

function ppl_matching_brace(array $tokens, int $open): ?int
{
    $depth = 0;
    for ($index = $open; $index < count($tokens); $index++) {
        if ($tokens[$index]['text'] === '{') {
            $depth++;
        } elseif ($tokens[$index]['text'] === '}') {
            $depth--;
            if ($depth === 0) {
                return $index;
            }
        }
    }
    return null;
}

/** @return list<int> */
function ppl_brace_depths(array $tokens): array
{
    $depths = [];
    $depth = 0;
    foreach ($tokens as $index => $token) {
        $depths[$index] = $depth;
        if ($token['text'] === '{') {
            $depth++;
        } elseif ($token['text'] === '}') {
            $depth = max(0, $depth - 1);
        }
    }
    return $depths;
}

function ppl_namespace(array $tokens): string
{
    foreach ($tokens as $index => $token) {
        if ($token['id'] !== T_NAMESPACE) {
            continue;
        }
        $parts = [];
        for ($cursor = $index + 1; $cursor < count($tokens); $cursor++) {
            $candidate = $tokens[$cursor];
            if ($candidate['text'] === ';' || $candidate['text'] === '{') {
                return trim(implode('', $parts), '\\');
            }
            if ($candidate['id'] !== T_WHITESPACE) {
                $parts[] = $candidate['text'];
            }
        }
    }
    return '';
}

/** @return array{declarations: list<array<string, mixed>>, functions: list<array<string, mixed>>, unresolved: list<array<string, string>>, limitations: list<string>} */
function ppl_lexical_facts(string $relative, string $source): array
{
    $tokens = ppl_token_records($source);
    $depths = ppl_brace_depths($tokens);
    $namespace = ppl_namespace($tokens);
    $namespaceIndexes = [];
    $namespaceBraced = false;
    foreach ($tokens as $index => $token) {
        if ($token['id'] !== T_NAMESPACE) {
            continue;
        }
        $namespaceIndexes[] = $index;
        for ($cursor = $index + 1; $cursor < count($tokens); $cursor++) {
            if ($tokens[$cursor]['text'] === '{') {
                $namespaceBraced = true;
                break;
            }
            if ($tokens[$cursor]['text'] === ';') {
                break;
            }
        }
    }
    $baseDepth = $namespaceBraced ? 1 : 0;
    $limitations = [];
    if (count($namespaceIndexes) > 1) {
        $limitations[] = 'multiple-namespaces-unresolved';
    }
    if ($namespaceBraced) {
        $limitations[] = 'braced-namespace-partial';
    }
    $types = [];
    $typeIds = [T_CLASS => 'class', T_INTERFACE => 'interface', T_TRAIT => 'trait'];
    if (defined('T_ENUM')) {
        $typeIds[constant('T_ENUM')] = 'enum';
    }
    foreach ($tokens as $index => $token) {
        if ($token['id'] === null || !array_key_exists($token['id'], $typeIds)) {
            continue;
        }
        $previous = ppl_previous_significant($tokens, $index);
        if ($previous !== null && $tokens[$previous]['id'] === T_NEW) {
            continue;
        }
        if ($depths[$index] !== $baseDepth) {
            continue;
        }
        $nameIndex = ppl_next_significant($tokens, $index);
        if ($nameIndex === null || $tokens[$nameIndex]['id'] !== T_STRING) {
            continue;
        }
        $open = null;
        for ($cursor = $nameIndex + 1; $cursor < count($tokens); $cursor++) {
            if ($tokens[$cursor]['text'] === '{') {
                $open = $cursor;
                break;
            }
            if ($tokens[$cursor]['text'] === ';') {
                break;
            }
        }
        if ($open === null || ($close = ppl_matching_brace($tokens, $open)) === null) {
            continue;
        }
        $name = $tokens[$nameIndex]['text'];
        $types[] = [
            'file' => $relative,
            'kind' => $typeIds[$token['id']],
            'symbol' => $name,
            'qualified_symbol' => $namespace === '' ? $name : $namespace . '\\' . $name,
            'body_open' => $open,
            'body_close' => $close,
            'span' => ppl_span($source, $token['start'], $tokens[$close]['end']),
            'spelling_sha256' => ppl_hash(substr($source, $token['start'], $tokens[$close]['end'] - $token['start'])),
            'source_sha256' => ppl_hash($source),
        ];
    }

    $functions = [];
    foreach ($tokens as $index => $token) {
        if ($token['id'] !== T_FUNCTION) {
            continue;
        }
        $nameIndex = ppl_next_significant($tokens, $index);
        if ($nameIndex !== null && $tokens[$nameIndex]['text'] === '&') {
            $nameIndex = ppl_next_significant($tokens, $nameIndex);
        }
        if ($nameIndex === null || $tokens[$nameIndex]['id'] !== T_STRING) {
            continue;
        }
        $owner = null;
        foreach ($types as $type) {
            if ($index > $type['body_open']
                && $index < $type['body_close']
                && $depths[$index] === $depths[$type['body_open']] + 1) {
                $owner = $type['symbol'];
                break;
            }
        }
        if ($owner === null && $depths[$index] !== $baseDepth) {
            continue;
        }
        if ($owner !== null) {
            $visibility = 'public';
            for ($cursor = $index - 1; $cursor >= 0; $cursor--) {
                $candidate = $tokens[$cursor];
                if (in_array($candidate['text'], [';', '{', '}'], true)) {
                    break;
                }
                if ($candidate['id'] === T_PRIVATE) {
                    $visibility = 'private';
                } elseif ($candidate['id'] === T_PROTECTED) {
                    $visibility = 'protected';
                } elseif ($candidate['id'] === T_PUBLIC) {
                    $visibility = 'public';
                }
            }
            if ($visibility !== 'public') {
                continue;
            }
        }
        $open = null;
        $endIndex = null;
        for ($cursor = $nameIndex + 1; $cursor < count($tokens); $cursor++) {
            if ($tokens[$cursor]['text'] === '{') {
                $open = $cursor;
                $endIndex = ppl_matching_brace($tokens, $cursor);
                break;
            }
            if ($tokens[$cursor]['text'] === ';') {
                $endIndex = $cursor;
                break;
            }
        }
        if ($endIndex === null) {
            continue;
        }
        $name = $tokens[$nameIndex]['text'];
        $spelling = substr($source, $token['start'], $tokens[$endIndex]['end'] - $token['start']);
        $normalized = '';
        if ($open !== null) {
            for ($cursor = $open + 1; $cursor < $endIndex; $cursor++) {
                if (ppl_significant($tokens[$cursor]['id'])) {
                    $normalized .= ($tokens[$cursor]['id'] ?? 0) . ':' . $tokens[$cursor]['text'] . "\0";
                }
            }
        }
        $functions[] = [
            'file' => $relative,
            'kind' => $owner === null ? 'function' : 'method',
            'symbol' => $name,
            'qualified_symbol' => $owner === null ? $name : $owner . '::' . $name,
            'owner' => $owner,
            'span' => ppl_span($source, $token['start'], $tokens[$endIndex]['end']),
            'spelling_sha256' => ppl_hash($spelling),
            'source_sha256' => ppl_hash($source),
            'body_sha256' => $open === null ? null : ppl_hash($normalized),
            'line_count' => substr_count($spelling, "\n") + 1,
            'has_body' => $open !== null,
        ];
    }
    $declarations = [];
    foreach ($types as $type) {
        unset($type['body_open'], $type['body_close']);
        $declarations[] = $type;
    }
    foreach ($functions as $function) {
        $declarations[] = $function;
    }
    usort($declarations, fn (array $left, array $right): int => [$left['file'], $left['span']['start_byte']] <=> [$right['file'], $right['span']['start_byte']]);
    $unresolved = [];
    foreach ($tokens as $token) {
        if ($token['id'] === T_STRING && strcasecmp($token['text'], 'class_alias') === 0) {
            $unresolved[] = [
                'file' => $relative,
                'symbol' => 'class_alias',
                'reason' => 'dynamic class_alias identity requires runtime/project resolution',
            ];
        }
    }
    return [
        'declarations' => $declarations,
        'functions' => $functions,
        'unresolved' => $unresolved,
        'limitations' => $limitations,
    ];
}

/** @return array{role: string, reason?: string} */
function ppl_role(string $relative, string $source): array
{
    $parts = array_map('strtolower', explode('/', $relative));
    $directories = array_slice($parts, 0, -1);
    if (array_intersect($directories, PPL_TOOLING_DIRECTORIES) !== []) {
        return ['role' => 'excluded', 'reason' => 'tooling'];
    }
    if (array_intersect($directories, ['vendor']) !== []) {
        return ['role' => 'excluded', 'reason' => 'vendor'];
    }
    if (array_intersect($directories, PPL_TEST_DIRECTORIES) !== []) {
        return ['role' => 'excluded', 'reason' => 'test'];
    }
    if (array_intersect($directories, PPL_GENERATED_DIRECTORIES) !== []) {
        return ['role' => 'excluded', 'reason' => 'generated-tree'];
    }
    if (array_intersect($directories, PPL_BUILD_DIRECTORIES) !== []) {
        return ['role' => 'excluded', 'reason' => 'build-tree'];
    }
    if (array_intersect($directories, PPL_REPORT_DIRECTORIES) !== []) {
        return ['role' => 'excluded', 'reason' => 'report-tree'];
    }
    if (preg_match('/(?:@generated\b|Code generated .* DO NOT EDIT\.)/i', substr($source, 0, 4096)) === 1) {
        return ['role' => 'excluded', 'reason' => 'generated-marker'];
    }
    return ['role' => 'candidate'];
}

function ppl_selected(string $path, string $target): bool
{
    return $path === $target || ppl_is_inside($target, $path);
}

/** @return list<array<string, mixed>> */
function ppl_inventory(string $root, string $target): array
{
    $inventory = [];
    $directory = new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS);
    $iterator = new RecursiveIteratorIterator($directory, RecursiveIteratorIterator::SELF_FIRST);
    foreach ($iterator as $info) {
        $path = $info->getPathname();
        $relative = ppl_relative($root, $path);
        if ($info->isLink()) {
            $inventory[] = [
                'file' => $relative,
                'role' => 'excluded',
                'reason' => 'symlink',
                'selected' => ppl_selected($path, $target),
                '_path' => $path,
            ];
            continue;
        }
        if (!$info->isFile() || strtolower($info->getExtension()) !== 'php') {
            continue;
        }
        $source = @file_get_contents($path);
        if ($source === false) {
            $inventory[] = [
                'file' => $relative,
                'role' => 'failed',
                'reason' => 'read-error',
                'selected' => ppl_selected($path, $target),
                '_path' => $path,
            ];
            continue;
        }
        $role = ppl_role($relative, $source);
        $selected = ppl_selected($path, $target);
        $inventory[] = [
            'file' => $relative,
            'role' => $role['role'] === 'candidate' && $selected ? 'eligible' : $role['role'],
            ...($role['reason'] ?? null ? ['reason' => $role['reason']] : []),
            'selected' => $selected,
            'source_sha256' => ppl_hash($source),
            'source_bytes' => strlen($source),
            '_path' => $path,
            '_source' => $source,
        ];
    }
    usort($inventory, fn (array $left, array $right): int => $left['file'] <=> $right['file']);
    return $inventory;
}

/** @return array<string, mixed> */
function ppl_collect_snapshot(
    string $root,
    string $target,
    string $php,
    string $composer,
    string $minimumPhp = '8.1.0',
    string $minimumComposer = '2.2.0',
): array {
    $status = 'complete';
    $errors = [];
    if (!is_dir($target) || is_link($target) || ppl_has_symlink_component($root, $target)) {
        $status = 'failed';
        $errors[] = 'target must be a non-symlink directory inside project root';
    }
    $inventory = ppl_inventory($root, $target);
    $phpProbe = ppl_probe_tool($php, 'php', $minimumPhp, $root);
    $composerProbe = ppl_probe_tool($composer, 'composer', $minimumComposer, $root);
    foreach ([$phpProbe, $composerProbe] as $probe) {
        if ($probe['state'] === 'failed') {
            $status = ppl_status_merge($status, 'failed');
            $errors[] = $probe['failure_kind'];
        } elseif ($probe['state'] !== 'ready') {
            $status = ppl_status_merge($status, 'partial');
            $errors[] = $probe['failure_kind'];
        }
    }

    $manifestPath = $root . DIRECTORY_SEPARATOR . 'composer.json';
    $composerManifest = null;
    if (!is_file($manifestPath) || is_link($manifestPath)) {
        $status = ppl_status_merge($status, 'partial');
        $errors[] = 'composer-manifest-missing-or-unsafe';
    } else {
        try {
            $decoded = json_decode((string) file_get_contents($manifestPath), true, 512, JSON_THROW_ON_ERROR);
            if (!is_array($decoded)) {
                throw new RuntimeException('composer.json must contain an object');
            }
            $composerManifest = [
                'name' => $decoded['name'] ?? null,
                'psr4' => is_array($decoded['autoload']['psr-4'] ?? null) ? $decoded['autoload']['psr-4'] : [],
                'scripts' => is_array($decoded['scripts'] ?? null) ? $decoded['scripts'] : [],
                'sha256' => ppl_hash((string) file_get_contents($manifestPath)),
            ];
            foreach ($composerManifest['psr4'] as $namespace => $directory) {
                if (!is_string($namespace) || !is_string($directory)) {
                    $status = ppl_status_merge($status, 'partial');
                    $errors[] = 'composer-psr4-non-string-mapping';
                }
            }
        } catch (Throwable $error) {
            $status = ppl_status_merge($status, 'failed');
            $errors[] = 'composer-manifest-malformed: ' . $error->getMessage();
        }
    }

    $composerValidation = ['returncode' => null, 'stdout' => '', 'stderr' => '', 'state' => 'not-run'];
    if ($composerProbe['state'] === 'ready') {
        $composerValidation = ppl_process(
            [$composerProbe['path'], 'validate', '--no-check-publish', '--no-interaction'],
            $root,
        );
        $composerValidation['state'] = $composerValidation['returncode'] === 0 ? 'passed' : 'failed';
        if ($composerValidation['returncode'] !== 0) {
            $status = ppl_status_merge($status, 'failed');
            $errors[] = 'composer-validation-failed';
        }
    }

    foreach ($inventory as &$row) {
        if ($row['role'] !== 'eligible') {
            continue;
        }
        try {
            $facts = ppl_lexical_facts($row['file'], $row['_source']);
            $row['parse_state'] = 'ok';
            $row['declarations'] = $facts['declarations'];
            $row['functions'] = $facts['functions'];
            $row['unresolved'] = $facts['unresolved'];
            $row['limitations'] = $facts['limitations'];
            if ($facts['limitations'] !== []) {
                $row['parse_state'] = 'partial';
                $status = ppl_status_merge($status, 'partial');
                array_push($errors, ...array_map(
                    fn (string $limitation): string => "php-source-partial:{$row['file']}:{$limitation}",
                    $facts['limitations'],
                ));
            }
        } catch (ParseError $error) {
            $row['parse_state'] = 'syntax-error';
            $row['parse_detail'] = $error->getMessage();
            $row['declarations'] = [];
            $row['functions'] = [];
            $row['unresolved'] = [];
            $row['limitations'] = [];
            $status = ppl_status_merge($status, 'partial');
            $errors[] = 'php-source-malformed:' . $row['file'];
        }
        $row['lint'] = ['returncode' => null, 'state' => 'not-run'];
        if ($phpProbe['state'] === 'ready') {
            $lint = ppl_process([$phpProbe['path'], '-l', $row['_path']], $root);
            $row['lint'] = [
                'returncode' => $lint['returncode'],
                'state' => $lint['returncode'] === 0 ? 'passed' : 'failed',
                'stdout' => $lint['stdout'],
                'stderr' => $lint['stderr'],
            ];
            if ($lint['returncode'] !== 0) {
                $kind = $row['parse_state'] === 'syntax-error' ? 'partial' : 'failed';
                $status = ppl_status_merge($status, $kind);
                $errors[] = 'php-lint-failed:' . $row['file'];
            }
        }
    }
    unset($row);

    $manifestRows = [];
    foreach ($inventory as $row) {
        if (isset($row['source_sha256'])) {
            $manifestRows[] = $row['file'] . "\0" . $row['source_sha256'] . "\n";
        }
    }
    return [
        'schema_version' => 1,
        'status' => $status,
        'errors' => array_values(array_unique($errors)),
        'project_root' => $root,
        'target' => ppl_relative($root, $target),
        'token_runtime' => ['path' => PHP_BINARY, 'version' => PHP_VERSION],
        'php' => $phpProbe,
        'composer' => $composerProbe,
        'composer_manifest' => $composerManifest,
        'composer_validate' => $composerValidation,
        'inventory' => $inventory,
        'source_manifest_sha256' => ppl_hash(implode('', $manifestRows)),
    ];
}

function ppl_sources_preserved(array $snapshot): bool
{
    foreach ($snapshot['inventory'] as $row) {
        if (!isset($row['source_sha256']) || !isset($row['_path'])) {
            continue;
        }
        $current = @file_get_contents($row['_path']);
        if ($current === false || ppl_hash($current) !== $row['source_sha256']) {
            return false;
        }
    }
    return true;
}

/** @return array<string, mixed> */
function ppl_public_snapshot(array $snapshot): array
{
    $public = $snapshot;
    unset($public['project_root']);
    $public['source_preserved'] = ppl_sources_preserved($snapshot);
    foreach (['stdout', 'stderr'] as $stream) {
        $content = (string) ($public['composer_validate'][$stream] ?? '');
        $public['composer_validate'][$stream . '_sha256'] = ppl_hash($content);
        $public['composer_validate'][$stream . '_bytes'] = strlen($content);
        unset($public['composer_validate'][$stream]);
    }
    foreach ($public['inventory'] as &$row) {
        $row['declaration_count'] = count($row['declarations'] ?? []);
        $row['function_count'] = count($row['functions'] ?? []);
        $row['unresolved_count'] = count($row['unresolved'] ?? []);
        if (isset($row['lint'])) {
            foreach (['stdout', 'stderr'] as $stream) {
                $content = (string) ($row['lint'][$stream] ?? '');
                $row['lint'][$stream . '_sha256'] = ppl_hash($content);
                $row['lint'][$stream . '_bytes'] = strlen($content);
                unset($row['lint'][$stream]);
            }
        }
        unset($row['_path'], $row['_source'], $row['declarations'], $row['functions'], $row['unresolved']);
    }
    unset($row);
    return $public;
}

function ppl_terminal_code(array $snapshot): int
{
    return match ($snapshot['status']) {
        'complete' => 0,
        'partial' => 2,
        default => 1,
    };
}

/** @return list<array<string, mixed>> */
function ppl_declarations(array $snapshot): array
{
    $facts = [];
    foreach ($snapshot['inventory'] as $row) {
        if ($row['role'] === 'eligible' && $row['parse_state'] !== 'syntax-error') {
            array_push($facts, ...$row['declarations']);
        }
    }
    usort($facts, fn (array $left, array $right): int => [$left['file'], $left['span']['start_byte']] <=> [$right['file'], $right['span']['start_byte']]);
    return $facts;
}

/** @return list<array<string, mixed>> */
function ppl_functions(array $snapshot): array
{
    $facts = [];
    foreach ($snapshot['inventory'] as $row) {
        if ($row['role'] === 'eligible' && $row['parse_state'] !== 'syntax-error') {
            array_push($facts, ...$row['functions']);
        }
    }
    return $facts;
}

/** @return list<array<string, string>> */
function ppl_unresolved(array $snapshot): array
{
    $facts = [];
    foreach ($snapshot['inventory'] as $row) {
        if ($row['role'] === 'eligible' && $row['parse_state'] !== 'syntax-error') {
            array_push($facts, ...$row['unresolved']);
        }
    }
    return $facts;
}
