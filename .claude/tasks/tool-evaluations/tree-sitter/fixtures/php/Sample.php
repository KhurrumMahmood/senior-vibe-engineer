<?php

namespace Demo;

use Vendor\Thing;

final class Sample
{
    public function compute(int $value): int
    {
        return helper($value);
    }
}

function helper(int $value): int
{
    return $value + 1;
}
