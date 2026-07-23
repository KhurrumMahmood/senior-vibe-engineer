<?php

declare(strict_types=1);

/**
 * Composer-scoped, deliberately narrow PHP direct-symbol facts.
 *
 * This is not a PHP AST or a replacement for PHPStan/Psalm.  It only resolves
 * first-party classes whose declared FQCN and source path agree with the host
 * Composer PSR-4 declaration, plus direct `$this` members and `new` class
 * expressions within those classes.  Dynamic names, aliases, traits,
 * inheritance, reflection, frameworks, and unknown source roots are recorded
 * as boundaries instead of guessed through.
 */

require_once dirname(__DIR__) . '/_php-project-lexical/php_project_lexical.php';

const PSE_ANALYZER = 'composer-psr4-direct-symbol-v1';

/** @return list<array{id: ?int, text: string, start: int, end: int, line: int}> */
function pse_tokens(string $source): array
{
    $raw = token_get_all($source, TOKEN_PARSE);
    $tokens = [];
    $offset = 0;
    $line = 1;
    foreach ($raw as $item) {
        $id = is_array($item) ? $item[0] : null;
        $text = is_array($item) ? $item[1] : $item;
        $tokens[] = ['id' => $id, 'text' => $text, 'start' => $offset, 'end' => $offset + strlen($text), 'line' => $line];
        $offset += strlen($text);
        $line += substr_count($text, "\n");
    }
    return $tokens;
}

function pse_significant(array $token): bool
{
    return !in_array($token['id'], [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT], true);
}

function pse_next(array $tokens, int $index): ?int
{
    for ($cursor = $index + 1; $cursor < count($tokens); $cursor++) {
        if (pse_significant($tokens[$cursor])) {
            return $cursor;
        }
    }
    return null;
}

function pse_previous(array $tokens, int $index): ?int
{
    for ($cursor = $index - 1; $cursor >= 0; $cursor--) {
        if (pse_significant($tokens[$cursor])) {
            return $cursor;
        }
    }
    return null;
}

/** @return list<int> */
function pse_depths(array $tokens): array
{
    $depth = 0;
    $rows = [];
    foreach ($tokens as $index => $token) {
        $rows[$index] = $depth;
        if ($token['text'] === '{') {
            $depth++;
        } elseif ($token['text'] === '}' && $depth > 0) {
            $depth--;
        }
    }
    return $rows;
}

function pse_match(array $tokens, int $open, string $opening, string $closing): ?int
{
    if (($tokens[$open]['text'] ?? null) !== $opening) {
        return null;
    }
    $depth = 0;
    for ($cursor = $open; $cursor < count($tokens); $cursor++) {
        if ($tokens[$cursor]['text'] === $opening) {
            $depth++;
        } elseif ($tokens[$cursor]['text'] === $closing) {
            $depth--;
            if ($depth === 0) {
                return $cursor;
            }
        }
    }
    return null;
}

function pse_name_token(?int $id): bool
{
    $nameTokens = [T_STRING, T_NS_SEPARATOR];
    foreach (['T_NAME_QUALIFIED', 'T_NAME_FULLY_QUALIFIED', 'T_NAME_RELATIVE'] as $constant) {
        if (defined($constant)) {
            $nameTokens[] = constant($constant);
        }
    }
    return $id !== null && in_array($id, $nameTokens, true);
}

/** @return array{0: string, 1: int}|null */
function pse_read_name(array $tokens, int $start): ?array
{
    $parts = [];
    $cursor = $start;
    while ($cursor < count($tokens)) {
        $token = $tokens[$cursor];
        if (!pse_significant($token)) {
            $cursor++;
            continue;
        }
        if (!pse_name_token($token['id']) && $token['text'] !== '\\') {
            break;
        }
        $parts[] = $token['text'];
        $cursor++;
    }
    if ($parts === []) {
        return null;
    }
    return [trim(implode('', $parts)), $cursor - 1];
}

