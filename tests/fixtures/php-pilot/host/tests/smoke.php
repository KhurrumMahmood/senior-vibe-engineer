<?php

declare(strict_types=1);

require dirname(__DIR__) . '/src/Shared/Clock.php';
require dirname(__DIR__) . '/src/Shared/FixedClock.php';
require dirname(__DIR__) . '/src/Billing/InvoiceService.php';
require dirname(__DIR__) . '/src/Shipping/ShipmentService.php';
require dirname(__DIR__) . '/src/Consumer/CheckoutService.php';
require dirname(__DIR__) . '/src/Legacy/LegacyInvoiceFormatter.php';

use Acme\Billing\InvoiceService;
use Acme\Consumer\CheckoutService;
use Acme\Legacy\LegacyInvoiceFormatter;
use Acme\Shared\FixedClock;
use Acme\Shipping\ShipmentService;

$checkout = new CheckoutService(
    new InvoiceService(new FixedClock('2026-07-21T00:00:00Z')),
    new ShipmentService(),
);
$result = $checkout->checkout(100, 8);

if ($result['invoice']['total'] !== 108 || $result['shipment']['status'] !== 'scheduled') {
    fwrite(STDERR, "unexpected checkout result\n");
    exit(1);
}

$formatted = (new LegacyInvoiceFormatter())->format($result['invoice']);
if ($formatted !== '2026-07-21T00:00:00Z:108') {
    fwrite(STDERR, "unexpected formatted invoice\n");
    exit(1);
}
