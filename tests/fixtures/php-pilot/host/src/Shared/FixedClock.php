<?php

declare(strict_types=1);

namespace Acme\Shared;

final class FixedClock implements Clock
{
    public function __construct(private string $value)
    {
    }

    public function now(): string
    {
        return $this->value;
    }
}
