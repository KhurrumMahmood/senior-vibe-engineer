# /extract-enum risk context

This file is scout context. The `/extract-enum` orchestrator does not load it;
the `agents/enum-profiler.md` scout reads it before classifying
data-migration risks and third-party bridge literals.

## Risk buckets the proposal must cover

| Bucket | Treat as | Proposal handling |
|---|---|---|
| Case variants (`"Pending"` vs `"pending"`) | Potential persisted-data mismatch | Flag a pre-deploy distinct-value audit and, when needed, a one-off normalization migration before adding `choices=`. |
| Vendor/webhook/import literals | Third-party bridge, not an enum member | Keep raw-string comparison or mapping boundary; propose a narrow `# noqa: stringly-status: <reason>` only for the bridge site. |
| Legacy tuple choices | Divergence risk | Compare tuple values with collected literals; if either side has extras, list the divergence before proposing TextChoices. |
| Read-only literals | Possibly stale state | Mark as "read but never written"; ask the reviewer to confirm whether raw SQL, fixtures, or external services write the value. |
| Assignment-only literals | Possibly dormant caller path | Mark as "written but never checked"; route suspicious code to `/find-dormant` after the enum proposal. |

## Plain enum fallback

This skill is only for Django model fields. If the carrier is a dataclass
attribute, function return value, module constant, or command-internal sentinel,
the endpoint is a plain string-valued enum (`enum.StrEnum` on Python 3.11+, or
`class X(str, Enum)`) defined next to that carrier. Do not propose
`models.TextChoices`, migrations, or a first-party `# noqa` escape for those
non-model carriers.
