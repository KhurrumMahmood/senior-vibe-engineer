<?php

declare(strict_types=1);

$root = dirname(__DIR__);
$paths = array_merge(
    glob($root . '/src/*/*.php') ?: [],
    [__FILE__, $root . '/tests/smoke.php'],
);

foreach ($paths as $path) {
    $command = escapeshellarg(PHP_BINARY) . ' -l ' . escapeshellarg($path);
    passthru($command, $status);
    if ($status !== 0) {
        exit($status);
    }
}
