# Cached input contract

`/triage-debt` can aggregate a host's retained evidence from
`reports/triage-debt/cache/current` (or `$TRIAGE_CACHE`) without invoking an
uninstalled project registry runtime.

The cache is evidence, not an authority replacement. Its producer remains the
host's own spec, decision, and detector tooling. The installed skill must copy
the retained files into its scan output, list missing files in `inputs.md`, and
avoid treating a missing input as a zero-finding result.
