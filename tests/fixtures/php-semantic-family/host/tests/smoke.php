<?php

declare(strict_types=1);

require dirname(__DIR__) . '/src/Domain/Job.php';

$job = new Acme\Domain\Job();
if (!$job->isQueued() || $job->labelMatchesQueue()) {
    fwrite(STDERR, "semantic fixture smoke failed\n");
    exit(1);
}
echo "php-semantic-ok\n";
