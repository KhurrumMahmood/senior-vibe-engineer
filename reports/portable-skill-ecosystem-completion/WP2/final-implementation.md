# WP2 final implementation evidence

- Date: 2026-07-16
- Implementer: Codex
- Base implementation revision: `849556f1a864edb2fb3929a7c542042d9185828f`
- Post-verifier repair revision: `96ff0d8c1b2301a9d1f2a0bf6e10ed6f592a43a3`
- Repair verification workspace: clean before execution; automatic test telemetry
  was removed afterward and its tracked hash remained `626ff572…ee83be`
- Platform: macOS 26.5.1 arm64
- Toolchain: Python 3.11.10; pytest 9.0.3; PyYAML 6.0.3; Ruff 0.6.9
- Scope: AC-2.1–AC-2.6; IM-1–IM-9

This record is implementer evidence, not independent verification. It moves
WP2 only to `implemented`; a fresh `fork_turns=none` verifier must independently
issue PASS for every AC before the tracker can say `verified`.

## Final implementation slice

- Durable `.engineering/project/host-profile.json` component and surface data
  is content-authenticated before Class B/C consumers use it. A present invalid
  durable profile does not silently revive a legacy manifest.
- Product-health surfaces use longest-match host selectors and neutral
  `skill`/`docs`/`tests`/`product_surface` fallbacks; no seed-host fallback
  remains.
- Component callsite inventory includes JavaScript/TypeScript/Vue family
  extensions and returns the canonical empty inventory when undeclared.
- Folder-topology and frontend-contract fixtures share route-sprawl's
  ignore-first roots and prove selected, ignored, outside-root, extension, and
  marker behavior.
- Frontend shared scripts resolve only against the scoped selected file set;
  ambiguous suffixes abstain. One consolidated boot payload is recognized by
  structure rather than a host-owned global name.
- Profile/evidence JSON readers fail cleanly on undecodable input.

## Attempt-1 verifier repairs

- The host-profile validator now enforces every top-level and nested field,
  exact mapping shapes, strict integer schema/contract versions, normalized
  relative paths, sorted unique nonblank lists, registry-valid per-root and
  aggregate stacks, evidence-to-assertion correspondence, exact projected
  roots, reason-bearing exclusions, component/surface types, and the content
  hash. Correctly rehashed malformed profiles fail before any consumer can
  treat them as coverage evidence.
- Adaptation now requires matching, nonempty perimeter JSON and Markdown
  artifacts with schema/version, executable-coverage mode, profile hash,
  exclusions, row shapes, and returned-payload equality before adoption may be
  `ready`. The boundary lives in `scripts/_lib/perimeter_audit.py`, keeping
  `project_adapt.py` below the 1,000-line spec inventory ceiling.
- Whole-codebase routing catches invalid-profile activation failures, exposes
  the activation error, still invokes the mandatory perimeter, and withholds a
  complete health conclusion when the scanner rejects the profile.

## Exact-revision commands

| Command | Exit | Result |
|---|---:|---|
| Repair-focused pytest matrix covering host profile, adaptation, perimeter, activation, routing, Class A/B/C, scope, registry consumers/guard, and engineering home | 0 | `181 passed` |
| `.venv/bin/python -m pytest -q --tb=short` | 0 | `506 passed, 1 skipped` |
| `.venv/bin/python scripts/skill_meta.py lint --quiet` | 0 | `OK — 76 skills, 76 declaring new contract` |
| `.venv/bin/python scripts/specs.py coverage portable-host-profile-routing` | 0 | IM-1–IM-9 present; eight ARs documented; no lag/ahead/orphans |
| `.venv/bin/python scripts/specs.py inventory-check portable-host-profile-routing` | 0 | `Status: CLEAN` |
| `.venv/bin/python -m pytest -q tests/test_ecosystem_consistency.py tests/test_skill_comply.py` | 0 | `9 passed` |
| Targeted Ruff over every changed Python implementation/test path | 0 | `All checks passed!` |
| Forbidden seed-host identifier search over all migrated Class B/C executable paths | 0 | `clean: no forbidden seed-host identifier` |
| Class A execution over the two baseline modules | 0 | `16 passed` |
| Route-sprawl detector and reporter replay against this repository | 0 | zero findings; output hashes match the pre-change oracle |

The generic system `skill-creator` validator was also tried on both touched
skills. It rejected the ecosystem's intentional extended frontmatter fields
(`job`, `tier`, `language`, `framework`, `scans`, and related contract keys).
Those required fields were retained. The repository-authoritative metadata,
skill-compliance, ecosystem-consistency, pre-commit, and artifact-drift gates
all passed.

## AC mapping

