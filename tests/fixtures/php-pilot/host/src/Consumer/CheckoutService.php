<?php

declare(strict_types=1);

namespace Acme\Consumer;

use Acme\Billing\InvoiceService;
use Acme\Shipping\ShipmentService;

final class CheckoutService
{
    public function __construct(
        private InvoiceService $invoices,
        private ShipmentService $shipments,
    ) {
    }

    public function checkout(int $subtotal, int $tax): array
    {
        return [
            'invoice' => $this->invoices->issue($subtotal, $tax),
            'shipment' => $this->shipments->schedule('standard'),
        ];
    }
}
