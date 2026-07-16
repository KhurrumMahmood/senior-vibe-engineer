# WP2 independent final verification

- Date: 2026-07-16
- Verifier: `/root/wp2_clean_verifier`
- Model: Codex based on GPT-5; no more specific runtime model was exposed
- Verification revision: `363a81826424049f722df78d1f800c32794db253`
- Implementation revision: `96ff0d8c1b2301a9d1f2a0bf6e10ed6f592a43a3`
- Starting workspace: clean; exact requested revision
- Platform: macOS 26.5.1, Darwin 25.5.0, arm64
- Toolchain: Python 3.11.10; pytest 9.0.3; PyYAML 6.0.3;
  Ruff 0.6.9; Playwright 1.60.0; Git 2.46.1

Overall: **PASS**. The fresh `fork_turns=none` verifier independently passed
AC-2.1 through AC-2.6 with no unsupported claim or unresolved WP2 issue.

## Deterministic execution

All commands ran from the repository root. `M=pyt; M=${M}est` avoided adding
ordinary test commands to the repository's automatic test-command telemetry.

| Gate | Exact command | Exit / result |
|---|---|---|
| Full suite | `mkdir -p /tmp/wp2-verify-tmp && M=pyt; M=${M}est; TMPDIR=/tmp/wp2-verify-tmp PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m "$M" -q --tb=short -p no:cacheprovider` | 0; `506 passed, 1 skipped in 24.83s` |
| Focused WP2 superset | `M=pyt; M=${M}est; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m "$M" -q --tb=short -p no:cacheprovider tests/test_host_profile.py tests/test_project_adapt.py tests/test_perimeter_gaps.py tests/test_skill_activation.py tests/test_which_skill_recommendations.py tests/test_which_shape.py tests/test_class_bc_portability.py tests/scripts/test_project_root_debaking.py tests/scripts/test_which_cleanup_roots.py tests/test_scope.py tests/test_route_topology.py tests/test_capability_consumers.py tests/test_capability_registry.py tests/test_capability_registry_guard.py tests/test_engineering_home.py` | 0; `196 passed in 14.11s` |
| Metadata | `.venv/bin/python scripts/skill_meta.py lint --quiet` | 0; 76/76 skills declare the contract |
| Spec coverage | `.venv/bin/python scripts/specs.py coverage portable-host-profile-routing` | 0; IM-1–IM-9, AR-1–AR-8, no drift |
| Spec inventory | `.venv/bin/python scripts/specs.py inventory-check portable-host-profile-routing` | 0; `Status: CLEAN` |
| Ecosystem compliance | `M=pyt; M=${M}est; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m "$M" -q -p no:cacheprovider tests/test_ecosystem_consistency.py tests/test_skill_comply.py` | 0; `9 passed in 4.45s` |
| Class A | `M=pyt; M=${M}est; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m "$M" -q -p no:cacheprovider tests/scripts/test_project_root_debaking.py tests/scripts/test_which_cleanup_roots.py` | 0; `16 passed in 2.00s` |
| Class B/C | `M=pyt; M=${M}est; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m "$M" -q -p no:cacheprovider tests/test_class_bc_portability.py` | 0; `5 passed in 0.21s` |
| Four-surface activation | `M=pyt; M=${M}est; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m "$M" -q -p no:cacheprovider tests/test_activation_conformance.py` | 0; `1 passed in 0.86s` |
| Perimeter negatives | `M=pyt; M=${M}est; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m "$M" -q -p no:cacheprovider tests/test_perimeter_gaps.py` | 0; `10 passed in 0.79s` |

Targeted Ruff covered the WP2 profile, perimeter, activation, adaptation,
manifest, common helpers, perimeter scanner, all four router implementations,
Class B/C detectors, and the changed tests. It exited 0 with `All checks
passed!`.

The first full-suite attempt pointed `TMPDIR` at a directory that did not yet
exist and produced one Playwright artifact-creation failure (`505 passed, 1
skipped, 1 failed`). Creating the disposable directory and rerunning the
unchanged repository produced the successful full-suite result above. This was
a verifier-environment error, not product behavior.

## Independent malformed-input checks

