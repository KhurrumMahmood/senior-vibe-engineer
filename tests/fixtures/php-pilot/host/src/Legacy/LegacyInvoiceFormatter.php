<?php

declare(strict_types=1);

namespace Acme\Legacy;

final class LegacyInvoiceFormatter
{
    public function format(array $invoice): string
    {
        return sprintf('%s:%d', $invoice['issued_at'], $invoice['total']);
    }
}
