# WP2 final implementation evidence

- Date: 2026-07-16
- Implementer: Codex
- Implementation revision: `849556f1a864edb2fb3929a7c542042d9185828f`
- Starting workspace: clean (`git status --short` emitted no paths)
- Platform: macOS 26.5.1 arm64
- Toolchain: Python 3.11.10; pytest 9.0.3; PyYAML 6.0.3
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

## Exact-revision commands

| Command | Exit | Result |
|---|---:|---|
| WP2-focused pytest matrix covering host profile, adaptation, perimeter, activation, all four routers, Class A/B/C, scope/route topology, registry consumers/guard, engineering home, and decode safety | 0 | `210 passed, 1 skipped` |
| `.venv/bin/python -m pytest -q` | 0 | `502 passed, 1 skipped` |
| `.venv/bin/python scripts/skill_meta.py lint --quiet` | 0 | `OK — 76 skills, 76 declaring new contract` |
| `.venv/bin/python scripts/specs.py coverage portable-host-profile-routing` | 0 | IM-1–IM-9 present; eight ARs documented; no lag/ahead/orphans |
| `.venv/bin/python scripts/specs.py inventory-check portable-host-profile-routing` | 0 | `Status: CLEAN` |
| Targeted Ruff over every changed Python implementation/test path | 0 | `All checks passed!` |
| Forbidden seed-host identifier search over all migrated Class B/C executable paths | 0 | `clean: no forbidden seed-host identifier` |
| Class A `--collect-only` over the two baseline modules | 0 | `16 tests collected` |
| Route-sprawl detector and reporter replay against this repository | 0 | zero findings; output hashes match the pre-change oracle |

The generic system `skill-creator` validator was also tried on both touched
skills. It rejected the ecosystem's intentional extended frontmatter fields
(`job`, `tier`, `language`, `framework`, `scans`, and related contract keys).
Those required fields were retained. The repository-authoritative metadata,
skill-compliance, ecosystem-consistency, pre-commit, and artifact-drift gates
all passed.

## AC mapping

- **AC-2.1 — implementer PASS.** Five-host deterministic/schema/evidence tests,
  mixed-root composition, native Rust/Go commands, and invalid assertion probes
  pass.
- **AC-2.2 — implementer PASS.** Adaptation consumes the profile, preserves
  host-owned files, is byte-idempotent, produces mandatory perimeter artifacts,
  surfaces gaps, and fails the injected bypass.
- **AC-2.3 — implementer PASS.** Capability/layer/binding requirements and
  explanations are enforced; the TypeScript fixture cannot receive a
  Django-bound recommendation.
- **AC-2.4 — implementer PASS.** One end-to-end conformance test obtains the
  identical activation decision/reason from `/which-skill`, `/which-shape`,
  `/which-cleanup`, and the activation manifest.
- **AC-2.5 — implementer PASS.** Uninstalled, missing-contract,
  version-incompatible, stale-hash, and wrong-executable-output evidence all
  remain gaps; reasonless exclusions fail; whole-codebase routing invokes the
  audit before a conclusion.
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
1c2c8842ecfa2bdab1387339c0642c073fc9d593186be23d231fc4f057401a30  .claude/skills/which-shape/scripts/route.py
ed8cc861d7165079eb0fa60440939619f91594f3589a4df5d50e6faba5c7abf8  ai-docs/specs/portable-host-profile-routing.md
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
