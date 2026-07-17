# WP3 Slice 6 phase-1 verification attempt 2

Date: 2026-07-16
Verifier: `/root/wp3_im14_trust_bundle/im15_lifecycle_lane/im14_fresh_verifier`
Model: GPT-5 Codex; exact variant and effort were not exposed
Revision: `9aed6b5149e6d7d116946065bdcb694a55310bea`
Tree: `9b59de312fc58690dc21d843cc570f240aff732d`
Workspace: clean detached checkout

## Verdict

- IM-14 integrated trust/router/bundle slice: **FAIL**
- Full IM-14: **OPEN**
- Findings: 0 P0, 1 P1

## Passing evidence

- The prior four P1 repairs passed: production structural closure, a new
  attempt-two dispatch ID, exact inline task/procedure/binding digest binding,
  and surface/path identity.
- All eight schemas passed structural closure, exemplars, unknown/missing-field
  rejection, and semantic checks.
- Representative direct, tie, low-shape, unique-selection, explicit, and
  answered-clarification outcomes matched ADR 0042. Only the selected outcome
  loaded a body; quick routing with zero compatible candidates returned the
  typed `error/no_compatible_candidate` outcome with zero body reads.
- A disposable five-surface router-only image had exactly five surfaces, zero
  activations, and ten router headers. The verifier recomputed release-root,
  bundle-index, manifest, raw-blob, recipe, projection, and tree digests.
- Wrong-root, blob-tamper, noncanonical-JSON, bootstrap-symlink, recovery-
  tamper, undeclared-file, traversal, absolute, backslash, non-NFC, and
  coherently rehashed cross-surface attacks failed closed.
- Focused verification: 229 passed. Ruff, strict metadata, framework leakage,
  intent/artifact drift, decisions, plans, spec coverage, and strict inventory
  were clean.

## Blocking finding

`validate_relative_path()` inspected `PurePosixPath(value).parts` after
construction. `PurePosixPath` normalized explicit `.` segments away, so a
projection recipe containing
`.engineering/bootstrap/claude-code/./runtime.py` passed both release build and
release verification. The materializer rejected it later, but trusting an
invalid release is a P1 boundary defect. Reproduced release-root digest:
`4008fb1ff56ffc75cf29ebbcf29de87f9bd5a1a493c34523820d14b9928e6786`.

Revision `42daae4fcd10170eab326028cb9d6eaffb53195d` repairs the raw-segment
validation and adds both direct and full release-build regressions. A new
fresh-context verifier must pass that exact or a descendant revision before
this bounded slice receives credit. This report grants no full IM-14 credit;
lifecycle, native execution adapters, dispatch runtime enforcement, privacy,
and IM-15–IM-18 remain open.
