# Natural task: interview the delivery host

Create a draft project profile, not an applied profile. This host exists for
the platform team and three pilot customers to accept signed webhooks and make
delivery retries observable. Signature acceptance and stable delivery identity
are correctness-critical. It is moving from fast feature work toward a durable
service; agents should slow down around authentication, duplicate delivery,
and retry ownership.

Inline retry calculation is an intentional short-term tradeoff. Inline metric
strings and unbounded retry attempts are known-bad patterns that must not
become doctrine. Over the next quarter, stabilize retry behavior before adding
operator UI. Capture anything still unresolved as an open question, and do not
edit application source.
