<?php

declare(strict_types=1);

final class StateDecoyTest
{
    private string $state = 'queued';

    private function unusedPrivate(): string
    {
        return 'test-decoy';
    }
}
