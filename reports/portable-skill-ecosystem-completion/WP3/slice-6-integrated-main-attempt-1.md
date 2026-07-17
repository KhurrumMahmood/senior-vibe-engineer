# WP3 Slice 6 integrated-main verification attempt 1

Date: 2026-07-16
Verifier: `/root/wp3_integrated_main_qa`
Model: GPT-5 Codex; exact variant and effort were not exposed
Revision: `f7dd6aed5942c0caa47de2c555823aa222dc9904`
Tree: `bf4e15222bee6c13b3d8471784a9b7b6e9a4ac9d`
Workspace: clean detached worktree

## Verdict

- Integrated bounded trust/dispatch/lifecycle tranche: **PASS**
- Findings: 0 P0, 0 P1
- Full native IM-14, IM-15, IM-16, and AC-3.6: **OPEN**

## Evidence

The combined release trust, schemas, tables, portfolios, surface matrix,
bundle, dispatcher, protected runtime, and lifecycle matrix collected 223
tests. The clean worktree passed 222; one test hard-coded a missing
worktree-local virtualenv. The verifier reran the remaining matrix as 222
passed/1 deselected and replayed that exact offline build-image/verify-image
case against the detached source with the shared explicit interpreter. The
expanded surface is therefore behaviorally 223/223 green. A focused 15-test
high-risk replay, Ruff, self-lint over 237 files, 76/76 strict metadata, 34
decision audits/links, seven plans, coverage, and all six strict inventories
passed.

Integration inspection found the dispatch runtime/tests byte-identical to
verified `923926f` and lifecycle implementation/CLI/tests byte-identical to
verified `64d66df`. The trust bundle correctly retains main's later explicit-
dot rejection, and the conflict resolution preserves both runtime and
lifecycle roots/inventories. Native lifecycle discovery and native launchers
remain intentionally unavailable and fail closed; this report grants no
native or full-criterion credit.
