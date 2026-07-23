<?php

declare(strict_types=1);

namespace Acme\Billing;

final class BillingTotalsB
{
    public function queuedTotal(array $lines): int
    {
        $total = 0;
        foreach ($lines as $line) {
            $total += (int) $line;
        }
        return $total;
    }
}
