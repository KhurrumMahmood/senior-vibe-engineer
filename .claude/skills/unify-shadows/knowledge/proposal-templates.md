# /unify-shadows proposal templates

Use exactly one section below as the body for `proposal.md` under
`## Proposed action`, based on the scan's `consolidation_shape`. Replace
the bracketed prompts with artifact-backed content from the profile files,
capability matrix, triage notes, and current source references.

## keep_separate_document_why

Document the separation; do not merge the implementations.

- Add or update an in-tree `INTENTIONAL shadow` comment for each member
  that lacks one. The comment must name the load-bearing divergence and
  cite the caller or resource contract that makes unification unsafe.
- Preserve the existing public signatures and return contracts.
- Extract a shared helper only if every profile identifies the same
  tractable share opportunity and the deletion test from
  `.claude/skills/_common/interface-depth.md` passes. If not, write
  "No tractable share" with the profile citations.
- Handoff to `/fix-workflow semantic:<id>` only for the documentation or
  narrow helper work above. Do not reopen the merge decision.

## share_utilities

Keep the separate entry points and extract the repeated mechanism they
share.

- Name the helper, its owning module, and the exact behavior it hides.
  The helper must remove repeated behavior from at least two members
  without forcing their signatures, callers, retry policy, resource
  ownership, or return contract to collapse.
- List each member change as `member -> call helper for <behavior>`.
- State the interface-depth deletion test result: what complexity would
  return to each caller if the helper were deleted.
- Preserve each member's caller-facing contract unless the caller-impact
  table explicitly names a migration and the test matrix covers it.

## complete_migration

Choose one surviving implementation and migrate all callers to it.

- Name the survivor and why it is canonical, citing profile evidence.
- For every other member, state whether it becomes a thin adapter during
  migration or is deleted in the same change. Do not leave a permanent
  parallel path.
- List caller moves in order, including import rewrites and return-shape
  adaptations.
- The stop condition must include a grep proving no live callers remain
  on retired members, plus tests for every subsystem that moved.

## merge_at_workflow

Unify at the workflow boundary rather than at helper level.

- Name the workflow authority that should own the choice between current
  members, and explain why lower-level helper extraction would leak policy.
- Move caller selection or orchestration into that authority while
  preserving member internals until tests prove the workflow contract.
- List the caller-facing workflow API and the compatibility adapters, if
  any, that are temporary during migration.
- The stop condition must include one workflow-level test that proves the
  authority chooses the right member for each supported case, plus a grep
  proving callers no longer select between shadows directly.
