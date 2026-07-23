<?php

declare(strict_types=1);

namespace Acme\Billing;

final class BillingValidator
{
    public function accepts(string $state): bool
    {
        return in_array($state, ['open', 'cancelled'], true);
    }
}
