# WP2 shared routing and honest-perimeter slice

- Date: 2026-07-16
- Implementer: Codex
- Implementation revision: `4cda6cf`
- Scope: AC-2.3 / AC-2.4 / AC-2.5, IM-5 / IM-6 / partial IM-9

## Implemented

- One canonical decision API joins the validated host profile, per-root
  language/framework compatibility, registry-selected layers/bindings,
  optional capability/layer/binding requirements, and manual host overrides.
- Manual opt-outs can narrow compatibility; allowlists cannot activate a
  stack-incompatible skill. Missing profiles retain an explicit migration-era
  manual decision rather than silently claiming profile compatibility.
- `/which-skill`, `/which-shape`, `/which-cleanup`, and `scripts/manifest.py`
  project the same decision object and inclusion/exclusion reasons.
- A TypeScript/React fixture excludes Django-bound skills. A four-surface
  end-to-end fixture proves byte-equivalent exclusion reasons for the same
  Python-bound skill.
- `/which-skill` enforces explicit required capabilities, layers, and bindings
  before relevance can become a recommendation.
- Perimeter evidence negatives now pin uninstalled detectors, missing
  contracts, incompatible contract versions, stale hashes, and structurally
  current evidence whose executable fixture emits the wrong observation.
- The whole-codebase health route executes the evidence-backed perimeter audit
  before presenting a conclusion. Missing profiles, gaps, and audit errors
  produce `incomplete_coverage`; the CLI exits 1 rather than returning a clean
  whole-codebase claim.

## Exact-revision implementer checks

| Command | Result |
|---|---|
| WP2 routing/profile/perimeter/registry focused pytest set | PASS — 149 passed |
| `.venv/bin/python scripts/skill_meta.py lint --quiet` | PASS — 76 skills |
| `.venv/bin/python scripts/specs.py coverage portable-host-profile-routing` | PASS — IM-1 through IM-6 implemented; no lag/ahead/orphans |
| `.venv/bin/python scripts/specs.py inventory-check portable-host-profile-routing` | PASS — CLEAN |
| Targeted Ruff command over every changed Python path | PASS |

This remains an implementation slice, not independent AC verification.
Profile-selected product surfaces and Class C equivalence fixtures (IM-7,
IM-8, and the remaining IM-9 matrix) must land before WP2 can move to
`implemented` or receive a fresh no-context verifier.
