<?php

declare(strict_types=1);

$root = dirname(__DIR__);
$iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root . '/src', FilesystemIterator::SKIP_DOTS));
foreach ($iterator as $file) {
    if ($file->getExtension() !== 'php') {
        continue;
    }
    $result = shell_exec(escapeshellcmd(PHP_BINARY) . ' -l ' . escapeshellarg($file->getPathname()));
    if (!is_string($result) || !str_contains($result, 'No syntax errors')) {
        fwrite(STDERR, "lint failed: {$file->getPathname()}\n");
        exit(1);
    }
}
echo "php-semantic-lint-ok\n";
