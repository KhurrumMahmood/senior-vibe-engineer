# Repair round 2 — dogfood-driven fixes

Input: `dogfood-log.md` (Phase 0–1 of /refactor-subsystem executed by a
fresh agent on host-a's pre-cleanup `core/tasks.py`, 4,782 LOC, in a
detached-HEAD clone with no convention docs, no venv, commits
forbidden). The log's 11 frictions each cite the text the executor was
following — it is a ready-made change spec, and it is also the replay
case the repair-skill doctrine requires: *what failed* is the friction
entry, *what changed* is the fix below, *what a future run should now
pass* is the same scenario executed without that improvisation.

Round-1 context: the verifier-PASSed repair (commit 0eab687) fixed the
defects the frame review + scout found. The dogfood then surfaced a
DIFFERENT class — text that is internally consistent but unexecutable
against real-host conditions (read-only agent types, chunker quirks,
absent docs). Scenario probes and the independent verifier both missed
this class by construction: neither runs the skill against a host.

## Fixes applied (same-day, by a fresh implementer sub-agent)

| Friction | Severity | Fix |
|---|---|---|
| F8 scout dispatch unexecutable (Explore is read-only; brief's own tool list omits Write) | high | inventory-scout.md + SKILL.md §1.3 (+ §6.3 same class): dispatch `general-purpose`; Write added to allowed tools, restricted to the three output paths |
| F6 chunker "orphan regions" conflated with §1.1.5 orphan chunks (33 blank-line regions → 33 junk scouts if literal) | high | SKILL.md §1.3.0: two-notion disambiguation; trivial separators folded with recorded disposition; only substantive spans become orphan chunks |
| F4 no fallback when convention docs absent; worked-example helpers invite false rules | high | SKILL.md §1.2: absence fallback (generic hygiene table, recorded in convention-sources.md for Phase 4 audit, origin helpers must NOT be imported); rule table marked as origin-project illustration via host-adapter comment |
| F7 chunk-map path collision (two formats, one path, overwrite unstated) | medium | SKILL.md §1.3.0: orchestrator REWRITES the chunker's markdown; raw JSON preserved; scouts dispatch only from the rewritten map (R35) |
| F3 venv guard reads as hard abort in phases that issue no Django commands | medium | SKILL.md §1.1 + operations.md: guard scoped to phases issuing Django/manage.py commands |
| F5 `specs.py solid` L1 fails mid-1.2.5 (checks for the file this step produces) | medium | SKILL.md §1.2.5: consume only Gate-2 output here; L1 SKIP/FAIL expected, not an abort signal |
| F11 Phase 1.5 gate condition 3 silent on the middle tier (big file, modest history) | low-med | SKILL.md §1.5: middle tier = orchestrator-owned archaeology, ≥3 LR-T where history supports, else recorded shortfall |
| F2 `ledger.py list` exits 1 on empty result | low | SKILL.md §1.1: noted as normal empty result |
| F1 stub commit unconditional, collides with no-commit environments | low | bootstrap.md §0.4 + SKILL.md Phase 0 invariant: record intent, defer commit |
| F9 `{{branch}}` empty on detached HEAD | trivial | inventory-scout.md + micro-fix-scout.md: detached-HEAD substitution |

## Residuals (deferred, ledgered)

- **F10** — `specs.py inventory-check` counts only `@shared_task`
  symbols; plain top-level helpers (~40% of the dogfood file) are
  invisible to the spec-reality gate. Script change, not a text fix;
  matters most on re-entry runs. Ledgered on the repair-skill entry.

## Replay case

Re-running the identical dogfood assignment (Phase 0–1, same clone
shape: no convention docs, no venv, detached HEAD, no commits) should
now complete with **zero** of D1–D6's improvisations required by
missing text — every judgment the round-1 executor had to invent is now
written down. The dogfood verdict question ("could a fresh executor run
Phase 0–1 from the text alone?") flips from NO to YES-modulo-F10.
