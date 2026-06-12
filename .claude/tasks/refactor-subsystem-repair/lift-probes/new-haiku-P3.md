# Phase 5.3.5 Decision: 3-Instance Naming Convention Violation

## Decision

**Fix sequentially in the orchestrator.** Do NOT dispatch the micro-fix swarm.

## Governing Rule

From `knowledge/execution-playbook.md` §5.4, the violation-count decision table:

> | Violation count | Decision | Execution |
> |---|---|---|
> | 1–4 | **Inline fix** in this refactor | Fix sequentially in the orchestrator. Not worth swarm overhead. |

With exactly 3 instances of the same naming-convention violation, the count falls squarely in the **1–4 range**, which mandates sequential orchestrator fixes, not a micro-fix swarm.

## Rationale

The playbook rationale (lines 299–302) clarifies the threshold logic:

> The 10-violation threshold is a heuristic — err on the side of inline fix if the violations are mechanical and in a small number of files. Err on the side of follow-up if fixes need judgment or span hot files the main worktree is actively editing.

With only 3 call sites across 3 files, the overhead of spawning a parallel sub-agent swarm (context setup, coordination, per-file dispatch) exceeds the cost of sequential orchestrator fixes. Swarm economics only favor parallel dispatch at 5+ violations (see the 5–10 row).

## Execution Path

1. Fix each of the 3 instances sequentially in the orchestrator.
2. Commit once all 3 are complete with a single `[<spec-id>:convention]` commit.
3. Re-run `python3 scripts/specs.py violations <spec-id>` to confirm the violation count dropped to zero.
