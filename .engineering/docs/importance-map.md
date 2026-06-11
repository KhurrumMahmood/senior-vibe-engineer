# Importance map

> This file is optional. When absent, `/find-orphaned-ideas --attention-gap`
> emits "No importance map declared — see ADR 0016" and exits cleanly.
> Copy this file into your host project, replace the example areas with
> areas your team actually defends, and update the locators as the
> codebase evolves.

Project owners declare which areas are high-value enough that
`/find-orphaned-ideas --attention-gap` should surface neglect against
them. This map is declarative — it answers "what the team decided to
defend", not "what the system noticed". See ADR 0016 (Importance Map
Shape) for the format contract and the alternatives considered.

Trigger: read this when authoring the importance map for your host
project, or when calibrating `/find-orphaned-ideas --attention-gap`.

## Shape (per ADR 0016)

Each area is a `## <area name>` heading. The area declares:

- A single `Tier:` line. Tier vocabulary is `critical` (project would
  break without it), `core` (load-bearing but replaceable),
  `supporting` (real work but not central). The skill ranks `critical`
  strictly above `core` strictly above `supporting`.
- A `Locators:` block listing one or more bullets. Each bullet's
  leading backtick-delimited token is either:
  - `path:<folder-path-or-glob>` — matches filesystem scans (TODO,
    dead-prototype). Globs are allowed.
  - `kind:<subsystem_kind>` — matches ledger projections (stale,
    harvest, stale-plans). `subsystem_kind` is the canonical taxonomy
    in `.claude/docs/idea-ledger.md`.
- An optional `Notes:` line for free-form context or ADR / spec links.

The drift detector flags `path:` entries whose path no longer exists
on disk, and `kind:` entries that do not appear in the ledger's
projected `subsystem_kind` set. Drift findings render under each area
without suppressing the area itself.

## Example areas (uncomment and adapt for your host project)

<!--
## Extraction runtime

Tier: critical

Locators:
- `path:<project>/services/extraction/` — extraction sidecar boundary
- `kind:extraction-runtime` — ledger projection of extraction work

Notes: Hot path; ADR 0013 covers idea-tracking, the sidecar boundary
lives in your sidecar ADR.

## Discovery pipeline

Tier: core

Locators:
- `path:<project>/services/discovery/` — discovery service
- `kind:auto-match` — auto-match ideas in the ledger

## UI polish

Tier: supporting

Locators:
- `path:<project>/templates/widgets/` — visual polish surfaces

Notes: Real work but not load-bearing.
-->
