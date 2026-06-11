# Plans

Forward-looking design documents for **System-tier** work — new
subsystems, cross-subsystem features, multi-week initiatives. A plan
captures *why and how* a feature should be built before there is any code
to preserve. When the plan is mature enough to drive execution it gets
**promoted** to a behavior-preserving spec under `ai-docs/specs/`.

## Plan vs Spec — when to use which

| | **Plan** (`ai-docs/plans/`) | **Spec** (`ai-docs/specs/`) |
|---|---|---|
| **Time horizon** | Forward — what we want | Frozen — what is true |
| **Lifecycle** | draft → scoped → impacted → architected → promoted | proposed → planned → in_progress → done |
| **Author** | The four System-tier skills | `/refactor-subsystem`, `/plan-feature`, manual |
| **Mutability** | Edited freely until promoted | Behavior-preserving — changes are discrete |
| **Anchor** | Decision provenance + impact analysis | Code roots + checklist items (`IM-N`, `AR-N`) |
| **Skills** | `/scope-feature`, `/impact-feature`, `/architecture-fit`, `/plan-spec` | `/refactor-subsystem`, `/fix-workflow` |

A plan is the artifact of *deciding to build*. A spec is the artifact of
*executing the build*. The promote step turns one into the other.

## Lifecycle

```
draft        — bare scaffold, no content
   │  /scope-feature
   ▼
scoped       — bounds in/out, success criteria, non-goals filled
   │  /impact-feature
   ▼
impacted     — full reachability + blast radius mapped
   │  /architecture-fit
   ▼
architected  — conformance with decisions + patterns + smells; open ADRs flagged
   │  /plan-spec
   ▼
promoted     — `successor_spec` set; spec scaffolded under ai-docs/specs/
```

Plans can also reach `abandoned` if the work is dropped before promotion.

## Frontmatter

```yaml
---
name: <slug>
title: <one-line description>
status: draft         # draft | scoped | impacted | architected | promoted | abandoned
date: 2026-05-01
authors: []
motivating_decision: null   # ADR id (e.g. 0001) when a decision motivated this work
successor_spec: null        # spec id (slug) once promoted
subsystems: []              # list of touched subsystems
workflows: []               # list of touched product workflows
---
```

## Sections

A System-tier plan grows in four passes; each skill fills its sections
and advances `status`:

1. **Scope & Bounds** — in / out / non-goals (`/scope-feature`)
2. **Success Criteria** — observable outcomes (`/scope-feature`)
3. **Impact Map** — subsystems, models, routes, services touched (`/impact-feature`)
4. **Blast Radius** — call sites, behaviors-to-preserve (`/impact-feature`)
5. **Architecture Fit** — decision conformance, pattern alignment, new smells (`/architecture-fit`)
6. **Open Decisions** — forks needing an ADR (`/architecture-fit`)
7. **Promotion Notes** — what changed when promoted (`/plan-spec`)

## CLI

```bash
.venv/bin/python scripts/plans.py init <slug> [--title ...] [--date YYYY-MM-DD] [--motivating-decision NNNN] [--force]
.venv/bin/python scripts/plans.py list [--json]
.venv/bin/python scripts/plans.py show <slug>
.venv/bin/python scripts/plans.py promote <slug> --code-roots <path> [--code-roots <path> ...] [--spec-id <slug>] [--allow-missing] [--force]
.venv/bin/python scripts/plans.py audit [--json]                      # lifecycle + link drift
```

`promote` writes `ai-docs/specs/<spec-id>.md` and requires at least one
`--code-roots` argument; pass it once per root the spec covers.

Note the form difference between CLI flags and YAML keys: the CLI uses
hyphens (`--motivating-decision`) while the frontmatter uses underscores
(`motivating_decision`). Same field, different surfaces.

Requires PyYAML (via `scripts/_lib/yaml_frontmatter.py`) — the project
venv already has it.
