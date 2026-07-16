# WP2 fresh-context verification attempt 1

- Date: 2026-07-16
- Verifier: `/root/wp2_fresh_verifier`
- Model: Codex based on GPT-5; no more specific runtime model exposed
- Revision: `40a0880dce49501c5ca1ba5b7dd17edb562c2dc5`
- Starting workspace: clean
- Platform: macOS 26.5.1 / Darwin 25.5.0 / arm64
- Toolchain: Python 3.11.10; pytest 9.0.3; PyYAML 6.0.3; Ruff 0.6.9; Git 2.46.1

Overall: **FAIL**. AC-2.3, AC-2.4, and AC-2.6 pass. AC-2.1, AC-2.2,
and AC-2.5 fail on two independently reproduced trust-boundary bypasses. WP2
must remain `in_progress`.

## Exact checks

- Full suite: exit 0, `502 passed, 1 skipped`.
- WP2 matrix: 210 collected; exit 0, `209 passed, 1 skipped`.
- Class A: 16 collected and 16 passed.
- Metadata lint, spec coverage/inventory, targeted Ruff, executable seed-host
  search, and route-sprawl detector/reporter all exited 0.
- Route-sprawl hashes matched the baseline: `e3b0c442…b855`,
  `ff59f32e…abd`, and `82204fb5…55f`.
- Disposable adversarial probes exited 0 and reproduced both blockers below.

## Adversarial findings

1. A correctly rehashed but structurally invalid profile returned zero
   validation errors. The profile used string-valued `code_roots`, a
   string-valued `commands.test`, and an integer evidence `path`. This can make
   perimeter enumeration silently empty while retaining a valid content hash.
2. Monkeypatching `run_perimeter_audit()` to return only `{"gaps": []}` made
   adoption report `ready` while `perimeter.json` and `perimeter.md` did not
   exist. `evidence.json` still referenced those nonexistent artifacts.
3. The implementer report said `210 passed, 1 skipped`; exact execution was
   210 collected and `209 passed, 1 skipped`. The report is corrected alongside
   this retained failed attempt.

Other bounded attacks passed: unregistered/unevidenced assertions and durable
profile hash tampering were rejected; ambiguous script suffixes abstained;
TypeScript/Django exclusion, four-surface agreement, evidence negatives,
reason-bearing exclusions, neutral longest-match labels, undeclared inventory,
Class C equivalence, Class A, and route-sprawl stayed green.

## AC verdicts

- **AC-2.1: FAIL.** Normal five-host profiles are deterministic and evidenced,
  but the canonical validator accepts materially malformed, correctly rehashed
  nested structures as schema-valid.
- **AC-2.2: FAIL.** Ordinary profile consumption, idempotency, gap reporting,
  and host ownership pass, but a truthy fake audit result bypasses mandatory
  perimeter artifacts and permits false adoption success.
- **AC-2.3: PASS.** Capability/layer/binding requirements and material reasons
  are enforced; TypeScript does not receive a Django-bound skill.
- **AC-2.4: PASS.** All four routing/manifest surfaces use the shared activation
  decision and exact reasons.
- **AC-2.5: FAIL.** The installed/version/evidence negative matrix and ordinary
  preflight pass, but malformed profiles can suppress source cells and produce
  a false no-gap result.
- **AC-2.6: PASS.** Durable/empty inventories, hash tampering, neutral/longest
  surfaces, ignore-first equivalence, ambiguous script abstention, seed-root
  search, all 16 Class A tests, and byte-identical route replay pass.

## Workspace integrity

Only automatic command telemetry changed during verification:
`logs/agent_policy/test_runs.jsonl` moved from SHA-256
`626ff572b868016e8f9360a3731ffbaf98670de9f248d738c87d2f2d2dee83be`
(one line) to
`6a865cfafbad399063b57019d1e1a6c1c536b951522383d41f33e192ad72b575`
(seven lines). The exact six-line append was inspected and then removed by the
coordinator. No source, test, spec, plan, or prior evidence content changed.

## Required repairs

- Validate every nested host-profile field type, evidence record, component
  profile, surface-label entry, and aggregate/root consistency invariant.
- Require profile/result-bound perimeter JSON and Markdown artifacts before
  adaptation may report `ready`.
- Add regressions for the shape-less truthy audit, correctly rehashed malformed
  profiles, and whole-codebase false-clean path, then repeat all ACs with a new
  fresh-context verifier.
