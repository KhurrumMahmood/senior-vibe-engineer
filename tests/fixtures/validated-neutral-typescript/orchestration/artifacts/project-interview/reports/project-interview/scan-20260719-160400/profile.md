# Project profile — delivery operations host

This draft captures the user's supplied intent. It is human-approved as an
interview answer set but was not applied to `.engineering/project/`.

## Purpose and users

The platform team and three pilot customers use the host to accept signed
webhooks and make delivery retries observable.

## Correctness-critical workflows

- Preserve signature acceptance at the webhook boundary.
- Preserve stable delivery identity across retries.

## Risk and direction

The project is moving from fast feature work toward a durable service. Agents
slow down around authentication, duplicate delivery, and retry ownership. The
next-quarter direction is to stabilize retries before adding operator UI.

## Tradeoffs and standardization

Inline retry calculation is an intentional short-term tradeoff. Inline metric
strings and unbounded retry attempts are known bad and must not be canonized by
frequency. Canonical patterns still require human approval.

## Do-not-break surfaces

Valid signed webhook acceptance and stable delivery identifiers remain the
primary do-not-break surfaces.