/** @return list<array{start: int, end: int}> */
function pse_split_segments(array $tokens, int $start, int $end): array
{
    $segments = [];
    $segmentStart = $start;
    $depth = 0;
    for ($cursor = $start; $cursor <= $end; $cursor++) {
        $text = $tokens[$cursor]['text'];
        if (in_array($text, ['(', '[', '{'], true)) {
            $depth++;
        } elseif (in_array($text, [')', ']', '}'], true) && $depth > 0) {
            $depth--;
        }
        if ($text === ',' && $depth === 0) {
            $segments[] = ['start' => $segmentStart, 'end' => $cursor - 1];
            $segmentStart = $cursor + 1;
        }
    }
    if ($segmentStart <= $end) {
        $segments[] = ['start' => $segmentStart, 'end' => $end];
    }
    return $segments;
}

/** @return array<string, string> */
function pse_aliases(array $tokens, array $depths, string $namespace, array &$boundaries): array
{
    $aliases = [];
    foreach ($tokens as $index => $token) {
        if ($token['id'] !== T_USE || $depths[$index] !== 0) {
            continue;
        }
        $start = pse_next($tokens, $index);
        if ($start === null) {
            continue;
        }
        if (in_array($tokens[$start]['id'], [T_FUNCTION, T_CONST], true) || $tokens[$start]['text'] === '{') {
            $boundaries[] = ['kind' => 'unresolved_import', 'line' => $token['line'], 'detail' => 'function, const, or grouped import'];
            continue;
        }
        $read = pse_read_name($tokens, $start);
        if ($read === null) {
            $boundaries[] = ['kind' => 'unresolved_import', 'line' => $token['line'], 'detail' => 'unparseable import'];
            continue;
        }
        [$target, $last] = $read;
        $alias = basename(str_replace('\\', '/', trim($target, '\\')));
        $next = pse_next($tokens, $last);
        if ($next !== null && $tokens[$next]['id'] === T_AS) {
            $name = pse_next($tokens, $next);
            if ($name === null || $tokens[$name]['id'] !== T_STRING) {
                $boundaries[] = ['kind' => 'unresolved_import', 'line' => $token['line'], 'detail' => 'invalid import alias'];
                continue;
            }
            $alias = $tokens[$name]['text'];
        }
        $aliases[strtolower($alias)] = trim($target, '\\');
    }
    return $aliases;
}

function pse_resolve(string $raw, string $namespace, array $aliases): ?string
{
    $raw = trim($raw);
    if ($raw === '' || str_contains($raw, '{') || str_contains($raw, '$')) {
        return null;
    }
    if (str_starts_with($raw, '\\')) {
        return trim($raw, '\\');
    }
    $parts = explode('\\', $raw);
    $first = strtolower($parts[0]);
    if (isset($aliases[$first])) {
        array_shift($parts);
        return $aliases[$first] . ($parts === [] ? '' : '\\' . implode('\\', $parts));
    }
    return $namespace === '' ? $raw : $namespace . '\\' . $raw;
}

/** @return array<string, string> */
function pse_psr4(array $snapshot): array
{
    $mappings = $snapshot['composer_manifest']['psr4'] ?? [];
    $result = [];
    foreach ($mappings as $prefix => $root) {
        if (is_string($prefix) && is_string($root) && str_ends_with($prefix, '\\')) {
            $result[trim($prefix, '\\')] = trim(str_replace('\\', '/', $root), '/');
        }
    }
    ksort($result);
    return $result;
}

function pse_psr4_owned(string $fqcn, string $file, array $mappings): bool
{
    foreach ($mappings as $prefix => $root) {
        if ($fqcn === $prefix || str_starts_with($fqcn, $prefix . '\\')) {
            $suffix = ltrim(substr($fqcn, strlen($prefix)), '\\');
            $expected = trim($root . '/' . str_replace('\\', '/', $suffix) . '.php', '/');
            if ($file === $expected) {
                return true;
            }
        }
    }
    return false;
}

