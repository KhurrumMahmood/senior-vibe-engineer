<?php

declare(strict_types=1);

$root = dirname(__DIR__);
$iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root . '/src'));
foreach ($iterator as $path) {
    if (!$path->isFile() || $path->getExtension() !== 'php') {
        continue;
    }
    passthru(escapeshellarg(PHP_BINARY) . ' -l ' . escapeshellarg($path->getPathname()), $status);
    if ($status !== 0) {
        exit($status);
    }
}
