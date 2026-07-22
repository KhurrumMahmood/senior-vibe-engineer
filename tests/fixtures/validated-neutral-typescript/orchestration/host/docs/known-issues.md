# Known issues

## retry-attempt-cap

`nextAttempt` increments without a ceiling. The pilot traffic is currently
small, but a poison delivery can consume unbounded worker attempts after retry
dispatch is connected.
