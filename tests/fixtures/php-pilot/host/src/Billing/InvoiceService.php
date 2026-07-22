<?php

declare(strict_types=1);

namespace Acme\Billing;

use Acme\Shared\Clock;

final class InvoiceService
{
    public function __construct(private Clock $clock)
    {
    }

    // Create the invoice response.
    public function issue(int $subtotal, int $tax): array
    {
        return [
            'issued_at' => $this->clock->now(),
            'total' => $subtotal + $tax,
        ];
    }
}
