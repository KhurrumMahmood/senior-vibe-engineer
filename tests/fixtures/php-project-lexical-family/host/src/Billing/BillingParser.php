<?php

declare(strict_types=1);

namespace Acme\Billing;

final class BillingParser
{
    public function parse(string $state): string
    {
        if ($state === 'cancelled_order') {
            return 'cancelled';
        }

        return 'open';
    }
}
