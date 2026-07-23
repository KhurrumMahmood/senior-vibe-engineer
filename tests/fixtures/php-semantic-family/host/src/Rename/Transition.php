<?php

declare(strict_types=1);

namespace Acme\Rename;

final class Transition
{
    public function convert(LegacyStatus $value): CanonicalStatus
    {
        return new CanonicalStatus();
    }

    public function retiredCopy(): string
    {
        return 'legacy status';
    }
}
