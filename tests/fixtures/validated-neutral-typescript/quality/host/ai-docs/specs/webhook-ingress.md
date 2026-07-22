---
id: webhook-ingress
motivating_decision: "0001"
status: active
last_modified: "2026-03-01"
---

# Webhook ingress

## Implementation

- [ ] IM-1 Receive the signed request at `src/ingest/webhook.ts`.
- [ ] IM-2 Validate the signature and create `VerifiedWebhook` before queue
  dispatch.
