# WP3 Slice 6 dispatch-runtime verification attempt 2

Date: 2026-07-16
Verifier: `/root/wp5_final_ac_verify/wp3_lifecycle_993ef7_review/dispatch_runtime_d451522_review`
Model: GPT-5 Codex; exact variant and effort were not exposed
Revision: `d451522ce649c507353c51a872e6fc732dc59576`
Tree: `93bd6b94928b6206002beb4d75b6cc2a47b70ffe`
Workspace: clean isolated worktree

## Verdict

- Repaired dispatch-runtime slice: **FAIL**
- Findings: 0 P0, 2 P1
- Full IM-14 and evaluated AC-3.6 surface: **OPEN**
- Native launcher evidence: absent; no credit granted

## Findings

1. The external surface-contract trust root remained claimant-controlled. The
   caller supplied both the contract and its expected digest, so a forged
   launcher declaration with a recomputed digest was accepted.
2. The injected executor and its accounting were not bound to the declared
   native launcher. An arbitrary callable could report a single input token
   and receive a successful result; no repository-owned launcher, trusted
   cancellation/accounting wrapper, zero-conversation proof, or native result
   integration existed.

The verifier independently cleared the five attempt-1 repair classes: the
canonical project state root and multi-root lock, exact retry/result binding,
conservative invalid-result handling, pre-mutation UUID validation, and raw/
artifact cleanup behavior. The focused runtime suite passed 26 tests; the
unique combined matrix passed 146 tests except one checkout-local virtualenv
path assumption that was replayed successfully with the main-clone
interpreter. Ruff, decision/spec/plan audits, and the symbol inventory were
clean. Repair must bind both capability and execution evidence to an external
verified release authority, and unsupported native launchers must fail closed.
