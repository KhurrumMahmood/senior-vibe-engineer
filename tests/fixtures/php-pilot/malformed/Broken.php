<?php

declare(strict_types=1);

final class Broken
{
    public function missingBrace(): void
    {
        echo 'broken';
}
