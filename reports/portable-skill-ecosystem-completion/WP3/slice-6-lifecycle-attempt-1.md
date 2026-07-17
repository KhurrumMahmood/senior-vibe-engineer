# WP3 Slice 6 lifecycle verification attempt 1

Date: 2026-07-16
Verifier: `/root/wp5_final_ac_verify/wp3_lifecycle_993ef7_review`
Model: GPT-5; exact variant and effort were not exposed
Revision: `993ef7e0486ac7a0af763209491101d3d0c0fb57`
Tree: `8f69b8a68ff248f46e2ec976f8e3f329bd874e95`
Workspace: clean isolated worktree

## Verdict

- IM-15: **FAIL**
- Evaluated AC-3.6 lifecycle surface: **FAIL**
- Findings: 0 P0, 7 P1
- IM-16 native matrix: not evaluated or credited

## Findings

1. `LifecycleInput.from_verified()` self-attested release trust without an
   out-of-band root; a fabricated release installed and verified.
2. The CLI accepted an arbitrary `module:factory` as a native discovery
   adapter, with no shipped command/parser/runtime/surface binding and no
   separation of host-owned discovery.
3. The authoritative legacy inventory was empty while a migration object could
   accept arbitrary entries and an unrelated digest; the CLI exposed no
   inventory-bound preview/plan path.
4. A forged canonical recovery journal could delete host-owned files before
   provenance was established; the verifier reproduced deletion of `HOST.txt`.
5. Repeated rollback toggled v2→v1→v2 instead of being idempotent.
6. Uninstall pruned arbitrary empty host-owned directories.
7. Update-time activation validation did not bind applicability and binding
   hashes.

The reviewer passed 105 lifecycle/contract/reference tests, 15 bundle tests
with one worktree-only deselection, and Ruff. One combined command had an
environmental failure because a pre-existing bundle CLI test assumes a
checkout-local `.venv`; that is not used to excuse any finding. The worktree
was clean before and after. No IM-15 credit is granted until all seven attacks
pass at an exact repaired revision in a new no-context review.
