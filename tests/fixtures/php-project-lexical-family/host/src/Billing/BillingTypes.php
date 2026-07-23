<?php

declare(strict_types=1);

namespace Acme\Billing;

enum BillingTypes: string
{
    case OPEN = 'open';
    case CANCELLED = 'cancelled';
}