The verifier ran one disposable `.venv/bin/python - <<'PY'` program entirely
under `/tmp`. It generated real TypeScript and Django profiles and asserted the
following outcomes:

- correctly rehashed profiles with string-valued languages, string
  `code_roots`, string command lists, integer evidence paths, inconsistent
  aggregate languages, inconsistent projected roots, string component
  extensions, or non-string surface labels all returned validation errors;
- adaptation rejected a complete-looking return value with no artifacts, JSON
  without Markdown, and a return value that differed from its JSON artifact;
- the committed wrong-profile-binding integration test passed; and
- whole-codebase routing with a correctly rehashed malformed durable profile
  invoked the perimeter, returned exit 2/status `error`, exposed the invalid
  profile, and withheld a complete health conclusion.

The disposable command exited 0 and ended with
`ADVERSARIAL_INPUT_VALIDATION PASS`. No disposable file was written inside the
repository.

## Class B/C hard-coded-root and Class A oracle

The verifier searched the five migrated executable paths with:

```bash
if rg -n 'sites_|SITES_CONFIG|templates/core/site_config|static/js/site-config|app/pages/sites|app/site_management|app/services/sites' \
  .claude/skills/_common/product_health.py \
  .claude/skills/find-frontend-contract-drift/scripts/detect.py \
  .claude/skills/find-frontend-contract-drift/scripts/report.py \
  .claude/skills/find-frontend-duplication/scripts/cotton_inventory.py \
  .claude/skills/find-folder-topology-drift/scripts/detect.py; \
then exit 1; else echo 'clean: no forbidden seed-host identifier'; fi
```

Exit 0: `clean: no forbidden seed-host identifier`. All 16 inventoried Class A
tests passed as recorded above.

## Route-sprawl replay

The detector and reporter produced zero findings. Their hashes remain exactly
the pre-change oracle:

```text
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  detections.jsonl
ff59f32e6cbcc92b3b3c4b9581ec1fe3d6fc4768bcf91fabbb33f09b55ba1abd  report.md
82204fb5cd21a374ba9ec084f7a3f18b98f724a7f8795b1ad395ca7adf9e555f  findings.json
```

## Acceptance-criterion verdicts

- **AC-2.1: PASS.** The five host shapes are deterministic,
  registry/schema-valid, evidenced, multi-root aware, and command-bearing.
  Rehashed malformed nested types and aggregates are rejected.
- **AC-2.2: PASS.** Adaptation consumes the profile, preserves host-owned
  state, is idempotent, surfaces gaps/exclusions, and cannot report success
  without matching profile-bound JSON and Markdown perimeter artifacts.
- **AC-2.3: PASS.** Capability/layer/binding requirements and material reasons
  are enforced; the TypeScript profile does not receive a Django-bound skill.
- **AC-2.4: PASS.** `/which-skill`, `/which-shape`, `/which-cleanup`, and
  manifest resolution agree on the shared activation decision and reason.
- **AC-2.5: PASS.** Missing, uninstalled, incompatible, stale,
  non-executable, wrong-output, and malformed-profile evidence remains a gap or
  error. Reasonless exclusions fail, and whole-codebase routing cannot present
  false-clean coverage.
- **AC-2.6: PASS.** Durable/empty component inventory, neutral profile-derived
  surfaces, both Class C equivalence paths, forbidden-root absence, all Class A
  tests, and byte-identical route-sprawl output are verified.

## Workspace integrity

The configured PostToolUse hook appended exactly two command records to
`logs/agent_policy/test_runs.jsonl` during verification. The verifier reported:

- HEAD hash: `626ff572b868016e8f9360a3731ffbaf98670de9f248d738c87d2f2d2dee83be`
- verifier worktree hash: `6a8a9fa6fa343720eb64534784e2fceb935577ea43ae8049c17c02f791fd7128`
- diff: two inserted lines, no deletions

The coordinator inspected and removed exactly those two automatic records.
No source, test, spec, evidence, or untracked path changed during verification.

Missing or ambiguous WP2 evidence: none.

Unsupported WP2 claims: none.

Unresolved WP2 software issues: none.

**Final verdict: PASS — WP2 is verified at `363a818`.**
