---
name: extract-workflow-registry
description: "Propose a canonical registry for a mapped product workflow: step id, label, route, visibility, status provider, active tab, template owner, frontend boot keys, and registry-owned endpoint payloads. EXPLAIN skill; no code edits."
argument-hint: "<workflow-name> [--workflow-map .claude/docs/workflows/<workflow-name>.md]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: explain
best_for: |
  A mapped product workflow ready for a canonical registry proposal —
  step id, label, route, visibility, status provider, active tab,
  template owner, frontend boot keys, registry-owned endpoint
  payloads. EXPLAIN; no code edits.
not_for: |
  Workflow detection (use /map-product-workflow first, then
  /find-workflow-duplication to surface drift). Refactor execution
  (use /fix-workflow or /refactor-subsystem). Drafting a brand-new
  workflow that has not been mapped yet.
language: python
framework: django
---

# /extract-workflow-registry

You are the orchestrator for a product-topology EXPLAIN skill. Convert
a product workflow map plus topology-drift findings into a concrete
registry proposal that a later refactor can implement.

## How success is judged

- `reports/workflow-registry/<workflow>/proposal.md` exists and names
  the source map, registry fields, proposed step entries, endpoint
  payload fields, consulted findings, guard candidates, and execution
  plan.
- The proposal's registry contract includes every field the skill
  promises: `id`, `label`, `route_name`, `url_builder`,
  `visibility_rule`, `status_provider`, `active_tab_key`,
  `template_owner`, `frontend_boot_keys`, `api_endpoints`, and
  `api_endpoint_templates`.
- The run summary pastes the real `propose.py` output (`wrote ...`) or
  the real error line. A missing workflow map is a stop condition, not
  permission to invent steps from memory.
- No production code edits occur; the proposal is the only write under
  `reports/workflow-registry/<workflow>/`.
Write toward these gates from the pipeline command.

## Authority vs Lexical Duplication

Do not treat every repeated word or URL fragment as a registry smell.
Labels like `Setup`, tab ids like `pages`, or `/api/sites/` in docs,
tests, and URLconfs are often normal lexical duplication.

Flag duplicated workflow authority instead: two or more executable
layers independently deciding the same workflow contract. Examples:
templates and JS each inventing step maps, views and JS each knowing
endpoint suffixes, or docs and code each carrying separate ordered
workflow tables that users depend on.

## Scope

- Supported workflow: any workflow with a map from
  `/map-product-workflow <workflow>`.
- Output: `reports/workflow-registry/<workflow>/proposal.md`.
- Python: `.venv/bin/python`.
- No production code edits.

## Pipeline

```bash
.venv/bin/python .claude/skills/extract-workflow-registry/scripts/propose.py \
  "<workflow-name>" \
  --workflow-map ".claude/docs/workflows/<workflow-name>.md" \
  --project-root "$(pwd)"
```

Add `--finding <path>` for route-sprawl, workflow-duplication,
frontend-contract, or docs-route reports that should inform the
proposal.

If the map path does not exist, abort and run
`/map-product-workflow <workflow-name>` first. Do not fall back to the
host descriptor directly: this skill consumes the reviewed map artifact
so the registry proposal is traceable to the topology snapshot.

## Registry Contract

The proposal always includes these fields:

- `id`
- `label`
- `route_name`
- `url_builder`
- `visibility_rule`
- `status_provider`
- `active_tab_key`
- `template_owner`
- `frontend_boot_keys`
- `api_endpoints`
- `api_endpoint_templates`

## Feature-Start Considerations

When a new product workflow feature adds a page, sub-tab, boot payload
key, status provider, or site-scoped endpoint, ask whether the workflow
registry should own that contract from the start. Do not wait for
three templates, two JS files, and a view to independently learn the
same step or endpoint.

Nice-to-have checks for new workflow features:

- Add reverse-backed contract tests for route/endpoint keys instead of
  copying expected URL strings into another table.
- Put template-to-JS boot data behind one payload/accessor, not new
  scattered `window.*` globals.
- Use dynamic endpoint templates for path parameters rather than
  ad-hoc string concatenation in JS.
- If the feature replaces a prototype page or script, plan the dormant
  sweep/delete pass as part of feature graduation.

## Endpoint Boot Payload Pattern

For `/sites` workflow endpoints, route definitions stay in Django
URLconf. The registry owns consumer endpoint knowledge:

- Generate payload values with Django `reverse()` from stable route
  names; do not hand-build `/api/sites/<site_id>/...` strings.
- Static site-scoped endpoints belong in `api_endpoints`.
- Dynamic path-parameter endpoints belong in `api_endpoint_templates`
  with explicit placeholder names, e.g. `{pies_id}`.
- Frontend consumers call boot helpers such as `siteEndpoint(...)`,
  `siteEndpointWithQuery(...)`, or `siteEndpointFor(...)` rather than
  concatenating route suffixes.
- Adoption proposals must name cache-busted JS includes, boot-payload
  characterization tests, and the regression guard that will block
  reintroduced hardcoded consumer URLs.
- Plan adoption in two passes: migrate active template-loaded
  consumers first, then sweep dormant workflow-family JS. Delete stale
  prototype files when they carry no unique product knowledge; keep a
  quarantine only when a human-readable reason survives review.

## Replay / smoke

For a deterministic replay, create a tiny workflow map containing a
Workflow Steps table, a Site-Scoped API Routes table, and a Frontend
Boot Contract table, then run `propose.py --workflow-map <fixture>
--skip-effectiveness-log --output <tmp>/proposal.md`. Paste the
`wrote <tmp>/proposal.md` line and inspect the proposal for
`api_endpoints` and `api_endpoint_templates`. This is the replay case
for the map-input and endpoint-field contracts.

## When things go sideways

| Symptom | Action |
|---|---|
| `.claude/docs/workflows/<workflow>.md` is missing | Abort; run `/map-product-workflow <workflow>` first or pass a valid `--workflow-map` |
| Workflow map contains zero steps | Abort; refresh `.engineering/docs/product-workflows.md`, rerun `/map-product-workflow`, then retry |
| Site-scoped API table is empty | Continue with `api_endpoints: none` and `api_endpoint_templates: none`; the proposal still owns step and boot contracts |
| `--finding` path is missing | Abort that finding input; rerun the drift detector or omit the stale finding |
| Effectiveness logging fails | Keep the proposal if `proposal.md` was written; paste the logging failure and do not claim the effectiveness record landed |
| User asks to edit routes/templates/JS now | Stop after the proposal and hand off to `/fix-workflow` or `/refactor-subsystem`; execution is out of scope |

## Next Skills

- `/refactor-subsystem` for multi-file adoption of the registry.
- `/fix-workflow` for a small route/doc/template cleanup.
- `/prevent-regression` after the registry or boot payload convention
  lands and has tests.
