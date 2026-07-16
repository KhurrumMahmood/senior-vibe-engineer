# WP2 profile-driven adaptation and perimeter slice

- Date: 2026-07-16
- Implementer: Codex
- Implementation revision: `bfc6d86`
- Scope: AC-2.2 / AC-2.5, IM-3 / IM-4, partial IM-6

## Implemented

- `/adapt-project` consumes the canonical versioned host profile; its generated
  adapter has no timestamp or absolute project-root content.
- Discovery emits host-profile, adapter, human report, perimeter machine/human
  reports, and an evidence manifest whose required tokens all resolve.
- The perimeter audit is mandatory on the adoption path. Missing/invalid audit
  artifacts are fatal; uncovered significant cells produce exit 1 and
  `incomplete_coverage`, never an adoption-success result.
- Durable reruns are byte-idempotent for generated adapter/profile artifacts,
  merge host-owned adapter extension keys, and leave host instructions and an
  approved interview profile unchanged.
- Canonical profile mode counts a detector only when its registry contract,
  hashes, tool/platform evidence, exact scan implementation, and fixture
  command validate and execute. Rejected candidates retain reasons.
- Accepted exclusions require `root:language=reason` and remain visible in
  machine output. Profile exclusions are also retained.
- Legacy declaration-only mode remains solely for the pinned predecessor
  comparison oracle; adoption always uses executable-evidence mode.

## Implementer checks

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_project_adapt.py tests/test_perimeter_gaps.py tests/test_host_profile.py` | PASS — 22 passed |
| `.venv/bin/python scripts/skill_meta.py lint --quiet` | PASS — 76 skills |
| `.venv/bin/ruff check scripts/project_adapt.py .claude/skills/find-perimeter-gaps/scripts/scan.py tests/test_project_adapt.py tests/test_perimeter_gaps.py` | PASS |
| `.venv/bin/python scripts/specs.py coverage portable-host-profile-routing` | PASS — IM-1 through IM-4 implemented; no lag/ahead/orphans |

This is a slice checkpoint, not independent AC-2.2/AC-2.5 verification. Shared
activation, whole-codebase entry routing, complete honest-evidence negative
matrix, and Class B/C work remain before WP2 can be implemented or verified.
