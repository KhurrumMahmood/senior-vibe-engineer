<?php

declare(strict_types=1);

namespace Acme\Domain;

final class SummaryFactory
{
    /** @param list<int> $values */
    public function summarizeByRange(array $values): Summary
    {
        return new Summary(labels: ['range'], total: count($values));
    }

    /** @param list<int> $values */
    public function summarizeByIndex(array $values): Summary
    {
        return new Summary(labels: ['index'], total: count($values));
    }

    /** @param list<int> $values */
    public function summarizeViaRange(array $values): Summary
    {
        return $this->summarizeByRange($values);
    }

    /** @param list<int> $values */
    public function alternative(array $values): AlternativeSummary
    {
        return new AlternativeSummary(labels: ['alternative'], total: count($values));
    }
}
