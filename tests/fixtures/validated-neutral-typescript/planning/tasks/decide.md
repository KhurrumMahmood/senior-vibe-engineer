# Natural task: decide webhook signature ownership

You are working in the TypeScript planning host. Author one proposed ADR for
the material choice of where webhook signatures are verified. The rule should
bind future HTTP entry points without forcing a queue or framework choice.

Compare verification at the HTTP boundary, only in the delivery worker, and at
both boundaries. Record trade-offs and a verification approach. Do not edit the
application source or broaden the decision into retry scheduling.
