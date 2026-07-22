# ADR 0001 — Verify delivery signatures at entry

## Incident

A retry worker once accepted a payload whose transport signature had already
been discarded, so the failure could not be attributed at the HTTP boundary.

## Decision

Every externally supplied delivery is authenticated and structurally validated
at its entry boundary before internal work is scheduled. Internal workers may
defend again, but they do not become the first trust boundary.
