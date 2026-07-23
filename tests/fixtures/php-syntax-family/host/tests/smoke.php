<?php

declare(strict_types=1);

require dirname(__DIR__) . '/src/Standards.php';

if (handledParse() !== 'parsed' || unhandledParse() !== 'parsed') {
    fwrite(STDERR, "unexpected syntax fixture result\n");
    exit(1);
}

echo "php-syntax-ok\n";
