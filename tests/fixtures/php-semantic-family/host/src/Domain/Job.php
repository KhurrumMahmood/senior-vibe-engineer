<?php

declare(strict_types=1);

namespace Acme\Domain;

final class Job
{
    private string $state = 'queued';
    private string $label = 'billing';

    public function isQueued(): bool
    {
        return $this->state === 'queued';
    }

    public function start(): void
    {
        $this->state = 'running';
    }

    public function finish(): void
    {
        $this->state = 'done';
    }

    public function labelMatchesQueue(): bool
    {
        return $this->label === 'queued';
    }

    private function unusedPrivate(): string
    {
        return 'unused';
    }

    private function usedPrivate(): string
    {
        return 'used';
    }

    public function output(): string
    {
        return $this->usedPrivate();
    }
}