- **AC-2.1 — implementer PASS.** Five-host deterministic/schema/evidence tests,
  mixed-root composition, native Rust/Go commands, invalid assertions, and 30
  correctly rehashed nested/aggregate/type mutations all pass.
- **AC-2.2 — implementer PASS.** Adaptation consumes the profile, preserves
  host-owned files, is byte-idempotent, produces mandatory perimeter artifacts,
  surfaces gaps, and rejects both the shape-less truthy bypass and artifacts
  bound to another profile.
- **AC-2.3 — implementer PASS.** Capability/layer/binding requirements and
  explanations are enforced; the TypeScript fixture cannot receive a
  Django-bound recommendation.
- **AC-2.4 — implementer PASS.** One end-to-end conformance test obtains the
  identical activation decision/reason from `/which-skill`, `/which-shape`,
  `/which-cleanup`, and the activation manifest.
- **AC-2.5 — implementer PASS.** Uninstalled, missing-contract,
  version-incompatible, stale-hash, and wrong-executable-output evidence all
  remain gaps; reasonless exclusions fail; whole-codebase routing invokes the
  audit before a conclusion; malformed profiles produce an explicit error and
  cannot become a false-clean scan.
- **AC-2.6 — implementer PASS.** The five committed Class B/C tests cover
  durable/empty inventory, profile/neutral surfaces, both Class C equivalence
  paths, generic boot payloads, and the hard-coded-root guard. The 16 Class A
  tests stay in the matrix, and the route-sprawl replay is byte-identical to
  its baseline outputs.

## Evidence hashes

```text
d6ed6a9a27291212f328155401294a095480f1ef7261930a354f3a2d02d38957  .claude/skills/_common/engineering_home.py
3ff644ecf26575399aced3d877c2f07dadc539069692d2e792c749b621a65882  .claude/skills/_common/product_health.py
9f0d7f24845928fc78d81bc53f65730f5b69f3e6938190b05d20e8055bbf24dd  .claude/skills/find-frontend-contract-drift/SKILL.md
55706bee6d37d552428e47e168fd666b540793659a1f472c07cdc600bed4aa86  .claude/skills/find-frontend-contract-drift/scripts/detect.py
01accbaa66714798361c6e0791ecb0b4e390ebaefc138f1c9d2e9c7a8b93ef1a  .claude/skills/find-frontend-contract-drift/scripts/report.py
c40b13f708e6751c3343f85ccd786b8e845279953e9dea8bb68a2b8363268d2f  .claude/skills/find-frontend-duplication/SKILL.md
30bc3f10e1b7bfbbf4f4f2937d7916259cbda52825e18fa7e0d44455c0e48cd0  .claude/skills/find-frontend-duplication/scripts/cotton_inventory.py
16d709b1db7ce968325816602cf8c9fc1a05265467bce9bf0bda51b45472b091  .claude/skills/find-perimeter-gaps/scripts/scan.py
000ec2593da9c387696ce44baf1f373de6ca93487ab8c38e52f18f6434125748  .claude/skills/which-shape/scripts/route.py
aaa4a77aa867dd35a2c51fae98f5e9eaf0bd82da64ec702201bc89bb8aef8e61  ai-docs/specs/portable-host-profile-routing.md
4bb5df48cec4d24f7cd0f2b41c17c8a2cf687c8c52df2149dbfdc470dcd4e0fc  scripts/_lib/host_profile.py
3658e5682540716e7c9b62647d963794d255411c0dff5d7f521374fa5347a438  scripts/_lib/perimeter_audit.py
7ddcbd93035356738c80289c83c37ce68d51d11990f762729fa4c48a142ce9fd  scripts/project_adapt.py
7db9bed87c47d15eee9836ea19b3d511497d4ee1291ba5b285c0e9c50fe1412a  tests/test_host_profile.py
312ff0809616d6e07147bcc063cd0f8259286ba623f2b5cfd692f3d5c00820f1  tests/test_perimeter_gaps.py
79de20912afadd76e8d5b5eae133d0113505e3bccf01be23e91692e549012748  tests/test_project_adapt.py
42f578313017e502d6b592096d9b1e577540fff74914de74053af80f5e40f91b  tests/test_which_shape.py
fe7d2812ca9b20bd727d59ff816b1e36c21d8356e8d2a9a8764b7f8aa0226d11  tests/test_class_bc_portability.py
```

Route replay outputs:

```text
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  detections.jsonl
ff59f32e6cbcc92b3b3c4b9581ec1fe3d6fc4768bcf91fabbb33f09b55ba1abd  report.md
82204fb5cd21a374ba9ec084f7a3f18b98f724a7f8795b1ad395ca7adf9e555f  findings.json
```

Missing or ambiguous implementation evidence: none. Independent adversarial
verification remains intentionally pending.
