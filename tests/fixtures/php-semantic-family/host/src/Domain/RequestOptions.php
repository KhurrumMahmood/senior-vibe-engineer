<?php

declare(strict_types=1);

namespace Acme\Domain;

final class RequestOptions
{
    public function __construct(
        public string $id,
        public string $region,
        public string $stage,
    ) {
    }
}