/** @return array{namespace: string, aliases: array<string,string>, classes: list<array<string,mixed>>, boundaries: list<array<string,mixed>>} */
function pse_parse_file(string $file, string $source): array
{
    $tokens = pse_tokens($source);
    $depths = pse_depths($tokens);
    $boundaries = [];
    $namespace = '';
    $namespaces = 0;
    foreach ($tokens as $index => $token) {
        if ($token['id'] !== T_NAMESPACE || $depths[$index] !== 0) {
            continue;
        }
        $namespaces++;
        $start = pse_next($tokens, $index);
        $read = $start === null ? null : pse_read_name($tokens, $start);
        if ($read === null) {
            $boundaries[] = ['kind' => 'unresolved_namespace', 'line' => $token['line'], 'detail' => 'unnamed or braced namespace'];
            continue;
        }
        $namespace = trim($read[0], '\\');
    }
    if ($namespaces > 1) {
        $boundaries[] = ['kind' => 'multiple_namespaces', 'line' => 1, 'detail' => 'only one namespace is resolved'];
    }
    $aliases = pse_aliases($tokens, $depths, $namespace, $boundaries);
    $classes = [];
    foreach ($tokens as $index => $token) {
        if (!in_array($token['id'], array_filter([T_CLASS, defined('T_ENUM') ? constant('T_ENUM') : null]), true)
            || $depths[$index] !== 0) {
            continue;
        }
        $previous = pse_previous($tokens, $index);
        if ($previous !== null && $tokens[$previous]['id'] === T_NEW) {
            continue;
        }
        $nameIndex = pse_next($tokens, $index);
        if ($nameIndex === null || $tokens[$nameIndex]['id'] !== T_STRING) {
            $boundaries[] = ['kind' => 'unresolved_class', 'line' => $token['line'], 'detail' => 'anonymous or malformed declaration'];
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
        $close = $open === null ? null : pse_match($tokens, $open, '{', '}');
        if ($close === null) {
            $boundaries[] = ['kind' => 'unresolved_class', 'line' => $token['line'], 'detail' => 'unbalanced class body'];
            continue;
        }
        $isFinal = false;
        for ($cursor = $index - 1; $cursor >= 0; $cursor--) {
            if (in_array($tokens[$cursor]['text'], [';', '{', '}'], true)) {
                break;
            }
            if ($tokens[$cursor]['id'] === T_FINAL) {
                $isFinal = true;
            }
        }
        $class = [
            'file' => $file,
            'line' => $token['line'],
            'name' => $tokens[$nameIndex]['text'],
            'fqcn' => $namespace === '' ? $tokens[$nameIndex]['text'] : $namespace . '\\' . $tokens[$nameIndex]['text'],
            'kind' => $token['id'] === T_CLASS ? 'class' : 'enum',
            'final' => $isFinal,
            'span' => ppl_span($source, $token['start'], $tokens[$close]['end']),
            'source_sha256' => ppl_hash($source),
            'methods' => [], 'properties' => [], 'new_expressions' => [], 'member_operations' => [], 'boundaries' => [],
            '_open' => $open, '_close' => $close, '_tokens' => $tokens, '_depths' => $depths,
        ];
        pse_parse_class_members($class, $source, $namespace, $aliases);
        $classes[] = $class;
    }
    return ['namespace' => $namespace, 'aliases' => $aliases, 'classes' => $classes, 'boundaries' => $boundaries];
}

function pse_member_visibility(array $tokens, int $function, int $classDepth): string
{
    $visibility = 'public';
    for ($cursor = $function - 1; $cursor >= 0; $cursor--) {
        if (in_array($tokens[$cursor]['text'], [';', '{', '}'], true)) {
            break;
        }
        if ($tokens[$cursor]['id'] === T_PRIVATE) {
            return 'private';
        }
        if ($tokens[$cursor]['id'] === T_PROTECTED) {
            return 'protected';
        }
        if ($tokens[$cursor]['id'] === T_PUBLIC) {
            $visibility = 'public';
        }
    }
    return $visibility;
}

/** @return list<array{name: string, required: bool, promoted: bool, type: ?string}> */
function pse_parameters(array $tokens, int $open, int $close, string $namespace, array $aliases): array
{
    $parameters = [];
    foreach (pse_split_segments($tokens, $open + 1, $close - 1) as $segment) {
        $name = null;
        $required = true;
        $promoted = false;
        $type = null;
        for ($cursor = $segment['start']; $cursor <= $segment['end']; $cursor++) {
            $token = $tokens[$cursor];
            if ($token['text'] === '=') {
                $required = false;
            }
            if (in_array($token['id'], [T_PUBLIC, T_PRIVATE, T_PROTECTED], true)) {
                $promoted = true;
            }
            if ($token['id'] === T_VARIABLE) {
                $name = ltrim($token['text'], '$');
                break;
            }
        }
        if ($name === null) {
            continue;
        }
        for ($cursor = $segment['start']; $cursor <= $segment['end']; $cursor++) {
            if ($tokens[$cursor]['id'] === T_VARIABLE) {
                break;
            }
            $typeTokenIds = [T_STRING];
            foreach (['T_ARRAY', 'T_CALLABLE', 'T_ITERABLE', 'T_OBJECT'] as $constant) {
                if (defined($constant)) {
                    $typeTokenIds[] = constant($constant);
                }
            }
            if (in_array($tokens[$cursor]['id'], $typeTokenIds, true)) {
                $read = pse_read_name($tokens, $cursor);
                if ($read !== null) {
                    $raw = $read[0];
                    if (!in_array(strtolower($raw), ['string', 'int', 'float', 'bool', 'array', 'mixed', 'iterable', 'callable', 'object'], true)) {
                        $type = pse_resolve($raw, $namespace, $aliases);
                    } else {
                        $type = strtolower($raw);
                    }
                }
                break;
            }
        }
        $parameters[] = ['name' => $name, 'required' => $required, 'promoted' => $promoted, 'type' => $type];
    }
    return $parameters;
}

function pse_parse_class_members(array &$class, string $source, string $namespace, array $aliases): void
{
    $tokens = $class['_tokens'];
    $depths = $class['_depths'];
    $classDepth = $depths[$class['_open']];
    for ($index = $class['_open'] + 1; $index < $class['_close']; $index++) {
        $token = $tokens[$index];
        if ($token['id'] !== T_FUNCTION || $depths[$index] !== $classDepth + 1) {
            continue;
        }
        $nameIndex = pse_next($tokens, $index);
        if ($nameIndex !== null && $tokens[$nameIndex]['text'] === '&') {
            $nameIndex = pse_next($tokens, $nameIndex);
        }
        if ($nameIndex === null || $tokens[$nameIndex]['id'] !== T_STRING) {
            $class['boundaries'][] = ['kind' => 'anonymous_or_magic_method', 'line' => $token['line'], 'detail' => 'unnamed function'];
            continue;
        }
        $paren = pse_next($tokens, $nameIndex);
        $parenClose = $paren === null ? null : pse_match($tokens, $paren, '(', ')');
        if ($parenClose === null) {
            $class['boundaries'][] = ['kind' => 'unresolved_method', 'line' => $token['line'], 'detail' => 'unbalanced parameter list'];
            continue;
        }
        $bodyOpen = null;
        for ($cursor = $parenClose + 1; $cursor < $class['_close']; $cursor++) {
            if ($tokens[$cursor]['text'] === '{') {
                $bodyOpen = $cursor;
                break;
            }
            if ($tokens[$cursor]['text'] === ';') {
                break;
            }
        }
        $bodyClose = $bodyOpen === null ? null : pse_match($tokens, $bodyOpen, '{', '}');
        if ($bodyClose === null) {
            $class['boundaries'][] = ['kind' => 'unresolved_method', 'line' => $token['line'], 'detail' => 'no concrete body'];
            continue;
        }
        $name = $tokens[$nameIndex]['text'];
        $returnType = null;
        $afterParameters = pse_next($tokens, $parenClose);
        if ($afterParameters !== null && $tokens[$afterParameters]['text'] === ':') {
            $typeStart = pse_next($tokens, $afterParameters);
            $readType = $typeStart === null ? null : pse_read_name($tokens, $typeStart);
            if ($readType !== null) {
                $rawType = $readType[0];
                $returnType = in_array(strtolower($rawType), ['string', 'int', 'float', 'bool', 'array', 'mixed', 'iterable', 'callable', 'object', 'void', 'never'], true)
                    ? strtolower($rawType)
                    : pse_resolve($rawType, $namespace, $aliases);
            }
        }
        $method = [
            'file' => $class['file'], 'line' => $token['line'], 'name' => $name,
            'fqmn' => $class['fqcn'] . '::' . $name,
            'visibility' => pse_member_visibility($tokens, $index, $classDepth),
            'parameters' => pse_parameters($tokens, $paren, $parenClose, $namespace, $aliases),
            'return_type' => $returnType,
            'span' => ppl_span($source, $token['start'], $tokens[$bodyClose]['end']),
            'source_sha256' => $class['source_sha256'],
            'body_open' => $bodyOpen, 'body_close' => $bodyClose,
            'direct_calls' => [], 'return_news' => [], 'dynamic_boundary' => false,
        ];
        pse_scan_method_body($class, $method, $source, $namespace, $aliases);
        $class['methods'][] = $method;
    }
    foreach ($class['methods'] as $method) {
        if (strtolower($method['name']) !== '__construct') {
            continue;
        }
        foreach ($method['parameters'] as $parameter) {
            if ($parameter['promoted']) {
                $class['properties'][] = [
                    'name' => $parameter['name'], 'type' => $parameter['type'], 'visibility' => 'promoted',
                    'line' => $method['line'], 'declared_in_constructor' => true,
                ];
            }
        }
    }
    pse_scan_properties($class, $namespace, $aliases);
}

function pse_scan_method_body(array &$class, array &$method, string $source, string $namespace, array $aliases): void
{
    $tokens = $class['_tokens'];
    $depths = $class['_depths'];
    for ($index = $method['body_open'] + 1; $index < $method['body_close']; $index++) {
        $token = $tokens[$index];
        if ($token['id'] === T_NEW) {
            $start = pse_next($tokens, $index);
            $read = $start === null ? null : pse_read_name($tokens, $start);
            if ($read === null) {
                $class['boundaries'][] = ['kind' => 'dynamic_new', 'line' => $token['line'], 'detail' => 'new expression does not name a class'];
                $method['dynamic_boundary'] = true;
                continue;
            }
            [$raw, $last] = $read;
            $open = pse_next($tokens, $last);
            $close = $open === null ? null : pse_match($tokens, $open, '(', ')');
            if ($open === null || $close === null) {
                $class['boundaries'][] = ['kind' => 'unresolved_new', 'line' => $token['line'], 'detail' => 'direct class without a balanced argument list'];
                continue;
            }
            $named = [];
            foreach (pse_split_segments($tokens, $open + 1, $close - 1) as $segment) {
                $first = pse_next($tokens, $segment['start'] - 1);
                $colon = $first === null ? null : pse_next($tokens, $first);
                if ($first !== null && $colon !== null && $tokens[$first]['id'] === T_STRING && $tokens[$colon]['text'] === ':') {
                    $named[] = $tokens[$first]['text'];
                }
            }
            $row = [
                'file' => $class['file'], 'line' => $token['line'], 'owner_method' => $method['fqmn'],
                'raw_class' => $raw, 'class' => pse_resolve($raw, $namespace, $aliases),
                'named_arguments' => array_values(array_unique($named)),
                'span' => ppl_span($source, $token['start'], $tokens[$close]['end']),
                'source_sha256' => $class['source_sha256'],
            ];
            $class['new_expressions'][] = $row;
            if ($index > $method['body_open'] && ($previous = pse_previous($tokens, $index)) !== null && $tokens[$previous]['id'] === T_RETURN) {
                $method['return_news'][] = $row;
            }
        }
        if ($token['id'] !== T_VARIABLE || $token['text'] !== '$this') {
            continue;
        }
        $arrow = pse_next($tokens, $index);
        $member = $arrow === null ? null : pse_next($tokens, $arrow);
        if ($arrow === null || $tokens[$arrow]['text'] !== '->' || $member === null) {
            continue;
        }
        if ($tokens[$member]['id'] !== T_STRING) {
            $method['dynamic_boundary'] = true;
            $class['boundaries'][] = ['kind' => 'dynamic_member_dispatch', 'line' => $token['line'], 'detail' => 'non-literal $this member'];
            continue;
        }
        $after = pse_next($tokens, $member);
        if ($after !== null && $tokens[$after]['text'] === '(') {
            $method['direct_calls'][] = ['name' => $tokens[$member]['text'], 'line' => $token['line']];
            continue;
        }
        $operation = null;
        if ($after !== null && $tokens[$after]['text'] === '=') {
            $operation = 'assignment';
        } elseif ($after !== null && in_array($tokens[$after]['text'], ['==', '===', '!=', '!=='], true)) {
            $operation = 'comparison';
        }
        if ($operation === null) {
            $previous = pse_previous($tokens, $index);
            if ($previous !== null && in_array($tokens[$previous]['text'], ['==', '===', '!=', '!=='], true)) {
                $operation = 'comparison';
            }
        }
        if ($operation !== null) {
            $literal = null;
            $literalIndex = $after === null ? null : pse_next($tokens, $after);
            if ($literalIndex !== null && $tokens[$literalIndex]['id'] === T_CONSTANT_ENCAPSED_STRING) {
                $literal = trim($tokens[$literalIndex]['text'], "'\"");
            }
            $class['member_operations'][] = [
                'file' => $class['file'], 'line' => $token['line'], 'owner_method' => $method['fqmn'],
                'member' => $tokens[$member]['text'], 'operation' => $operation, 'literal' => $literal,
                'source_sha256' => $class['source_sha256'],
            ];
        }
    }
}

function pse_scan_properties(array &$class, string $namespace, array $aliases): void
{
    $tokens = $class['_tokens'];
    $depths = $class['_depths'];
    $classDepth = $depths[$class['_open']];
    for ($index = $class['_open'] + 1; $index < $class['_close']; $index++) {
        if ($tokens[$index]['id'] !== T_VARIABLE || $depths[$index] !== $classDepth + 1) {
            continue;
        }
        $insideFunctionHeader = false;
        for ($cursor = $index - 1; $cursor >= $class['_open']; $cursor--) {
            if (in_array($tokens[$cursor]['text'], [';', '{', '}'], true)) {
                break;
            }
            if ($tokens[$cursor]['id'] === T_FUNCTION) {
                $insideFunctionHeader = true;
                break;
            }
        }
        if ($insideFunctionHeader) {
            continue;
        }
        $previous = pse_previous($tokens, $index);
        $scalarTypeTokens = [T_STRING];
        foreach (['T_ARRAY', 'T_CALLABLE', 'T_ITERABLE', 'T_OBJECT'] as $constant) {
            if (defined($constant)) {
                $scalarTypeTokens[] = constant($constant);
            }
        }
        if ($previous === null || !in_array($tokens[$previous]['id'], $scalarTypeTokens, true)) {
            continue;
        }
        $name = ltrim($tokens[$index]['text'], '$');
        $type = strtolower($tokens[$previous]['text']);
        $visibility = 'public';
        for ($cursor = $index - 1; $cursor >= $class['_open']; $cursor--) {
            if (in_array($tokens[$cursor]['text'], [';', '{', '}'], true)) {
                break;
            }
            if ($tokens[$cursor]['id'] === T_PRIVATE) {
                $visibility = 'private';
            } elseif ($tokens[$cursor]['id'] === T_PROTECTED) {
                $visibility = 'protected';
            }
        }
        $class['properties'][] = ['name' => $name, 'type' => $type, 'visibility' => $visibility, 'line' => $tokens[$index]['line'], 'declared_in_constructor' => false];
    }
}

function pse_semantic_tool(string $root): array
{
    $candidates = [
        ['kind' => 'phpstan', 'config' => 'phpstan.neon', 'binary' => 'vendor/bin/phpstan'],
        ['kind' => 'phpstan', 'config' => 'phpstan.neon.dist', 'binary' => 'vendor/bin/phpstan'],
        ['kind' => 'psalm', 'config' => 'psalm.xml', 'binary' => 'vendor/bin/psalm'],
        ['kind' => 'psalm', 'config' => 'psalm.xml.dist', 'binary' => 'vendor/bin/psalm'],
    ];
    foreach ($candidates as $candidate) {
        $config = $root . DIRECTORY_SEPARATOR . $candidate['config'];
        $binary = $root . DIRECTORY_SEPARATOR . $candidate['binary'];
        if (!is_file($config) && !is_file($binary)) {
            continue;
        }
        if (!is_file($config) || !is_file($binary) || is_link($config) || is_link($binary) || !is_executable($binary)) {
            return ['state' => 'incomplete', 'kind' => $candidate['kind'], 'configuration' => $candidate['config'], 'binary' => $candidate['binary'], 'reason' => 'configured analyzer is missing, unsafe, or not executable'];
        }
        $probe = ppl_process([$binary, '--version'], $root);
        if ($probe['returncode'] !== 0) {
            return ['state' => 'failed', 'kind' => $candidate['kind'], 'configuration' => $candidate['config'], 'binary' => $candidate['binary'], 'reason' => 'configured analyzer version probe failed'];
        }
        return [
            'state' => 'configured', 'kind' => $candidate['kind'], 'configuration' => $candidate['config'], 'binary' => $candidate['binary'],
            'configuration_sha256' => ppl_hash((string) file_get_contents($config)),
            'version' => trim($probe['stdout'] !== '' ? $probe['stdout'] : $probe['stderr']),
        ];
    }
    return ['state' => 'not-configured', 'reason' => 'no project-local PHPStan/Psalm configuration and executable pair'];
}

/** @return array<string,mixed> */
function pse_collect(string $root, string $target, string $php, string $composer, string $minimumPhp = '8.1.0', string $minimumComposer = '2.2.0'): array
{
    $snapshot = ppl_collect_snapshot($root, $target, $php, $composer, $minimumPhp, $minimumComposer);
    $status = $snapshot['status'];
    $errors = $snapshot['errors'];
    $mappings = pse_psr4($snapshot);
    if ($mappings === []) {
        $status = ppl_status_merge($status, 'partial');
        $errors[] = 'composer-psr4-mapping-required';
    }
    $tool = pse_semantic_tool($root);
    if ($tool['state'] === 'incomplete') {
        $status = ppl_status_merge($status, 'partial');
        $errors[] = 'configured-semantic-tool-incomplete';
    } elseif ($tool['state'] === 'failed') {
        $status = ppl_status_merge($status, 'failed');
        $errors[] = 'configured-semantic-tool-failed';
    }
    $classes = [];
    $boundaries = [];
    foreach ($snapshot['inventory'] as $row) {
        if (($row['role'] ?? null) !== 'eligible' || ($row['parse_state'] ?? null) === 'syntax-error') {
            continue;
        }
        foreach ($row['unresolved'] ?? [] as $unresolved) {
            $boundaries[] = [
                'file' => $row['file'], 'kind' => 'lexical_unresolved_boundary',
                'line' => 0, 'detail' => ($unresolved['symbol'] ?? 'unknown') . ': ' . ($unresolved['reason'] ?? 'unresolved'),
            ];
        }
        try {
            $parsed = pse_parse_file($row['file'], $row['_source']);
        } catch (Throwable $error) {
            $status = ppl_status_merge($status, 'partial');
            $errors[] = 'semantic-parser-failed:' . $row['file'];
            $boundaries[] = ['file' => $row['file'], 'kind' => 'semantic_parser_failed', 'detail' => $error->getMessage()];
            continue;
        }
        foreach ($parsed['boundaries'] as $boundary) {
            $boundaries[] = ['file' => $row['file'], ...$boundary];
        }
        foreach ($parsed['classes'] as $class) {
            if (!pse_psr4_owned($class['fqcn'], $class['file'], $mappings)) {
                $status = ppl_status_merge($status, 'partial');
                $errors[] = 'composer-class-identity-unresolved:' . $class['file'];
                $boundaries[] = ['file' => $class['file'], 'kind' => 'composer_class_identity_unresolved', 'line' => $class['line'], 'detail' => $class['fqcn']];
                continue;
            }
            foreach ($class['boundaries'] as $boundary) {
                $boundaries[] = ['file' => $class['file'], ...$boundary];
            }
            unset($class['_open'], $class['_close'], $class['_tokens'], $class['_depths']);
            foreach ($class['methods'] as &$method) {
                unset($method['body_open'], $method['body_close']);
            }
            unset($method);
            $classes[] = $class;
        }
    }
    if ($classes === [] && $status === 'complete') {
        $status = 'partial';
        $errors[] = 'no-composer-owned-class-symbols';
    }
    $index = [];
    foreach ($classes as $class) {
        $index[$class['fqcn']] = true;
    }
    foreach ($classes as &$class) {
        foreach ($class['new_expressions'] as &$expression) {
            if (!is_string($expression['class']) || !isset($index[$expression['class']])) {
                $expression['resolution'] = 'unresolved';
                $boundaries[] = ['file' => $expression['file'], 'kind' => 'new_target_unresolved', 'line' => $expression['line'], 'detail' => $expression['raw_class']];
            } else {
                $expression['resolution'] = 'composer-psr4';
            }
        }
        unset($expression);
        foreach ($class['methods'] as &$method) {
            foreach ($method['return_news'] as &$expression) {
                $expression['resolution'] = is_string($expression['class']) && isset($index[$expression['class']]) ? 'composer-psr4' : 'unresolved';
            }
            unset($expression);
        }
        unset($method);
    }
    unset($class);
    $lock = $root . DIRECTORY_SEPARATOR . 'composer.lock';
    if (is_link($lock)) {
        $status = ppl_status_merge($status, 'partial');
        $errors[] = 'composer-lock-unsafe-symlink';
    }
    $identity = [
        'composer_name' => $snapshot['composer_manifest']['name'] ?? null,
        'composer_json_sha256' => $snapshot['composer_manifest']['sha256'] ?? null,
        'composer_lock' => is_file($lock) && !is_link($lock)
            ? ['state' => 'present', 'sha256' => ppl_hash((string) file_get_contents($lock))]
            : ['state' => is_link($lock) ? 'unsafe-symlink' : 'absent'],
        'psr4' => $mappings,
        'composer_validate_state' => $snapshot['composer_validate']['state'],
    ];
    if (!ppl_sources_preserved($snapshot)) {
        $status = 'failed';
        $errors[] = 'unexpected-source-mutation';
    }
    return [
        'schema_version' => 1,
        'language' => 'php',
        'analyzer' => PSE_ANALYZER,
        'status' => $status,
        'failure_kind' => $errors === [] ? null : $errors[0],
        'errors' => array_values(array_unique($errors)),
        'project_identity' => $identity,
        'semantic_tool' => $tool,
        'target' => $snapshot['target'],
        'source_manifest_sha256' => $snapshot['source_manifest_sha256'],
        'source_inventory' => ppl_public_snapshot($snapshot),
        'classes' => $classes,
        'boundaries' => $boundaries,
        'source_preserved' => ppl_sources_preserved($snapshot),
        'limits' => [
            'Composer PSR-4 plus direct `$this`/`new` relationships only; no general PHP type inference or call graph.',
            'PHPStan/Psalm are recorded when project-configured, but this provider never fabricates their symbol/reference output.',
            'Dynamic calls, class_alias, reflection, frameworks, traits, inheritance, containers, and external consumers remain unresolved.',
        ],
    ];
}

function pse_cli_main(array $argv): int
{
    try {
        $options = ppl_cli($argv, ['project-root', 'target'], [
            'php' => 'php', 'composer' => 'composer', 'minimum-php' => '8.1.0', 'minimum-composer' => '2.2.0',
        ]);
        $root = ppl_project_root($options['project-root']);
        $target = ppl_inside_path($root, $options['target'], 'target');
        $facts = pse_collect($root, $target, $options['php'], $options['composer'], $options['minimum-php'], $options['minimum-composer']);
        fwrite(STDOUT, json_encode($facts, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n");
        return ppl_terminal_code(['status' => $facts['status']]);
    } catch (Throwable $error) {
        fwrite(STDERR, $error->getMessage() . "\n");
        return 64;
    }
}

if (realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    exit(pse_cli_main($argv));
}
