---
name: extract-workflow-registry
description: "Propose a canonical registry for a mapped product workflow: step id, label, route, visibility, status provider, active tab, template owner, frontend boot keys, and registry-owned endpoint payloads. EXPLAIN skill; no code edits."
argument-hint: "<workflow-name: sites> [--workflow-map .claude/docs/workflows/sites.md]"
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

- Supported workflow: `sites`.
- Output: `reports/workflow-registry/<workflow>/proposal.md`.
- No production code edits.

## Pipeline

```bash
python3 .claude/skills/extract-workflow-registry/scripts/propose.py \
  sites \
  --workflow-map .claude/docs/workflows/sites.md
```

Add `--finding <path>` for route-sprawl, workflow-duplication,
frontend-contract, or docs-route reports that should inform the
proposal.

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

## Next Skills

- `/refactor-subsystem` for multi-file adoption of the registry.
- `/fix-workflow` for a small route/doc/template cleanup.
- `/prevent-regression` after the registry or boot payload convention
  lands and has tests.
