# Pattern briefing — boundary validation

_Topic kind: pattern_
_Generated: 2026-07-19T15:03:00Z_

## Applied to your context

**Your context:** `src/ingest/webhook.ts`

**Right (conforms):** Parse the request once and pass `VerifiedWebhook` to the
queue adapter.
- Example shape: `acceptsWebhook(message)` before dispatch.

**Wrong (violates):** Pass raw headers into retry scheduling and let worker
code decide whether the request was valid.
- Example shape: a worker import that reaches back into HTTP request state.

**Why this matters in your context specifically:** The ingress module is the
only place that can establish the verified command promised to the worker.

## Rule (one line)
> Validate untrusted webhook input at the ingress boundary before passing a typed command to worker code.

## Why

Without an ingress boundary, every consumer reinterprets untrusted headers and
payloads, producing a layer violation and duplicated security policy.

ADR 0001 codifies the consequence: queue scheduling owns retry timing after
ingress creates the verified command.

- Smell: `Layer violation` (`.claude/docs/architectural-smells.md#layer-violation`).
- Decision: ADR `0001` (`Queue boundary`).

## Exemplar (rule followed correctly)
- `ai-docs/specs/webhook-ingress.md::IM-2` — requires `VerifiedWebhook` before
  queue dispatch.

## Counter-example (rule violated in the wild)
- `reports/omnibus/latest/triage.md::omnibus-001` — one worker change mixed
  scheduling, transport retries, and dashboard formatting.

## Enforcement
- **Lint:** No lint yet.
- **Test:** No fixture guard yet.
- **Gap:** File `/decide boundary-validation-enforcement` before adding a
  mechanical guard.

## Notes
- The rule was already imperative; no rewrite was needed.
- Recommended next skill: `/decide boundary-validation-enforcement`.
