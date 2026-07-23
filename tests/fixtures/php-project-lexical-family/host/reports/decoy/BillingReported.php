<?php

declare(strict_types=1);

// cancelled_order is an excluded report decoy.
function excluded_report_clone(array $lines): int
{
    $total = 0;
    foreach ($lines as $line) {
        $total += (int) $line;
    }
    return $total;
}
