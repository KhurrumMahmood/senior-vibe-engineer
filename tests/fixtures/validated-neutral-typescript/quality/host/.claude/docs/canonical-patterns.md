# Canonical patterns

## Boundary validation

Validate untrusted webhook input at the ingress boundary before passing a
typed command to worker code.

The worker receives `VerifiedWebhook`, never raw headers or request bodies.
