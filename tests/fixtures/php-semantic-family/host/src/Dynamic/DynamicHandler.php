<?php

declare(strict_types=1);

namespace Acme\Dynamic;

final class DynamicHandler
{
    private function runtimeOnly(): string
    {
        return 'runtime';
    }

    public function invoke(string $method): string
    {
        return $this->{$method}();
    }
}
