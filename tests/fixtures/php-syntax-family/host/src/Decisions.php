<?php

declare(strict_types=1);

// decision:0001 records the syntax-only audit fixture boundary.
// decision:9999 is intentionally orphaned for the audit final artifact.
function decisionFixture(): string
{
    return 'decision fixture';
}

$commentStringDecoy = '// decision:7777';
