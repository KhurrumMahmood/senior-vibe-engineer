<?php

declare(strict_types=1);

namespace Acme\Domain;

final class RequestFactory
{
    public function oldRequest(): RequestOptions
    {
        return new RequestOptions(id: 'old', stage: 'live');
    }

    public function newRequestOne(): RequestOptions
    {
        return new RequestOptions(id: 'one', region: 'us', stage: 'live');
    }

    public function newRequestTwo(): RequestOptions
    {
        return new RequestOptions(id: 'two', region: 'us', stage: 'live');
    }

    public function newRequestThree(): RequestOptions
    {
        return new RequestOptions(id: 'three', region: 'us', stage: 'live');
    }
}
