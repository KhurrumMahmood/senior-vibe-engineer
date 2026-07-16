# WP0 fresh-context verification attempt 1

- Verifier: `/root/wp0_fresh_verifier` (Codex GPT-5; exact variant unavailable)
- Revision: `8c7e9b2e13b1dd0a42be19f49900eb9deea6f923`
- Pre-verification workspace: clean
- Platform: macOS 26.5.1, Darwin 25.5.0, arm64
- Toolchain: Python 3.11.10, pytest 9.0.3, Ruff 0.6.9, Playwright 1.60.0
- Overall: **FAIL**

## Criterion verdicts

| Criterion | Verdict | Independent evidence |
|---|---|---|
| AC-0.1 | PASS | Full suite collected 404 tests: 403 passed and one unrelated skip; all four renderer tests ran and the browser smoke launched headless Chromium. |
| AC-0.2 | PASS | 23 triage tests passed. Inspection proved the dated within-grace test injects `--now`; ignoring it changes the expected return code and fails the regression. |
| AC-0.3 | PASS | Counts/state/contracts agreed; the live gate was clean; direct bad-fixture execution emitted `missing_contract_script_ref` for `scripts/vanished.py`; the good fixture exited 0. |
| AC-0.4 | PASS | Plans, decisions, links, metadata, artifact drift, ecosystem consistency, self-lint, targeted Ruff, and the test suites all exited 0. |
| AC-0.5 | FAIL | Inheritance and retirement sequencing were incomplete. |

## Blocking AC-0.5 findings

1. Active predecessor references remained in the consistency-session plan, the
   status-projection plan, and the pending-threads design board.
2. W3 named five concept/binding families, but the successor guaranteed only
   two and permitted an arbitrary substitute pair.
3. AC-7.1/AC-7.2 preserved ADR 0027/0028 behavior but did not require formal
   acceptance, rejection, supersession, or accurate embodiment links.
4. W6's explicit onboarding funnel as one diagram had no exact owner.
5. Mapping and abandonment landed in the same commit, so no committed
   pre-retirement zero-unmapped state existed.

The verifier also noted two non-blocking specificity gaps: Success 1 did not
explicitly name router/perimeter criteria, and Success 6 did not enumerate all
reference-clean commands. Both are repaired with the blocking findings.

## Evidence hashes at the failed revision

```text
eb924780599a556b7edd530b835c14edca6dfa239daa2845583be16f326c6f3a  reports/portable-skill-ecosystem-completion/WP0/evidence.md
57d8e914d3ae715df61b0ecb129efc80858f74b66f8b48f3617a41b934ee3ccc  ai-docs/plans/portable-skill-ecosystem-completion.md
13d5c17bdde8e222d370b39339fe06576f7764a916b4a5e62b886119a923353f  ai-docs/plans/shareable-core-reorganization.md
```

Required-command logging dirtied only `logs/agent_policy/test_runs.jsonl`;
the verifier supplied its full patch and SHA-256, and the coordinator removed
only those generated records before beginning this repair.
