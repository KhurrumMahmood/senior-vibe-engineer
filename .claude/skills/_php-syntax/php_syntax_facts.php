<?php

declare(strict_types=1);

/**
 * PHP-local, syntax-only facts for the Cohort A A2 read-only consumers.
 *
 * This deliberately owns a different boundary from _php-project-lexical:
 * comments, direct named-function bodies, branch tokens, direct call spelling,
 * and lexical try enclosures. It does not resolve PHP symbols, dispatch,
 * Composer autoloading, types, framework conventions, behavior, or safe edits.
 */

const PPS_TEST_DIRECTORIES = ['test', 'tests', 'spec', 'specs', 'fixtures', 'testdata'];
const PPS_GENERATED_DIRECTORIES = ['generated', 'gen'];
const PPS_BUILD_DIRECTORIES = ['build', 'dist', 'out', 'cache', 'coverage'];
const PPS_REPORT_DIRECTORIES = ['report', 'reports'];
const PPS_TOOLING_DIRECTORIES = ['.agents', '.claude', '.git', '.idea', '.vscode'];

/** @return array<string, string> */
function pps_cli(array $argv, array $required, array $defaults = []): array
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

function pps_normalize_path(string $path): string
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

function pps_is_absolute(string $path): bool
{
    return str_starts_with($path, DIRECTORY_SEPARATOR)
        || preg_match('/\A[A-Za-z]:[\\\\\/]/', $path) === 1;
}

function pps_is_inside(string $root, string $candidate): bool
{
    $root = rtrim(pps_normalize_path($root), DIRECTORY_SEPARATOR);
    $candidate = pps_normalize_path($candidate);
    return $candidate === $root || str_starts_with($candidate, $root . DIRECTORY_SEPARATOR);
}

function pps_project_root(string $supplied): string
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

function pps_inside_path(string $root, string $supplied, string $label): string
{
    $candidate = pps_is_absolute($supplied) ? $supplied : $root . DIRECTORY_SEPARATOR . $supplied;
    $candidate = pps_normalize_path($candidate);
    $probe = $candidate;
    $tail = [];
    while (!file_exists($probe) && !is_link($probe) && dirname($probe) !== $probe) {
        array_unshift($tail, basename($probe));
        $probe = dirname($probe);
    }
    $resolvedProbe = realpath($probe);
    if ($resolvedProbe !== false) {
        $candidate = pps_normalize_path(
            $resolvedProbe . ($tail === [] ? '' : DIRECTORY_SEPARATOR . implode(DIRECTORY_SEPARATOR, $tail)),
        );
    }
    if (!pps_is_inside($root, $candidate)) {
        throw new InvalidArgumentException("{$label} must stay inside project root");
    }
    return $candidate;
}

function pps_relative(string $root, string $path): string
{
    $relative = ltrim(substr(pps_normalize_path($path), strlen(rtrim($root, DIRECTORY_SEPARATOR))), DIRECTORY_SEPARATOR);
    return str_replace(DIRECTORY_SEPARATOR, '/', $relative);
}

