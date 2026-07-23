<?php

declare(strict_types=1);

namespace Acme\Domain;

final class AlternativeSummary
{
    /** @param list<string> $labels */
    public function __construct(public array $labels, public int $total)
    {
    }
}
