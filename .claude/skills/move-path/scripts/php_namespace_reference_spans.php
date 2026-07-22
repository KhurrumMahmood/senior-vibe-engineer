<?php

declare(strict_types=1);

/**
 * Emit exact PHP token spans for one bounded PSR-4 namespace-directory move.
 *
 * The Python orchestrator owns discovery, Composer mapping, exclusions, native
 * checks, and rollback. This helper owns only PHP syntax and token byte spans.
 */

function finish(array $payload, int $exitCode): never
{
    echo json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), "\n";
    exit($exitCode);
}

function lineForOffset(string $text, int $offset): int
{
    return substr_count(substr($text, 0, $offset), "\n") + 1;
}

function startsWithNamespace(string $name, string $namespace): bool
{
    $normalized = ltrim($name, '\\');
    return $normalized === $namespace || str_starts_with($normalized, $namespace . '\\');
}

function replaceNamespacePrefix(string $name, string $old, string $new): string
{
    $leadingSlash = str_starts_with($name, '\\') ? '\\' : '';
    $normalized = ltrim($name, '\\');
    return $leadingSlash . $new . substr($normalized, strlen($old));
}

function literalBody(string $token): ?string
{
    if (strlen($token) < 2) {
        return null;
    }
    $quote = $token[0];
    if (($quote !== "'" && $quote !== '"') || $token[strlen($token) - 1] !== $quote) {
        return null;
    }
    $body = substr($token, 1, -1);
    if ($quote === "'") {
        return str_replace(["\\\\", "\\'"], ["\\", "'"], $body);
    }
    return stripcslashes($body);
}

function tokenNameIds(): array
{
    $ids = [T_STRING];
    foreach (['T_NAME_QUALIFIED', 'T_NAME_FULLY_QUALIFIED', 'T_NAME_RELATIVE'] as $constant) {
        if (defined($constant)) {
            $ids[] = constant($constant);
        }
    }
    return $ids;
}

function covered(int $offset, array $spans): bool
{
    foreach ($spans as $span) {
        if ($offset >= $span['start'] && $offset < $span['end']) {
            return true;
        }
    }
    return false;
}

function analyzeFile(
    string $root,
    string $relative,
    string $oldNamespace,
    string $newNamespace,
    string $oldPath,
    string $newPath,
): array {
    $absolute = $root . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $relative);
    $text = file_get_contents($absolute);
    if ($text === false) {
        throw new RuntimeException("unable to read {$relative}");
    }
    try {
        $tokens = token_get_all($text, TOKEN_PARSE);
    } catch (ParseError $error) {
        throw new RuntimeException("{$relative}: {$error->getMessage()}", previous: $error);
    }

    $spans = [];
    $namespaces = [];
    $offset = 0;
    $expectNamespace = false;
    $inRequire = false;
    $nameIds = tokenNameIds();
    foreach ($tokens as $token) {
        $id = is_array($token) ? $token[0] : null;
        $value = is_array($token) ? $token[1] : $token;
        $start = $offset;
        $end = $start + strlen($value);

        if ($id === T_NAMESPACE) {
            $expectNamespace = true;
        } elseif ($id !== null && in_array($id, [T_REQUIRE, T_REQUIRE_ONCE, T_INCLUDE, T_INCLUDE_ONCE], true)) {
            $inRequire = true;
        } elseif ($value === ';') {
            $inRequire = false;
            $expectNamespace = false;
        }

        if ($id !== null && in_array($id, $nameIds, true)) {
            $isNamespaceDeclaration = $expectNamespace;
            if ($isNamespaceDeclaration) {
                $namespaces[] = ltrim($value, '\\');
                $expectNamespace = false;
            }
            if (startsWithNamespace($value, $oldNamespace)) {
                $kind = $isNamespaceDeclaration ? 'php_namespace' : 'php_name';
                $spans[] = [
                    'file' => $relative,
                    'start' => $start,
                    'end' => $end,
                    'line' => lineForOffset($text, $start),
                    'old_text' => $value,
                    'new_text' => replaceNamespacePrefix($value, $oldNamespace, $newNamespace),
                    'kind' => $kind,
                ];
            }
        } elseif ($id === T_CONSTANT_ENCAPSED_STRING && $inRequire) {
            $body = literalBody($value);
            $prefix = '/' . trim($oldPath, '/') . '/';
            if ($body !== null && str_starts_with($body, $prefix)) {
                $candidate = ltrim($body, '/');
                $candidatePath = $root . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $candidate);
                if (is_file($candidatePath) && !is_link($candidatePath)) {
                    $newBody = '/' . trim($newPath, '/') . '/' . substr($body, strlen($prefix));
                    $spans[] = [
                        'file' => $relative,
                        'start' => $start + 1,
                        'end' => $end - 1,
                        'line' => lineForOffset($text, $start),
                        'old_text' => $body,
                        'new_text' => $newBody,
                        'kind' => 'php_require_path',
                    ];
                }
            }
        }
        $offset = $end;
    }

    $blocked = [];
    foreach ([$oldNamespace, '/' . trim($oldPath, '/') . '/', trim($oldPath, '/') . '/'] as $needle) {
        $cursor = 0;
        while (($found = strpos($text, $needle, $cursor)) !== false) {
            if (!covered($found, $spans)) {
                $blocked[] = [
                    'kind' => 'php_dynamic_old_identity',
                    'path' => $relative,
                    'line' => lineForOffset($text, $found),
                    'identity' => $needle,
                ];
            }
            $cursor = $found + strlen($needle);
        }
    }

    return [
        'spans' => $spans,
        'blocked' => $blocked,
        'namespaces' => array_values(array_unique($namespaces)),
    ];
}