function pps_has_symlink_component(string $root, string $path): bool
{
    if (!pps_is_inside($root, $path)) {
        return true;
    }
    $current = rtrim($root, DIRECTORY_SEPARATOR);
    $relative = pps_relative($root, $path);
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

/** @return array{returncode: int, stdout: string, stderr: string} */
function pps_process(array $command, string $cwd): array
{
    $spec = [1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
    $process = proc_open($command, $spec, $pipes, $cwd);
    if (!is_resource($process)) {
        return ['returncode' => 127, 'stdout' => '', 'stderr' => 'process could not start'];
    }
    $stdout = stream_get_contents($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    return ['returncode' => proc_close($process), 'stdout' => $stdout, 'stderr' => $stderr];
}

function pps_resolve_command(string $configured): ?string
{
    if (str_contains($configured, DIRECTORY_SEPARATOR) || str_contains($configured, '/')) {
        return is_file($configured) && is_executable($configured) ? $configured : null;
    }
    $path = getenv('PATH') ?: '';
    foreach (explode(PATH_SEPARATOR, $path) as $directory) {
        $candidate = rtrim($directory, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . $configured;
        if (is_file($candidate) && is_executable($candidate)) {
            return $candidate;
        }
    }
    return null;
}

/** @return array<string, mixed> */
function pps_probe_tool(string $configured, string $name, string $minimum, string $root): array
{
    $path = pps_resolve_command($configured);
    if ($path === null) {
        return ['state' => 'missing', 'failure_kind' => "{$name}_tool_missing", 'configured' => $configured];
    }
    $result = pps_process([$path, '--version'], $root);
    if ($result['returncode'] !== 0) {
        return [
            'state' => 'failed', 'failure_kind' => "{$name}_tool_probe_failed", 'configured' => $configured,
            'path' => $path, 'returncode' => $result['returncode'],
        ];
    }
    $match = [];
    $versionPattern = $name === 'php'
        ? '/PHP\s+(\d+\.\d+(?:\.\d+)?)/i'
        : '/Composer version\s+(\d+\.\d+(?:\.\d+)?)/i';
    if (preg_match($versionPattern, $result['stdout'] . "\n" . $result['stderr'], $match) !== 1) {
        return [
            'state' => 'failed', 'failure_kind' => "{$name}_tool_probe_failed", 'configured' => $configured,
            'path' => $path, 'returncode' => 0,
        ];
    }
    $version = $match[1];
    return [
        'state' => version_compare($version, $minimum, '>=') ? 'ready' : 'too-old',
        'path' => $path,
        'version' => $version,
        'minimum_version' => $minimum,
        ...(version_compare($version, $minimum, '>=') ? [] : ['failure_kind' => "{$name}_tool_too_old"]),
    ];
}

function pps_status_merge(string $current, string $candidate): string
{
    $priority = ['complete' => 0, 'partial' => 1, 'failed' => 2];
    return $priority[$candidate] > $priority[$current] ? $candidate : $current;
}

function pps_hash(string $content): string
{
    return hash('sha256', $content);
}

/** @return array<string, mixed> */
function pps_span(string $source, int $start, int $end): array
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
function pps_tokens(string $source): array
{
    $parsed = token_get_all($source, TOKEN_PARSE);
    $records = [];
    $offset = 0;
    $line = 1;
    foreach ($parsed as $token) {
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

function pps_significant(?int $id): bool
{
    return $id === null || !in_array($id, [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT], true);
}

function pps_next(array $tokens, int $index): ?int
{
    for ($cursor = $index + 1; $cursor < count($tokens); $cursor++) {
        if (pps_significant($tokens[$cursor]['id'])) {
            return $cursor;
        }
    }
    return null;
}

function pps_previous(array $tokens, int $index): ?int
{
    for ($cursor = $index - 1; $cursor >= 0; $cursor--) {
        if (pps_significant($tokens[$cursor]['id'])) {
            return $cursor;
        }
    }
    return null;
}

function pps_matching_brace(array $tokens, int $open): ?int
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
function pps_brace_depths(array $tokens): array
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

/** @return array{role: string, reason?: string} */
function pps_role(string $relative, string $source): array
{
    $parts = array_map('strtolower', explode('/', $relative));
    $directories = array_slice($parts, 0, -1);
    if (array_intersect($directories, PPS_TOOLING_DIRECTORIES) !== []) {
        return ['role' => 'excluded', 'reason' => 'tooling'];
    }
    if (in_array('vendor', $directories, true)) {
        return ['role' => 'vendor', 'reason' => 'vendor'];
    }
    if (array_intersect($directories, PPS_TEST_DIRECTORIES) !== []) {
        return ['role' => 'test', 'reason' => 'test'];
    }
    if (array_intersect($directories, PPS_GENERATED_DIRECTORIES) !== []) {
        return ['role' => 'generated', 'reason' => 'generated-tree'];
    }
    if (array_intersect($directories, PPS_BUILD_DIRECTORIES) !== []) {
        return ['role' => 'build', 'reason' => 'build-tree'];
    }
    if (array_intersect($directories, PPS_REPORT_DIRECTORIES) !== []) {
        return ['role' => 'report', 'reason' => 'report-tree'];
    }
    if (preg_match('/(?:@generated\b|Code generated .* DO NOT EDIT\.)/i', substr($source, 0, 4096)) === 1) {
        return ['role' => 'generated', 'reason' => 'generated-marker'];
    }
    return ['role' => 'candidate'];
}

function pps_selected(string $path, string $target): bool
{
    return $path === $target || pps_is_inside($target, $path);
}

/** @return list<array<string, mixed>> */
function pps_inventory(string $root, string $target): array
{
    $inventory = [];
    $directory = new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS);
    $iterator = new RecursiveIteratorIterator($directory, RecursiveIteratorIterator::SELF_FIRST);
    foreach ($iterator as $info) {
        $path = $info->getPathname();
        $relative = pps_relative($root, $path);
        if ($info->isLink()) {
            $inventory[] = [
                'file' => $relative, 'role' => 'symlink', 'reason' => 'symlink',
                'selected' => pps_selected($path, $target), '_path' => $path,
            ];
            continue;
        }
        if (!$info->isFile() || strtolower($info->getExtension()) !== 'php') {
            continue;
        }
        $source = @file_get_contents($path);
        if ($source === false) {
            $inventory[] = [
                'file' => $relative, 'role' => 'failed', 'reason' => 'read-error',
                'selected' => pps_selected($path, $target), '_path' => $path,
            ];
            continue;
        }
        $role = pps_role($relative, $source);
        $selected = pps_selected($path, $target);
        $inventory[] = [
            'file' => $relative,
            'role' => $role['role'] === 'candidate' && $selected ? 'source' : $role['role'],
            ...($role['reason'] ?? null ? ['reason' => $role['reason']] : []),
            'selected' => $selected,
            'source_sha256' => pps_hash($source),
            'source_bytes' => strlen($source),
            '_path' => $path,
            '_source' => $source,
        ];
    }
    usort($inventory, fn (array $left, array $right): int => $left['file'] <=> $right['file']);
    return $inventory;
}

/** @return list<array{open: int, close: int}> */
function pps_nested_callable_ranges(array $tokens, int $open, int $close): array
{
    $ranges = [];
    for ($index = $open + 1; $index < $close; $index++) {
        if ($tokens[$index]['id'] !== T_FUNCTION) {
            continue;
        }
        $bodyOpen = null;
        for ($cursor = $index + 1; $cursor < $close; $cursor++) {
            if ($tokens[$cursor]['text'] === '{') {
                $bodyOpen = $cursor;
                break;
            }
            if ($tokens[$cursor]['text'] === ';') {
                break;
            }
        }
        if ($bodyOpen !== null && ($bodyClose = pps_matching_brace($tokens, $bodyOpen)) !== null) {
            $ranges[] = ['open' => $index, 'close' => $bodyClose];
            $index = $bodyClose;
        }
    }
    return $ranges;
}

function pps_in_range(int $index, array $ranges): bool
{
    foreach ($ranges as $range) {
        if ($index >= $range['open'] && $index <= $range['close']) {
            return true;
        }
    }
    return false;
}

/** @return array{events: list<array<string, mixed>>, score: int, limitations: list<string>} */
function pps_branch_facts(string $source, array $tokens, int $open, int $close): array
{
    $events = [];
    $nested = pps_nested_callable_ranges($tokens, $open, $close);
    $tokenKinds = [
        T_IF => 'if', T_ELSEIF => 'elseif', T_FOR => 'for', T_FOREACH => 'foreach',
        T_WHILE => 'while', T_DO => 'do', T_CATCH => 'catch', T_CASE => 'case',
        T_DEFAULT => 'default',
    ];
    if (defined('T_MATCH')) {
        $tokenKinds[constant('T_MATCH')] = 'match';
    }
    for ($index = $open + 1; $index < $close; $index++) {
        if (pps_in_range($index, $nested)) {
            continue;
        }
        $token = $tokens[$index];
        $kind = $tokenKinds[$token['id']] ?? null;
        if ($kind === null && $token['text'] === '&&') {
            $kind = 'logical_and';
        } elseif ($kind === null && $token['text'] === '||') {
            $kind = 'logical_or';
        }
        if ($kind === null) {
            continue;
        }
        $events[] = [
            'kind' => $kind, 'line' => $token['line'],
            'span' => pps_span($source, $token['start'], $token['end']),
        ];
    }
    $limitations = [];
    if (defined('T_FN')) {
        foreach ($tokens as $index => $token) {
            if ($index > $open && $index < $close && $token['id'] === constant('T_FN')) {
                $limitations[] = 'arrow-function-body-boundary';
                break;
            }
        }
    }
    return ['events' => $events, 'score' => count($events), 'limitations' => $limitations];
}

/** @return list<array{open: int, close: int}> */
function pps_try_ranges(array $tokens): array
{
    $ranges = [];
    foreach ($tokens as $index => $token) {
        if ($token['id'] !== T_TRY) {
            continue;
        }
        for ($cursor = $index + 1; $cursor < count($tokens); $cursor++) {
            if ($tokens[$cursor]['text'] === '{') {
                $close = pps_matching_brace($tokens, $cursor);
                if ($close !== null) {
                    $ranges[] = ['open' => $cursor, 'close' => $close];
                }
                break;
            }
        }
    }
    return $ranges;
}

/** @return list<array<string, mixed>> */
function pps_call_facts(string $source, array $tokens, array $functions): array
{
    $calls = [];
    $tries = pps_try_ranges($tokens);
    $declarationIds = [T_FUNCTION, T_CLASS, T_INTERFACE, T_TRAIT, T_NEW, T_NAMESPACE, T_USE];
    if (defined('T_ENUM')) {
        $declarationIds[] = constant('T_ENUM');
    }
    foreach ($tokens as $index => $token) {
        if ($token['id'] !== T_STRING) {
            continue;
        }
        $next = pps_next($tokens, $index);
        $previous = pps_previous($tokens, $index);
        if ($next === null || $tokens[$next]['text'] !== '(' || ($previous !== null && in_array($tokens[$previous]['id'], $declarationIds, true))) {
            continue;
        }
        $start = $token['start'];
        $spelling = $token['text'];
        if ($previous !== null && in_array($tokens[$previous]['text'], ['::', '->'], true)) {
            $receiver = pps_previous($tokens, $previous);
            if ($receiver !== null && in_array($tokens[$receiver]['id'], [T_STRING, T_VARIABLE], true)) {
                $start = $tokens[$receiver]['start'];
                $spelling = $tokens[$receiver]['text'] . $tokens[$previous]['text'] . $token['text'];
            }
        }
        $owner = null;
        foreach ($functions as $function) {
            if ($token['start'] > $function['body_span']['start_byte'] && $token['end'] < $function['body_span']['end_byte']) {
                $owner = $function['qualified_name'];
                break;
            }
        }
        $enclosures = [];
        foreach ($tries as $range) {
            if ($index > $range['open'] && $index < $range['close']) {
                $enclosures[] = 'try';
                break;
            }
        }
        $calls[] = [
            'spelling' => $spelling, 'line' => $token['line'], 'function' => $owner,
            'enclosures' => $enclosures, 'span' => pps_span($source, $start, $tokens[$next]['end']),
        ];
    }
    usort($calls, fn (array $left, array $right): int => [$left['line'], $left['spelling']] <=> [$right['line'], $right['spelling']]);
    return $calls;
}

/** @return array{comments: list<array<string, mixed>>, functions: list<array<string, mixed>>, calls: list<array<string, mixed>>, limitations: list<string>} */
function pps_syntax_facts(string $relative, string $source): array
{
    $tokens = pps_tokens($source);
    $depths = pps_brace_depths($tokens);
    $types = [];
    $typeIds = [T_CLASS => 'class', T_INTERFACE => 'interface', T_TRAIT => 'trait'];
    if (defined('T_ENUM')) {
        $typeIds[constant('T_ENUM')] = 'enum';
    }
    foreach ($tokens as $index => $token) {
        if ($token['id'] === null || !isset($typeIds[$token['id']])) {
            continue;
        }
        $previous = pps_previous($tokens, $index);
        if ($previous !== null && $tokens[$previous]['id'] === T_NEW) {
            continue;
        }
        $name = pps_next($tokens, $index);
        if ($name === null || $tokens[$name]['id'] !== T_STRING) {
            continue;
        }
        $open = null;
        for ($cursor = $name + 1; $cursor < count($tokens); $cursor++) {
            if ($tokens[$cursor]['text'] === '{') {
                $open = $cursor;
                break;
            }
            if ($tokens[$cursor]['text'] === ';') {
                break;
            }
        }
        if ($open !== null && ($close = pps_matching_brace($tokens, $open)) !== null) {
            $types[] = ['name' => $tokens[$name]['text'], 'open' => $open, 'close' => $close];
        }
    }
    $functions = [];
    $limitations = [];
    foreach ($tokens as $index => $token) {
        if ($token['id'] !== T_FUNCTION) {
            continue;
        }
        $name = pps_next($tokens, $index);
        if ($name !== null && $tokens[$name]['text'] === '&') {
            $name = pps_next($tokens, $name);
        }
        if ($name === null || $tokens[$name]['id'] !== T_STRING) {
            continue;
        }
        $open = null;
        for ($cursor = $name + 1; $cursor < count($tokens); $cursor++) {
            if ($tokens[$cursor]['text'] === '{') {
                $open = $cursor;
                break;
            }
            if ($tokens[$cursor]['text'] === ';') {
                break;
            }
        }
        if ($open === null || ($close = pps_matching_brace($tokens, $open)) === null) {
            continue;
        }
        $owner = null;
        foreach ($types as $type) {
            if ($index > $type['open'] && $index < $type['close'] && $depths[$index] === $depths[$type['open']] + 1) {
                $owner = $type['name'];
                break;
            }
        }
        $branch = pps_branch_facts($source, $tokens, $open, $close);
        array_push($limitations, ...$branch['limitations']);
        $functions[] = [
            'file' => $relative, 'name' => $tokens[$name]['text'], 'owner' => $owner,
            'qualified_name' => $owner === null ? $tokens[$name]['text'] : $owner . '::' . $tokens[$name]['text'],
            'line' => $token['line'], 'end_line' => $tokens[$close]['line'],
            'loc' => $tokens[$close]['line'] - $token['line'] + 1,
            'span' => pps_span($source, $token['start'], $tokens[$close]['end']),
            'body_span' => pps_span($source, $tokens[$open]['start'], $tokens[$close]['end']),
            'spelling_sha256' => pps_hash(substr($source, $token['start'], $tokens[$close]['end'] - $token['start'])),
            'branch_score' => $branch['score'], 'branch_events' => $branch['events'],
        ];
    }
    usort($functions, fn (array $left, array $right): int => [$left['file'], $left['line'], $left['qualified_name']] <=> [$right['file'], $right['line'], $right['qualified_name']]);
    $comments = [];
    foreach ($tokens as $token) {
        if (!in_array($token['id'], [T_COMMENT, T_DOC_COMMENT], true)) {
            continue;
        }
        $comments[] = [
            'text' => $token['text'], 'line' => $token['line'],
            'form' => $token['id'] === T_DOC_COMMENT ? 'doc' : (str_starts_with($token['text'], '//') || str_starts_with($token['text'], '#') ? 'line' : 'block'),
            'span' => pps_span($source, $token['start'], $token['end']),
        ];
    }
    return [
        'comments' => $comments, 'functions' => $functions,
        'calls' => pps_call_facts($source, $tokens, $functions),
        'limitations' => array_values(array_unique($limitations)),
    ];
}

/** @return array<string, mixed> */
function pps_public_probe(array $probe): array
{
    return $probe;
}

/** @return array<string, mixed> */
function pps_produce(
    string $projectRoot,
    string $targetInput,
    string $php = 'php',
    string $composer = 'composer',
    string $minimumPhp = '8.1.0',
    string $minimumComposer = '2.2.0',
): array {
    $root = pps_project_root($projectRoot);
    $target = pps_inside_path($root, $targetInput, 'target');
    $status = 'complete';
    $errors = [];
    if (!is_dir($target) || is_link($target) || pps_has_symlink_component($root, $target)) {
        $status = 'failed';
        $errors[] = 'target_invalid';
    }
    $inventory = pps_inventory($root, $target);
    $phpProbe = pps_probe_tool($php, 'php', $minimumPhp, $root);
    $composerProbe = pps_probe_tool($composer, 'composer', $minimumComposer, $root);
    foreach ([$phpProbe, $composerProbe] as $probe) {
        if ($probe['state'] === 'failed') {
            $status = pps_status_merge($status, 'failed');
            $errors[] = $probe['failure_kind'];
        } elseif ($probe['state'] !== 'ready') {
            $status = pps_status_merge($status, 'partial');
            $errors[] = $probe['failure_kind'];
        }
    }
    $manifestPath = $root . DIRECTORY_SEPARATOR . 'composer.json';
    $composerManifest = null;
    if (!is_file($manifestPath) || is_link($manifestPath)) {
        $status = pps_status_merge($status, 'partial');
        $errors[] = 'composer_manifest_missing_or_unsafe';
    } else {
        try {
            $decoded = json_decode((string) file_get_contents($manifestPath), true, 512, JSON_THROW_ON_ERROR);
            if (!is_array($decoded)) {
                throw new RuntimeException('composer.json must contain an object');
            }
            $composerManifest = ['sha256' => pps_hash((string) file_get_contents($manifestPath))];
        } catch (Throwable $error) {
            $status = pps_status_merge($status, 'failed');
            $errors[] = 'composer_manifest_malformed';
        }
    }
    $composerValidation = ['returncode' => null, 'state' => 'not-run'];
    if ($composerProbe['state'] === 'ready') {
        $validation = pps_process([$composerProbe['path'], 'validate', '--no-check-publish', '--no-interaction'], $root);
        $composerValidation = ['returncode' => $validation['returncode'], 'state' => $validation['returncode'] === 0 ? 'passed' : 'failed'];
        if ($validation['returncode'] !== 0) {
            $status = pps_status_merge($status, 'failed');
            $errors[] = 'composer_validation_failed';
        }
    }
    $files = [];
    foreach ($inventory as &$row) {
        if ($row['role'] !== 'source') {
            continue;
        }
        $row['lint'] = ['returncode' => null, 'state' => 'not-run'];
        try {
            $facts = pps_syntax_facts($row['file'], $row['_source']);
            $row['parse_state'] = $facts['limitations'] === [] ? 'ok' : 'partial';
            if ($facts['limitations'] !== []) {
                $status = pps_status_merge($status, 'partial');
                $errors[] = 'php_syntax_ambiguity';
            }
            $files[] = [
                'file' => $row['file'], 'source_sha256' => $row['source_sha256'],
                'comments' => $facts['comments'], 'functions' => $facts['functions'], 'calls' => $facts['calls'],
                'limitations' => $facts['limitations'],
            ];
        } catch (ParseError) {
            $row['parse_state'] = 'syntax-error';
            $status = pps_status_merge($status, 'partial');
            $errors[] = 'php_parse_diagnostics';
        }
        if ($phpProbe['state'] === 'ready') {
            $lint = pps_process([$phpProbe['path'], '-l', $row['_path']], $root);
            $row['lint'] = ['returncode' => $lint['returncode'], 'state' => $lint['returncode'] === 0 ? 'passed' : 'failed'];
            if ($lint['returncode'] !== 0) {
                $kind = $row['parse_state'] === 'syntax-error' ? 'partial' : 'failed';
                $status = pps_status_merge($status, $kind);
                $errors[] = $kind === 'partial' ? 'php_parse_diagnostics' : 'php_lint_failed';
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
    if ($composerManifest !== null) {
        $manifestRows[] = "composer.json\0" . $composerManifest['sha256'] . "\n";
    }
    $before = pps_hash(implode('', $manifestRows));
    $afterRows = [];
    foreach ($inventory as $row) {
        if (!isset($row['_path'], $row['source_sha256'])) {
            continue;
        }
        $current = @file_get_contents($row['_path']);
        if ($current === false || pps_hash($current) !== $row['source_sha256']) {
            $errors[] = 'source_mutation_detected';
            $status = 'failed';
        }
        if ($current !== false) {
            $afterRows[] = $row['file'] . "\0" . pps_hash($current) . "\n";
        }
    }
    if ($composerManifest !== null) {
        $current = @file_get_contents($manifestPath);
        if ($current === false || pps_hash($current) !== $composerManifest['sha256']) {
            $errors[] = 'source_mutation_detected';
            $status = 'failed';
        }
        if ($current !== false) {
            $afterRows[] = "composer.json\0" . pps_hash($current) . "\n";
        }
    }
    $after = pps_hash(implode('', $afterRows));
    $publicInventory = [];
    foreach ($inventory as $row) {
        unset($row['_path'], $row['_source']);
        $publicInventory[] = $row;
    }
    usort($files, fn (array $left, array $right): int => $left['file'] <=> $right['file']);
    $failure = $errors[0] ?? 'none';
    return [
        'schema_version' => 1,
        'status' => $status,
        'failure_kind' => $status === 'complete' ? 'none' : $failure,
        'analyzer' => 'php-token-syntax-facts-v1',
        'target' => pps_relative($root, $target),
        'php' => pps_public_probe($phpProbe),
        'composer' => pps_public_probe($composerProbe),
        'composer_manifest' => $composerManifest,
        'composer_validate' => $composerValidation,
        'inventory' => $publicInventory,
        'files' => $status === 'complete' ? $files : [],
        'source_manifest' => ['before_sha256' => $before, 'after_sha256' => $after, 'preserved' => $before === $after],
        'limitations' => [
            'Token facts establish spelling and lexical enclosure only; no symbol, call target, type, Composer, framework, behavior, or refactor authority.',
        ],
    ];
}

function pps_terminal_code(array $facts): int
{
    return match ($facts['status']) {
        'complete' => 0,
        'partial' => 2,
        default => 1,
    };
}

if (realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    try {
        $options = pps_cli(
            $argv,
            ['project-root', 'target'],
            ['php' => 'php', 'composer' => 'composer', 'minimum-php' => '8.1.0', 'minimum-composer' => '2.2.0'],
        );
        $facts = pps_produce(
            $options['project-root'], $options['target'], $options['php'], $options['composer'],
            $options['minimum-php'], $options['minimum-composer'],
        );
        echo json_encode($facts, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . "\n";
        exit(pps_terminal_code($facts));
    } catch (Throwable $error) {
        fwrite(STDERR, $error->getMessage() . "\n");
        exit(64);
    }
}
