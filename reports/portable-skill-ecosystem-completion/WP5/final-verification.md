# WP5 final verification

Date: 2026-07-16
Verifier: `/root/wp5_final_ac_reverify`
Model: Codex based on GPT-5; exact variant and effort were not exposed
Revision: `430c9605566eef0c0a2b1cbf0ce2ba0135e6b6ae`
Tree: `6e1a3c12a63d2f02c40d80baa666458c3574a2c0`
Workspace: clean detached clone
Verdict: **PASS — AC-5.1–AC-5.7**

## Acceptance verdicts

| Criterion | Verdict | Independent result |
|---|---|---|
| AC-5.1 | PASS | Productized package/help, schema v1, identity v2, deterministic artifacts, CLI/library equivalence, and prototype isolation passed. |
| AC-5.2 | PASS | Five native tools plus Python/TypeScript parser observations retained provider, location, severity, version, raw hashes, and explicit executable identity. |
| AC-5.3 | PASS | Every required provider failure is typed, and a completed zero manifest remains distinct from failure. |
| AC-5.4 | PASS | The repaired same-root public scan→judgment→digest→diff→ratchet replay produced before=6, after=0, six fixed, zero new/persisting, and six actionable judgments. |
| AC-5.5 | PASS | Bounded ID-addressed digests, judgment-gated consumers, packets, and independent Git-derived harness rescan/diff ownership passed hostile attacks. |
| AC-5.6 | PASS | Python, TypeScript, Rust, Go, and mixed live boundaries passed; ADR 0036/0040 product paths and embodiment are accurate. |
| AC-5.7 | PASS | Network/DNS/model denial, agent-free detection, judgment failure blocking, consumer bypass rejection, and packet bounds passed. |

## Exact evidence

- Full suite: 857 passed, 0 skipped.
- Required live matrix: 11 passed, 17 deselected, 0 skipped.
- Browser/render: 4 passed, 0 skipped.
- Controlling focused suite: 79 passed.
- Parser/fact suite: 89 passed.
- Hostile trust/CLI/Git/judgment/harness suite: 90 passed.
- WP4 entry rerun: 65 passed plus live benchmark and cross-platform comparison.
- Spec coverage: 28/28 accounted, with 16 IM and 12 AR checked and zero
  lag, ahead, partial, or orphan references.
- Skill metadata: 76/76; 34 decisions and links, seven plans, and five specs
  clean.

The public replay's exact fixed IDs were `f2_0a30d4b2ed757586e5b2af8a`,
`f2_1db54af1a533aac716464a57`, `f2_2d64d3db8dba1ee27aeea997`,
`f2_3ebb34b1a5167a9fcfa0599e`, `f2_a49b292322bd714e190d40d0`, and
`f2_b2d8d610eed0a5b6c897960d`.

Pinned tools were Python 3.11.10, pytest 9.0.3, Ruff 0.6.9, ESLint 9.38.0,
TypeScript 5.9.3, rustc/Cargo 1.89.0, Clippy 0.1.89, and Go/Go-vet 1.24.6.
The verifier's runtime exposed Node 26.3.1/npm 11.16.0 while using the exact
pinned ESLint/TypeScript packages and absolute executables.

Two execution notes were non-blocking and retained rather than hidden. An
initial full-suite invocation omitted Ruff's directory from `PATH` and failed
four required-live cases; the mandated corrected environment passed 857/857.
One first WP4 entry benchmark exceeded warm-CV timing; an immediate unchanged-
tree rerun passed all 65 contracts, the live benchmark, and platform matrix.
No P0/P1 findings remain.
