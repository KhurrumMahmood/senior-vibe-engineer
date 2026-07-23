<?php

declare(strict_types=1);

namespace Acme\Billing;

final class BillingTotalsA
{
    public function pendingTotal(array $lines): int
    {
        $total = 0;
        foreach ($lines as $line) {
            $total += (int) $line;
        }
        return $total;
    }
}