$requestText = stream_get_contents(STDIN);
$request = json_decode($requestText, true);
if (!is_array($request)) {
    finish(['status' => 'failed', 'error' => 'PHP helper request must be a JSON object', 'blocked' => []], 1);
}
foreach (['project_root', 'old_namespace', 'new_namespace', 'old_path', 'new_path', 'moved_path', 'expected_moved_namespace', 'files'] as $key) {
    if (!array_key_exists($key, $request)) {
        finish(['status' => 'failed', 'error' => "PHP helper request is missing {$key}", 'blocked' => []], 1);
    }
}

$root = rtrim((string) $request['project_root'], DIRECTORY_SEPARATOR);
$movedPath = trim((string) $request['moved_path'], '/');
$spans = [];
$blocked = [];
$declared = [];
try {
    foreach ($request['files'] as $relative) {
        $relative = str_replace('\\', '/', (string) $relative);
        $result = analyzeFile(
            $root,
            $relative,
            (string) $request['old_namespace'],
            (string) $request['new_namespace'],
            (string) $request['old_path'],
            (string) $request['new_path'],
        );
        array_push($spans, ...$result['spans']);
        array_push($blocked, ...$result['blocked']);
        if ($relative === $movedPath || str_starts_with($relative, $movedPath . '/')) {
            $declared[$relative] = $result['namespaces'];
        }
    }
} catch (Throwable $error) {
    finish([
        'status' => 'failed',
        'error' => $error->getMessage(),
        'blocked' => [['kind' => 'php_parse_failed', 'detail' => $error->getMessage()]],
        'spans' => [],
        'declared_namespaces' => $declared,
    ], 1);
}

foreach ($declared as $relative => $namespaces) {
    if ($namespaces !== [(string) $request['expected_moved_namespace']]) {
        $blocked[] = [
            'kind' => 'php_moved_namespace_mismatch',
            'path' => $relative,
            'expected' => (string) $request['expected_moved_namespace'],
            'actual' => $namespaces,
        ];
    }
}

$dynamic = array_filter($blocked, fn (array $item): bool => $item['kind'] === 'php_dynamic_old_identity');
$mismatch = array_filter($blocked, fn (array $item): bool => $item['kind'] === 'php_moved_namespace_mismatch');
$status = $mismatch !== [] ? 'unsupported' : ($dynamic !== [] ? 'partial' : 'complete');
finish([
    'status' => $status,
    'blocked' => array_values($blocked),
    'spans' => $spans,
    'declared_namespaces' => $declared,
], $status === 'complete' ? 0 : ($status === 'partial' ? 3 : 2));
