<?php

declare(strict_types=1);

/**
 * Emit lexical PHP comments and per-file parse failures as one JSON document.
 *
 * TOKEN_PARSE makes token_get_all apply the same grammar as the current PHP
 * runtime without loading a Composer project or executing the selected source.
 */
function analyze_file(string $path): array
{
    $source = @file_get_contents($path);
    if ($source === false) {
        return [
            'path' => $path,
            'status' => 'read-error',
            'detail' => 'could not read selected PHP source',
            'comments' => [],
        ];
    }

    try {
        $tokens = token_get_all($source, TOKEN_PARSE);
    } catch (ParseError $error) {
        return [
            'path' => $path,
            'status' => 'syntax-error',
            'detail' => $error->getMessage(),
            'comments' => [],
        ];
    }

    $comments = [];
    $offset = 0;
    $lineStart = 0;
    foreach ($tokens as $token) {
        $lexeme = is_array($token) ? $token[1] : $token;
        if (is_array($token) && ($token[0] === T_COMMENT || $token[0] === T_DOC_COMMENT)) {
            $comments[] = [
                'line' => $token[2],
                'text' => $lexeme,
                'standalone' => trim(substr($source, $lineStart, $offset - $lineStart)) === '',
            ];
        }
        $lastNewline = strrpos($lexeme, "\n");
        $offset += strlen($lexeme);
        if ($lastNewline !== false) {
            $lineStart = $offset - strlen($lexeme) + $lastNewline + 1;
        }
    }

    return [
        'path' => $path,
        'status' => 'ok',
        'comments' => $comments,
    ];
}

$files = array_slice($argv, 1);
$results = array_map('analyze_file', $files);
echo json_encode(
    ['schema_version' => 1, 'files' => $results],
    JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES
), "\n";
