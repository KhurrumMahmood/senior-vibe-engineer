<?php

declare(strict_types=1);

function routeInvoice(array $states): int
{
    $total = 0;
    if ($states !== [] && count($states) > 0) {
        foreach ($states as $state) {
            if ($state === 'open') {
                $total++;
            }
        }
    }
    for ($index = 0; $index < 1; $index++) {
        $total += $index;
    }
    while (false) {
        $total++;
    }
    try {
        throw new RuntimeException('fixture');
    } catch (RuntimeException) {
        $total++;
    }
    switch ($total) {
        case 1:
            return 1;
        default:
            return $total;
    }
}

function closureDecoy(array $states): int
{
    $callback = function (array $items): int {
        $count = 0;
        foreach ($items as $item) {
            if ($item === 'open' && $count === 0) {
                $count++;
            }
        }
        return $count;
    };
    return $callback($states);
}
