# WP2 canonical host-profile slice

- Date: 2026-07-16
- Implementer: Codex
- Starting revision: `2029139`
- Implementation revision: `38f9c6c`
- Scope: AC-2.1 / IM-1 / IM-2 implementation checkpoint

## Implemented

- One registry-backed, versioned host-profile API with deterministic content
  hashing and no timestamp or absolute-root content.
- Per-root composition for Python/Django, TypeScript/Node/React, Rust, Go, and
  mixed monorepos.
- Evidence for every asserted language, framework, and tool.
- Neutral component/surface defaults, reason-bearing exclusions, code roots,
  and build/test/lint/dev/setup commands.
- Validation of registry IDs, evidence completeness, command shape, root
  ordering, exclusions, registry/contract versions, and content hash.

## Implementer checks

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_host_profile.py` | PASS — 5 passed |
| `.venv/bin/ruff check scripts/_lib/host_profile.py tests/test_host_profile.py` | PASS |

This is a slice checkpoint, not independent AC-2.1 verification. AC-2.1 remains
open until all WP2 work is cleanly committed and a fresh-context verifier passes
the exact acceptance criterion at that revision.
