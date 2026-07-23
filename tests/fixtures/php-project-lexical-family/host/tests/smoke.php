<?php

declare(strict_types=1);

require dirname(__DIR__) . '/src/Billing/BillingParser.php';
require dirname(__DIR__) . '/src/Billing/BillingTotalsA.php';

use Acme\Billing\BillingParser;
use Acme\Billing\BillingTotalsA;

if ((new BillingParser())->parse('cancelled_order') !== 'cancelled') {
    fwrite(STDERR, "unexpected parser result\n");
    exit(1);
}
if ((new BillingTotalsA())->pendingTotal([4, 5]) !== 9) {
    fwrite(STDERR, "unexpected total\n");
    exit(1);
}

echo "php-project-lexical-ok\n";
