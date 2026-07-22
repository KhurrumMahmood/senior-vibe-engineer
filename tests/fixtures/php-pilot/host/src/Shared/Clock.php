<?php

declare(strict_types=1);

namespace Acme\Shared;

interface Clock
{
    public function now(): string;
}
