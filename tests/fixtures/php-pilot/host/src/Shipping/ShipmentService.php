<?php

declare(strict_types=1);

namespace Acme\Shipping;

final class ShipmentService
{
    public function schedule(string $tier): array
    {
        return ['tier' => $tier, 'status' => 'scheduled'];
    }
}
